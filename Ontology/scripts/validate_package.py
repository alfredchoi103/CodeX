from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from scripts.confidence import verify_claim_confidence


class CoreLoader(yaml.SafeLoader):
    """Safe YAML loader with the YAML 1.2 core boolean vocabulary."""


CoreLoader.yaml_implicit_resolvers = {
    key: [
        resolver
        for resolver in resolvers
        if resolver[0]
        not in {
            "tag:yaml.org,2002:bool",
            "tag:yaml.org,2002:int",
            "tag:yaml.org,2002:float",
            "tag:yaml.org,2002:null",
            "tag:yaml.org,2002:timestamp",
        }
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^[-+]?(?:0o[0-7_]+|0x[0-9a-fA-F_]+|0b[0-1_]+|[0-9][0-9_]*)$"),
    list("-+0123456789"),
)
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        r"^[-+]?(?:(?:[0-9][0-9_]*\.[0-9_]*|\.[0-9_]+)"
        r"(?:[eE][-+]?[0-9]+)?|"
        r"[0-9][0-9_]*[eE][-+]?[0-9]+|\.(?:inf|Inf|INF|nan|NaN|NAN))$"
    ),
    list("-+0123456789."),
)
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:null",
    re.compile(r"^(?:~|null|Null|NULL)?$"),
    ["~", "n", "N", ""],
)


def _construct_core_int(loader: CoreLoader, node: yaml.Node) -> int:
    value = loader.construct_scalar(node).replace("_", "")
    sign = -1 if value.startswith("-") else 1
    unsigned = value[1:] if value[:1] in "+-" else value
    if unsigned.startswith("0o"):
        return sign * int(unsigned[2:], 8)
    if unsigned.startswith("0x"):
        return sign * int(unsigned[2:], 16)
    if unsigned.startswith("0b"):
        return sign * int(unsigned[2:], 2)
    return sign * int(unsigned, 10)


CoreLoader.add_constructor("tag:yaml.org,2002:int", _construct_core_int)


def _construct_unique_mapping(
    loader: CoreLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    """Construct a mapping while rejecting duplicate explicit keys.

    Merge keys are excluded from the duplicate scan so YAML's normal merge/override
    behavior remains intact.  The constructor is installed only on CoreLoader.
    """
    explicit_keys: set[Any] = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=False)
        try:
            duplicate = key in explicit_keys
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found unhashable key: {exc}",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ValueError(f"Duplicate key {key!r}")
        explicit_keys.add(key)
    return yaml.constructor.SafeConstructor.construct_mapping(loader, node, deep=deep)


CoreLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


DOCUMENTS = {
    "manifest": "manifest.yaml",
    "semantics": "semantics.yaml",
    "kinetics": "kinetics.yaml",
    "bindings": "bindings.yaml",
    "policies": "policies.yaml",
    "evidence": "evidence.yaml",
    "migrations": "migrations.yaml",
    "traceability": "traceability.yaml",
}


def load_structured(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        if path.suffix == ".json":
            return json.load(stream)
        return yaml.load(stream, Loader=CoreLoader)


def validate_document(path: Path, schema_path: Path, definition: str) -> list[str]:
    try:
        document = load_structured(path)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return [f"{path.name}: cannot load document: {exc}"]
    try:
        schema = load_structured(schema_path)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return [f"<schema>: cannot load schema: {exc}"]
    if not isinstance(schema, dict):
        return ["<schema>: schema root must be an object"]
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or definition not in definitions:
        return [f"<schema>: unknown definition {definition!r}"]
    selected_schema = {
        "$schema": schema["$schema"],
        "$defs": definitions,
        "$ref": f"#/$defs/{definition}",
    }
    validator = Draft202012Validator(
        selected_schema, format_checker=FormatChecker()
    )
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(
            validator.iter_errors(document),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
    ]


OPEN_PAYLOAD_KEYS = frozenset(
    {"default", "descriptions", "metadata", "mapping", "value"}
)


def _walk(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            yield path + (str(key),), key, child
            if key not in OPEN_PAYLOAD_KEYS:
                yield from _walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + (str(index),))


def _is_external_ref(value: str) -> bool:
    return (
        "://" in value
        or value.startswith("external:")
        or bool(re.fullmatch(r"(?:docs/)?[A-Za-z0-9._/-]+\.md#[a-z0-9-]+", value))
    )


def validate_traceability_profile(
    schema: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    prefix = "<schema>: traceability profile configuration"
    if not isinstance(schema, dict):
        return None, [f"{prefix}: schema root must be an object"]
    profile = schema.get("x-traceability-profile")
    if not isinstance(profile, dict):
        return None, [f"{prefix}: missing x-traceability-profile object"]
    if profile.get("version") != "1.0":
        return None, [f"{prefix}: version must be '1.0'"]
    collections = profile.get("collections")
    if not isinstance(collections, list) or not collections:
        return None, [f"{prefix}: collections must be a non-empty array"]
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        return None, [f"{prefix}: schema $defs must be an object"]
    errors: list[str] = []

    def check_collection(owner_definition: str, collection: Any, location: str) -> None:
        if not isinstance(collection, dict):
            errors.append(f"{prefix}: {location} must be an object")
            return
        path = collection.get("path")
        definition = collection.get("definition")
        owner = definitions.get(owner_definition)
        target = definitions.get(definition) if isinstance(definition, str) else None
        if not isinstance(path, str) or not isinstance(definition, str):
            errors.append(f"{prefix}: {location} requires string path and definition")
            return
        try:
            item_ref = owner["properties"][path]["items"]["$ref"]
        except (KeyError, TypeError):
            errors.append(
                f"{prefix}: {location} path {owner_definition}.{path} is not a schema array"
            )
        else:
            if item_ref != f"#/$defs/{definition}":
                errors.append(
                    f"{prefix}: {location} expects {owner_definition}.{path} items "
                    f"to reference {definition}"
                )
        try:
            id_ref = target["properties"]["id"]["$ref"]
        except (KeyError, TypeError):
            errors.append(
                f"{prefix}: {location} definition {definition!r} has no stable id"
            )
        else:
            if id_ref != "#/$defs/stableId":
                errors.append(
                    f"{prefix}: {location} definition {definition!r} has no stable id"
                )
        nested = collection.get("nested", [])
        if not isinstance(nested, list):
            errors.append(f"{prefix}: {location}.nested must be an array")
            return
        for index, child in enumerate(nested):
            check_collection(definition, child, f"{location}.nested[{index}]")

    for index, collection in enumerate(collections):
        location = f"collections[{index}]"
        if not isinstance(collection, dict):
            errors.append(f"{prefix}: {location} must be an object")
            continue
        document = collection.get("document")
        if not isinstance(document, str) or document not in DOCUMENTS:
            errors.append(f"{prefix}: {location} references unknown document {document!r}")
            continue
        check_collection(document, collection, location)
    return (None if errors else profile), errors


def _accepted_traceable_ids(
    documents: dict[str, Any], profile: dict[str, Any]
) -> set[str]:
    """Derive accepted traceable IDs solely from the versioned schema profile."""
    default_status = documents.get("manifest", {}).get("status")
    result: set[str] = set()

    def collect(owner: dict[str, Any], collection: dict[str, Any], inherited: str) -> None:
        for item in owner.get(collection["path"], []):
            status = item.get("status", inherited)
            if status != "accepted":
                continue
            result.add(item["id"])
            for child in collection.get("nested", []):
                collect(item, child, status)

    for collection in profile["collections"]:
        collect(documents[collection["document"]], collection, default_status)
    return result


def validate_traceability_coverage(
    documents: dict[str, Any], profile: dict[str, Any]
) -> list[str]:
    expected = _accepted_traceable_ids(documents, profile)
    records = documents.get("traceability", {}).get("records", [])
    counts: dict[str, int] = {}
    for record in records:
        element_ref = record.get("elementRef")
        if isinstance(element_ref, str):
            counts[element_ref] = counts.get(element_ref, 0) + 1
    actual = set(counts)
    errors: list[str] = []
    if missing := sorted(expected - actual):
        errors.append(f"traceability coverage missing elements: {', '.join(missing)}")
    if unknown := sorted(actual - expected):
        errors.append(f"traceability coverage has unknown elements: {', '.join(unknown)}")
    if duplicates := sorted(key for key, count in counts.items() if count != 1):
        errors.append(f"traceability coverage has duplicate elements: {', '.join(duplicates)}")
    return errors


def validate_traceability_evidence_types(documents: dict[str, Any]) -> list[str]:
    evidence_record_ids = {
        record.get("id")
        for record in documents.get("evidence", {}).get("evidenceRecords", [])
        if isinstance(record, dict)
    }
    errors: list[str] = []
    for record_index, record in enumerate(
        documents.get("traceability", {}).get("records", [])
    ):
        for evidence_index, evidence_ref in enumerate(record.get("evidenceRefs", [])):
            if evidence_ref not in evidence_record_ids:
                errors.append(
                    f"traceability.yaml:records/{record_index}/evidenceRefs/"
                    f"{evidence_index}: expected EvidenceRecord, got {evidence_ref!r}"
                )
    return errors


def validate_traceability_identity(documents: dict[str, Any]) -> list[str]:
    manifest = documents.get("manifest", {})
    traceability = documents.get("traceability", {})
    errors: list[str] = []
    for field in ("ontologyId", "ontologyVersion"):
        actual = traceability.get(field)
        expected = manifest.get(field)
        if actual != expected:
            errors.append(
                f"traceability.yaml:{field}: {actual!r} does not match "
                f"manifest.yaml:{field} {expected!r}"
            )
    return errors


def validate_claim_confidences(documents: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    claims = documents.get("evidence", {}).get("discoveryClaims", [])
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        claim_id = claim.get("id", f"index {index}")
        try:
            mismatches = verify_claim_confidence(claim)
        except (TypeError, ValueError) as exc:
            errors.append(
                f"evidence.yaml:discoveryClaims/{index} ({claim_id}): {exc}"
            )
            continue
        errors.extend(
            f"evidence.yaml:discoveryClaims/{index} ({claim_id}): {message}"
            for message in mismatches
        )
    return errors


def validate_claim_evidence_types(documents: dict[str, Any]) -> list[str]:
    evidence_record_ids = {
        record.get("id")
        for record in documents.get("evidence", {}).get("evidenceRecords", [])
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    errors: list[str] = []
    for claim_index, claim in enumerate(
        documents.get("evidence", {}).get("discoveryClaims", [])
    ):
        if not isinstance(claim, dict):
            continue
        for field in ("evidenceRefs", "counterEvidenceRefs"):
            for ref_index, reference in enumerate(claim.get(field, [])):
                if reference not in evidence_record_ids:
                    errors.append(
                        f"evidence.yaml:discoveryClaims/{claim_index}/{field}/"
                        f"{ref_index}: expected EvidenceRecord, got {reference!r}"
                    )
        rationale = claim.get("confidenceRationale", {})
        if isinstance(rationale, dict):
            for dimension, detail in rationale.items():
                if not isinstance(detail, dict):
                    continue
                for ref_index, reference in enumerate(detail.get("evidenceRefs", [])):
                    if reference not in evidence_record_ids:
                        errors.append(
                            f"evidence.yaml:discoveryClaims/{claim_index}/"
                            f"confidenceRationale/{dimension}/evidenceRefs/{ref_index}: "
                            f"expected EvidenceRecord, got {reference!r}"
                        )
    return errors


def validate_discovery_bundle(
    evidence_graph: Any,
    claims_document: Any,
    schema_path: Path,
) -> list[str]:
    errors: list[str] = []
    try:
        schema = load_structured(schema_path)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return [f"schema: cannot load explicit schema path: {exc}"]
    if not isinstance(schema, dict):
        return ["schema: explicit schema root must be an object"]
    for label, document, definition in (
        ("evidenceGraph", evidence_graph, "evidenceGraph"),
        ("discoveryClaimsDocument", claims_document, "discoveryClaimsDocument"),
    ):
        selected = {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
        validator = Draft202012Validator(selected, format_checker=FormatChecker())
        errors.extend(
            f"{label}/{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in sorted(
                validator.iter_errors(document),
                key=lambda item: tuple(str(part) for part in item.absolute_path),
            )
        )
    if errors:
        return errors
    observation_ids_list = [item["id"] for item in evidence_graph["observations"]]
    claim_ids_list = [item["id"] for item in claims_document["claims"]]
    observation_ids = set(observation_ids_list)
    claim_ids = set(claim_ids_list)
    if evidence_graph["ontologyId"] != claims_document["ontologyId"]:
        errors.append(
            "ontologyId mismatch: evidenceGraph and discoveryClaimsDocument must match"
        )
    for identifier in sorted({item for item in observation_ids if observation_ids_list.count(item) > 1}):
        errors.append(f"duplicate EvidenceObservation ID: {identifier!r}")
    for identifier in sorted({item for item in claim_ids if claim_ids_list.count(item) > 1}):
        errors.append(f"duplicate DiscoveryClaim ID: {identifier!r}")
    for identifier in sorted(observation_ids & claim_ids):
        errors.append(f"ID collision between evidence and claim: {identifier!r}")
    for claim_index, claim in enumerate(claims_document.get("claims", [])):
        if not isinstance(claim, dict):
            continue
        errors.extend(
            f"claims/{claim_index}: {message}"
            for message in verify_claim_confidence(claim)
        )
        for field in ("evidenceRefs", "counterEvidenceRefs"):
            for ref_index, reference in enumerate(claim.get(field, [])):
                if reference not in observation_ids:
                    errors.append(
                        f"claims/{claim_index}/{field}/{ref_index}: expected "
                        f"EvidenceObservation ID, got {reference!r}"
                    )
        rationale = claim.get("confidenceRationale", {})
        if isinstance(rationale, dict):
            for dimension, detail in rationale.items():
                if not isinstance(detail, dict):
                    continue
                for ref_index, reference in enumerate(detail.get("evidenceRefs", [])):
                    if reference not in observation_ids:
                        errors.append(
                            f"claims/{claim_index}/confidenceRationale/{dimension}/"
                            f"evidenceRefs/{ref_index}: expected EvidenceObservation ID, "
                            f"got {reference!r}"
                        )
    return errors


def validate_adjudication(
    evidence_graph: Any,
    claims_document: Any,
    adjudication: Any,
    schema_path: Path,
) -> list[str]:
    """Validate the immutable-claim to human-decision boundary."""
    errors = validate_discovery_bundle(evidence_graph, claims_document, schema_path)
    try:
        schema = load_structured(schema_path)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return errors + [f"schema: cannot load explicit schema path: {exc}"]
    selected = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/adjudicationDocument",
    }
    validator = Draft202012Validator(selected, format_checker=FormatChecker())
    errors.extend(
        f"adjudication/{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in sorted(
            validator.iter_errors(adjudication),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
    )
    if errors or not isinstance(adjudication, dict):
        return errors
    if adjudication.get("ontologyId") != claims_document.get("ontologyId"):
        errors.append("adjudication/ontologyId: must match discovery claims ontologyId")
    claim_ids = {
        item.get("id") for item in claims_document.get("claims", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    observation_ids = {
        item.get("id") for item in evidence_graph.get("observations", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    counts = Counter(
        item.get("claimRef") for item in adjudication.get("decisions", [])
        if isinstance(item, dict) and isinstance(item.get("claimRef"), str)
    )
    if missing := sorted(claim_ids - set(counts)):
        errors.append(f"adjudication/decisions: missing claim decisions: {', '.join(missing)}")
    if unknown := sorted(set(counts) - claim_ids):
        errors.append(f"adjudication/decisions: unknown claim references: {', '.join(unknown)}")
    if duplicates := sorted(identifier for identifier, count in counts.items() if count != 1):
        errors.append(f"adjudication/decisions: duplicate claim decisions: {', '.join(duplicates)}")
    for index, decision in enumerate(adjudication.get("decisions", [])):
        if not isinstance(decision, dict):
            continue
        for reference in decision.get("evidenceRefs", []):
            if reference not in observation_ids:
                errors.append(
                    f"adjudication/decisions/{index}/evidenceRefs: unknown "
                    f"EvidenceObservation ID {reference!r}"
                )
    return sorted(errors)


def validate_documentation_refs(
    documents: dict[str, Any], project_root: Path
) -> list[str]:
    root = project_root.resolve()
    records = documents.get("traceability", {}).get("records", [])
    errors: list[str] = []
    anchor_pattern = re.compile(r'<a\s+id=["\']([a-z0-9]+(?:-[a-z0-9]+)*)["\']\s*></a>')
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        reference = record.get("documentationRef")
        location = f"traceability.yaml:records/{index}/documentationRef"
        if not isinstance(reference, str):
            errors.append(f"{location}: must be a project-relative Markdown path plus #anchor")
            continue
        path_text = reference.rsplit("#", maxsplit=1)[0]
        relative_path = Path(path_text)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(f"{location}: path escapes project root: {path_text!r}")
            continue
        if "#" not in reference:
            errors.append(f"{location}: must be a project-relative Markdown path plus #anchor")
            continue
        _, anchor = reference.rsplit("#", maxsplit=1)
        target = (root / relative_path).resolve()
        if not target.is_relative_to(root):
            errors.append(f"{location}: path escapes project root: {path_text!r}")
            continue
        if not target.is_file():
            errors.append(f"{location}: file does not exist: {path_text!r}")
            continue
        try:
            anchors = set(anchor_pattern.findall(target.read_text(encoding="utf-8")))
        except (OSError, UnicodeError) as exc:
            errors.append(f"{location}: cannot read documentation file: {exc}")
            continue
        if anchor not in anchors:
            errors.append(f"{location}: anchor does not exist: {anchor!r}")
    return errors


def validate_references(documents: dict[str, Any]) -> list[str]:
    id_locations: dict[str, list[str]] = {}
    for document_name, document in documents.items():
        for path, key, child in _walk(document):
            if key == "id" and isinstance(child, str):
                id_locations.setdefault(child, []).append(
                    f"{document_name}:{'/'.join(path)}"
                )
    declared_ids = set(id_locations)
    errors: list[str] = []
    for declared_id, locations in id_locations.items():
        if len(locations) > 1:
            errors.append(
                f"duplicate id {declared_id!r} declared at {', '.join(sorted(locations))}"
            )
    for document_name, document in documents.items():
        for path, key, child in _walk(document):
            references: list[str] = []
            if key.endswith("Ref") and isinstance(child, str):
                references = [child]
            elif key.endswith("Refs") and isinstance(child, list):
                references = [item for item in child if isinstance(item, str)]
            for reference in references:
                if reference not in declared_ids and not _is_external_ref(reference):
                    errors.append(
                        f"{document_name}:{'/'.join(path)}: unknown reference {reference!r}"
                    )
    return sorted(errors)


def calculate_digest(package_dir: Path) -> str:
    digest = hashlib.sha256()
    for definition, filename in sorted(DOCUMENTS.items(), key=lambda item: item[1]):
        if definition == "manifest":
            continue
        document = load_structured(package_dir / filename)
        if definition == "traceability":
            document = dict(document)
            document.pop("sourceDigest", None)
        canonical = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest.update(filename.encode("utf-8"))
        digest.update(b"\n")
        digest.update(canonical.encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def validate_package(package_dir: Path, schema_path: Path) -> list[str]:
    errors: list[str] = []
    documents: dict[str, Any] = {}
    try:
        schema = load_structured(schema_path)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return [f"<schema>: cannot load schema: {exc}"]
    profile, profile_errors = validate_traceability_profile(schema)
    errors.extend(profile_errors)
    package_root = package_dir.resolve()
    for definition, filename in DOCUMENTS.items():
        path = package_dir / filename
        if path.is_symlink():
            errors.append(f"{filename}: symlinked package documents are forbidden")
            continue
        if not path.is_file():
            errors.append(f"{filename}: missing required document")
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(package_root):
            errors.append(f"{filename}: package document escapes package root")
            continue
        try:
            documents[definition] = load_structured(path)
            errors.extend(
                f"{filename}:{error}"
                for error in validate_document(path, schema_path, definition)
            )
        except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
            errors.append(f"{filename}: cannot load document: {exc}")

    traceability = documents.get("traceability")
    if isinstance(traceability, dict):
        project_root = schema_path.resolve().parents[2]
        errors.extend(validate_documentation_refs(documents, project_root))
    manifest = documents.get("manifest")
    if isinstance(manifest, dict) and isinstance(traceability, dict):
        errors.extend(validate_traceability_identity(documents))
    errors.extend(validate_claim_confidences(documents))
    errors.extend(validate_claim_evidence_types(documents))

    if errors:
        return sorted(errors)

    errors.extend(validate_references(documents))
    if profile is not None:
        errors.extend(validate_traceability_coverage(documents, profile))
    errors.extend(validate_traceability_evidence_types(documents))
    if all(definition in documents for definition in DOCUMENTS):
        expected = calculate_digest(package_dir)
        actual = documents["manifest"].get("contentDigest")
        if actual != expected:
            errors.append(f"manifest.yaml:contentDigest: expected {expected}, actual {actual}")
        traceability_digest = documents["traceability"].get("sourceDigest")
        if traceability_digest != expected:
            errors.append(
                "traceability.yaml:sourceDigest: "
                f"expected {expected}, actual {traceability_digest}"
            )
    return sorted(errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an ontology package")
    parser.add_argument("package_dir", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).parents[1] / "spec/v1/ontology-package.schema.json",
    )
    args = parser.parse_args(argv)
    errors = validate_package(args.package_dir, args.schema)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Valid ontology package: {args.package_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
