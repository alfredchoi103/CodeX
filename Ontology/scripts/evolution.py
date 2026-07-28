from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from scripts.validate_package import DOCUMENTS, load_structured


_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_IMPACT = {"patch": 0, "minor": 1, "major": 2}
_SCHEMA_PATH = Path(__file__).parents[1] / "spec/v1/ontology-package.schema.json"
_OPERATION_IMPACT = {
    "metadata": "patch",
    "add": "minor",
    "rename": "major",
    "retype": "major",
    "split": "major",
    "merge": "major",
    "relink": "major",
    "supersede": "major",
    "retract": "major",
}
_CORRECTION_OPERATIONS = frozenset(
    {"rename", "retype", "split", "merge", "relink", "supersede", "retract"}
)


def _valid_alias_proof(change: dict[str, Any]) -> bool:
    proof = change.get("aliasProof")
    original = change.get("originalDefinition")
    updated = change.get("newDefinition")
    diff_paths = _definition_diff_paths(original, updated)
    return (
        change.get("operation") == "rename"
        and isinstance(original, dict)
        and isinstance(updated, dict)
        and isinstance(original.get("id"), str)
        and original.get("id") == updated.get("id")
        and bool(diff_paths)
        and all(path and path[0] in {"label", "name", "descriptions", "aliases"} for path in diff_paths)
        and isinstance(proof, dict)
        and proof.get("stableIdPreserved") is True
        and proof.get("consumerIdentifiersUnchanged") is True
        and isinstance(proof.get("evidenceRefs"), list)
        and bool(proof["evidenceRefs"])
        and all(isinstance(item, str) and item for item in proof["evidenceRefs"])
    )


def _definition_diff_paths(
    original: Any, updated: Any, path: tuple[str, ...] = ()
) -> set[tuple[str, ...]]:
    if isinstance(original, dict) and isinstance(updated, dict):
        paths: set[tuple[str, ...]] = set()
        for key in sorted(set(original) | set(updated)):
            if key not in original or key not in updated:
                paths.add(path + (str(key),))
            else:
                paths.update(
                    _definition_diff_paths(original[key], updated[key], path + (str(key),))
                )
        return paths
    return set() if original == updated else {path}


def parse_semver(value: str) -> tuple[int, int, int]:
    """Parse the project's strict three-number SemVer core."""
    if not isinstance(value, str) or not (match := _SEMVER.fullmatch(value)):
        raise ValueError(f"invalid SemVer core: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def classify_change(changes: list[dict[str, Any]]) -> str:
    """Return the greatest required impact; an empty release is a patch."""
    result = "patch"
    for change in changes:
        operation = change.get("operation")
        if operation not in _OPERATION_IMPACT:
            raise ValueError(f"unknown correction operation: {operation!r}")
        operation_impact = (
            "minor" if operation == "rename" and _valid_alias_proof(change)
            else _OPERATION_IMPACT[operation]
        )
        explicit = change.get("compatibility", operation_impact)
        if explicit not in _IMPACT:
            raise ValueError(f"unknown compatibility impact: {explicit!r}")
        candidate = max((operation_impact, explicit), key=_IMPACT.__getitem__)
        if _IMPACT[candidate] > _IMPACT[result]:
            result = candidate
    return result


def required_bump(changes: list[dict[str, Any]]) -> str:
    return classify_change(changes)


def validate_version_bump(before: str, after: str, required: str) -> list[str]:
    if required not in _IMPACT:
        return [f"version: unknown required bump {required!r}"]
    try:
        old = parse_semver(before)
        new = parse_semver(after)
    except ValueError as exc:
        return [f"version: {exc}"]
    if new <= old:
        return [f"version: {after} must be greater than {before}"]
    expected = {
        "patch": (old[0], old[1], old[2] + 1),
        "minor": (old[0], old[1] + 1, 0),
        "major": (old[0] + 1, 0, 0),
    }[required]
    if new != expected:
        expected_text = ".".join(str(part) for part in expected)
        return [
            f"version: {required} change from {before} requires {expected_text}, got {after}"
        ]
    return []


_COLLECTIONS: dict[str, tuple[tuple[str, str | None], ...]] = {
    "semantics": (
        ("objectTypes", "properties"),
        ("links", None),
        ("interfaces", None),
        ("invariants", None),
        ("businessTerms", None),
    ),
    "kinetics": (
        ("actions", None),
        ("queries", None),
        ("stateMachines", "states"),
        ("domainEvents", None),
    ),
    "policies": (
        ("authorizationPolicies", None),
        ("auditPolicies", None),
        ("qualityPolicies", None),
        ("compliancePolicies", None),
    ),
}


def collect_accepted_stable_ids(documents: dict[str, Any]) -> set[str]:
    """Collect accepted semantic/kinetic/policy IDs with lifecycle inheritance."""
    inherited = documents.get("manifest", {}).get("status")
    result: set[str] = set()
    for document_name, collections in _COLLECTIONS.items():
        document = documents.get(document_name, {})
        for collection_name, nested_name in collections:
            for item in document.get(collection_name, []):
                status = item.get("status", inherited)
                if status != "accepted":
                    continue
                if isinstance(item.get("id"), str):
                    result.add(item["id"])
                if nested_name:
                    for child in item.get(nested_name, []):
                        if child.get("status", status) == "accepted" and isinstance(
                            child.get("id"), str
                        ):
                            result.add(child["id"])
    return result


def _refs(entry: dict[str, Any], singular: str, plural: str) -> set[str]:
    values: set[str] = set()
    if isinstance(entry.get(singular), str):
        values.add(entry[singular])
    values.update(value for value in entry.get(plural, []) if isinstance(value, str))
    return values


def validate_lineage(
    old_ids: set[str],
    new_ids: set[str],
    changes: list[dict[str, Any]],
    lineage: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    covered: set[str] = set()
    normalized_lineage: list[tuple[str, frozenset[str], frozenset[str]]] = []
    for index, entry in enumerate(lineage):
        operation = entry.get("operation")
        predecessors = _refs(entry, "predecessorRef", "predecessorRefs")
        successors = _refs(entry, "successorRef", "successorRefs")
        if operation not in _CORRECTION_OPERATIONS:
            errors.append(f"lineage/{index}/operation: unknown correction operation {operation!r}")
        if not predecessors:
            errors.append(f"lineage/{index}/predecessorRefs: must be non-empty")
        if operation == "retract":
            if successors:
                errors.append(f"lineage/{index}/successorRefs: retract must be empty")
        elif not successors:
            errors.append(f"lineage/{index}/successorRefs: must be non-empty")
        normalized_lineage.append(
            (str(operation), frozenset(predecessors), frozenset(successors))
        )
        covered.update(predecessors)
        for predecessor in sorted(predecessors - old_ids):
            errors.append(f"lineage/{index}: unknown predecessor {predecessor!r}")
        for successor in sorted(successors - new_ids):
            errors.append(f"lineage/{index}: unknown successor {successor!r}")
    lineage_counts = Counter(normalized_lineage)
    for key, count in lineage_counts.items():
        if count > 1:
            errors.append(f"lineage: duplicate lineage entry {key!r}")
    change_keys: list[tuple[str, frozenset[str], frozenset[str]]] = []
    for index, change in enumerate(changes):
        operation = change.get("operation")
        predecessors = _refs(change, "predecessorRef", "predecessorRefs")
        successors = _refs(change, "successorRef", "successorRefs")
        if operation == "rename" and predecessors != successors:
            errors.append(
                f"changes/{index}: rename must preserve the same stable ID"
            )
        if operation == "split" and (len(predecessors) != 1 or len(successors) < 2):
            errors.append(
                f"changes/{index}: split requires one predecessor and multiple successors"
            )
        if operation == "merge" and (len(predecessors) < 2 or len(successors) != 1):
            errors.append(
                f"changes/{index}: merge requires multiple predecessors and one successor"
            )
        key = (str(operation), frozenset(predecessors), frozenset(successors))
        if operation in _CORRECTION_OPERATIONS:
            change_keys.append(key)
        if operation in _CORRECTION_OPERATIONS and lineage_counts[key] == 0:
            errors.append(
                f"changes/{index}: {operation} requires matching lineage "
                "predecessor/successor edges"
            )
    change_counts = Counter(change_keys)
    for key in sorted(set(change_counts) | set(lineage_counts), key=repr):
        if change_counts[key] != lineage_counts[key]:
            errors.append(
                f"lineage: correction changes and lineage must match one-to-one for {key!r}"
            )
    for index, key in enumerate(normalized_lineage):
        if change_counts[key] == 0:
            errors.append(
                f"lineage/{index}: correction lineage has no matching correction change"
            )
    graph: dict[str, set[str]] = {}
    for operation, predecessors, successors in normalized_lineage:
        for predecessor in predecessors:
            for successor in successors:
                if operation == "rename" and predecessor == successor:
                    continue
                graph.setdefault(predecessor, set()).add(successor)
    visiting: set[str] = set()
    visited: set[str] = set()

    def has_cycle(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(has_cycle(child) for child in graph.get(node, set())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    if any(has_cycle(node) for node in sorted(graph)):
        errors.append("lineage: directed predecessor/successor graph contains a cycle")
    for identifier in sorted(old_ids - new_ids - covered):
        errors.append(
            f"lineage: accepted element {identifier!r} disappeared without successor or retract"
        )
    return errors


_BREAKING_FIELDS = (
    "originalDefinition",
    "newDefinition",
    "impactAnalysis",
    "migrationStrategy",
    "backfill",
    "rollback",
    "compatibilityWindow",
    "acceptanceEvidence",
    "dualRead",
    "dualWrite",
)
_IMPACT_AREAS = (
    "data",
    "api",
    "action",
    "query",
    "policy",
    "document",
    "audit",
    "consumers",
)


def validate_migration(migration: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("fromVersion", "toVersion", "changes", "lineage"):
        if field not in migration:
            errors.append(f"{field}: required field is missing")
    changes = migration.get("changes", [])
    if not isinstance(changes, list):
        return errors + ["changes: must be an array"]
    for index, change in enumerate(changes):
        prefix = f"changes/{index}"
        operation = change.get("operation")
        compatibility = change.get("compatibility")
        required_fields = (
            "id", "operation", "compatibility", "predecessorRefs", "successorRefs",
            "originalDefinition", "newDefinition", "errorCause", "evidenceRefs",
            "impactAnalysis", "migrationStrategy", "backfill", "rollback",
            "compatibilityWindow", "dualRead", "dualWrite", "acceptanceEvidence",
        )
        for field in required_fields:
            if field not in change:
                errors.append(f"{prefix}/{field}: required field is missing")
        if operation in _OPERATION_IMPACT and compatibility in _IMPACT:
            minimum = (
                "minor" if operation == "rename" and _valid_alias_proof(change)
                else _OPERATION_IMPACT[operation]
            )
            if _IMPACT[compatibility] < _IMPACT[minimum]:
                errors.append(
                    f"{prefix}/compatibility: cannot understate {operation} impact"
                )
        if compatibility == "major" or operation in _CORRECTION_OPERATIONS:
            for field in _BREAKING_FIELDS:
                if field not in change or change.get(field) is None:
                    errors.append(f"{prefix}/{field}: required for a breaking change")
        if operation == "retract":
            for field in ("errorCause", "evidenceRefs", "impactAnalysis"):
                if not change.get(field):
                    errors.append(f"{prefix}/{field}: required for retract")
        impact = change.get("impactAnalysis")
        if isinstance(impact, dict):
            for area in _IMPACT_AREAS:
                if area not in impact:
                    errors.append(f"{prefix}/impactAnalysis/{area}: required impact area")
        for mode in ("dualRead", "dualWrite"):
            value = change.get(mode)
            if isinstance(value, dict):
                allowed = {"enabled", "description"}
                if mode == "dualWrite":
                    allowed.update(
                        {"idempotencyKey", "ordering", "conflictAuthority", "stopConditions"}
                    )
                unknown = sorted(set(value) - allowed)
                for field in unknown:
                    errors.append(f"{prefix}/{mode}/{field}: unknown field")
                if not isinstance(value.get("enabled"), bool):
                    errors.append(f"{prefix}/{mode}/enabled: must be boolean")
                if not isinstance(value.get("description"), str) or not value.get("description"):
                    errors.append(f"{prefix}/{mode}/description: must be non-empty")
        if "aliasProof" in change:
            proof = change.get("aliasProof")
            if not isinstance(proof, dict):
                errors.append(f"{prefix}/aliasProof: must be an object")
            else:
                for field in sorted(set(proof) - {"stableIdPreserved", "consumerIdentifiersUnchanged", "evidenceRefs"}):
                    errors.append(f"{prefix}/aliasProof/{field}: unknown field")
                if not _valid_alias_proof(change):
                    errors.append(
                        f"{prefix}/aliasProof: rename alias exception requires both true "
                        "flags and non-empty evidenceRefs"
                    )
                    if operation == "rename" and compatibility == "minor":
                        errors.append(
                            f"{prefix}/compatibility: misclassified alias changes "
                            "non-display semantics or has no real rename diff"
                        )
        rollback = change.get("rollback")
        if not isinstance(rollback, dict):
            errors.append(f"{prefix}/rollback: must be an operational rollback object")
        else:
            for field in ("procedure", "triggerConditions", "verificationSteps"):
                values = rollback.get(field)
                if not isinstance(values, list) or not values or not all(
                    isinstance(value, str) and value for value in values
                ):
                    errors.append(f"{prefix}/rollback/{field}: must be a non-empty string array")
        dual_write = change.get("dualWrite")
        if isinstance(dual_write, dict) and dual_write.get("enabled") is True:
            for field in ("idempotencyKey", "ordering", "conflictAuthority"):
                if not isinstance(dual_write.get(field), str) or not dual_write.get(field):
                    errors.append(f"{prefix}/dualWrite/{field}: required when enabled")
            stop_conditions = dual_write.get("stopConditions")
            if not isinstance(stop_conditions, list) or not stop_conditions or not all(
                isinstance(value, str) and value for value in stop_conditions
            ):
                errors.append(
                    f"{prefix}/dualWrite/stopConditions: non-empty strings required when enabled"
                )
            if "temporary-dual-write" not in change.get("migrationStrategy", []):
                errors.append(
                    f"{prefix}/migrationStrategy: enabled dualWrite requires temporary-dual-write"
                )
    return errors


def validate_package_migrations(migrations: dict[str, Any]) -> list[str]:
    """Validate in-package changes without requiring a cross-release version pair."""
    changes = migrations.get("changes", [])
    lineage = migrations.get("lineage", [])
    if not changes and not lineage:
        return []
    adapted = {
        "fromVersion": migrations.get("version"),
        "toVersion": migrations.get("version"),
        "changes": changes,
        "lineage": lineage,
    }
    errors = validate_migration(adapted)
    old_ids = {
        reference
        for change in changes
        for reference in change.get("predecessorRefs", [])
        if isinstance(reference, str)
    }
    new_ids = {
        reference
        for change in changes
        for reference in change.get("successorRefs", [])
        if isinstance(reference, str)
    }
    errors.extend(validate_lineage(old_ids, new_ids, changes, lineage))
    return sorted(set(errors))


def _load_package(value: Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"manifest": value}
    return {
        definition: load_structured(value / filename)
        for definition, filename in DOCUMENTS.items()
    }


def _collect_element_lifecycles(documents: dict[str, Any]) -> dict[str, str | None]:
    inherited = documents.get("manifest", {}).get("status")
    result: dict[str, str | None] = {}
    for document_name, collections in _COLLECTIONS.items():
        document = documents.get(document_name, {})
        for collection_name, nested_name in collections:
            for item in document.get(collection_name, []):
                if not isinstance(item, dict):
                    continue
                status = item.get("status", inherited)
                if isinstance(item.get("id"), str):
                    result[item["id"]] = status
                if nested_name:
                    for child in item.get(nested_name, []):
                        if isinstance(child, dict) and isinstance(child.get("id"), str):
                            result[child["id"]] = child.get("status", status)
    return result


def _collect_profile_definitions(
    documents: dict[str, Any], schema: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Index only ID-bearing elements declared by the schema traceability profile."""
    result: dict[str, dict[str, Any]] = {}

    def collect(owner: dict[str, Any], collection: dict[str, Any]) -> None:
        items = owner.get(collection.get("path"), [])
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id")
            if isinstance(identifier, str):
                result[identifier] = item
            for nested in collection.get("nested", []):
                if isinstance(nested, dict):
                    collect(item, nested)

    profile = schema.get("x-traceability-profile", {})
    for collection in profile.get("collections", []):
        if not isinstance(collection, dict):
            continue
        document = documents.get(collection.get("document"), {})
        if isinstance(document, dict):
            collect(document, collection)
    return result


def validate_evolution(
    previous: Path | dict[str, Any],
    current: Path | dict[str, Any],
    migration: Path | dict[str, Any],
) -> list[str]:
    old_documents = _load_package(previous)
    new_documents = _load_package(current)
    migration_document = load_structured(migration) if isinstance(migration, Path) else migration
    old_manifest = old_documents["manifest"]
    new_manifest = new_documents["manifest"]
    errors: list[str] = []
    schema = load_structured(_SCHEMA_PATH)
    selected_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/evolutionMigration",
    }
    validator = Draft202012Validator(selected_schema, format_checker=FormatChecker())
    schema_errors = [
        "migration.yaml:"
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in sorted(
            validator.iter_errors(migration_document),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
    ]
    if schema_errors:
        return sorted(set(schema_errors))
    if old_manifest.get("ontologyId") != new_manifest.get("ontologyId"):
        errors.append("manifest.yaml:ontologyId: evolution requires the same ontologyId")
    old_version = old_manifest.get("ontologyVersion")
    new_version = new_manifest.get("ontologyVersion")
    if old_version == new_version and old_manifest.get("contentDigest") != new_manifest.get(
        "contentDigest"
    ):
        errors.append(
            "manifest.yaml:contentDigest: published ontologyVersion is immutable; "
            "the same version cannot have a different contentDigest"
        )
    if old_version == new_version:
        errors.append(
            "version: same ontologyVersion is forbidden; a new release is required"
        )
    if migration_document.get("fromVersion") != old_version:
        errors.append("migration.yaml:fromVersion: does not match previous ontologyVersion")
    if migration_document.get("toVersion") != new_version:
        errors.append("migration.yaml:toVersion: does not match current ontologyVersion")
    errors.extend(validate_migration(migration_document))
    if old_version != new_version:
        try:
            bump = required_bump(migration_document.get("changes", []))
        except ValueError as exc:
            errors.append(f"migration.yaml:changes: {exc}")
        else:
            errors.extend(validate_version_bump(old_version, new_version, bump))
    if len(old_documents) > 1 and len(new_documents) > 1:
        old_ids = collect_accepted_stable_ids(old_documents)
        new_ids = collect_accepted_stable_ids(new_documents)
        target_lifecycles = _collect_element_lifecycles(new_documents)
        old_definitions = _collect_profile_definitions(old_documents, schema)
        new_definitions = _collect_profile_definitions(new_documents, schema)
        evidence_ids = {
            record.get("id")
            for documents in (old_documents, new_documents)
            for record in documents.get("evidence", {}).get("evidenceRecords", [])
            if isinstance(record, dict) and isinstance(record.get("id"), str)
        }
        for change_index, change in enumerate(migration_document.get("changes", [])):
            if change.get("operation") == "retract":
                for ref_index, reference in enumerate(change.get("predecessorRefs", [])):
                    if target_lifecycles.get(reference) != "retracted":
                        errors.append(
                            f"migration.yaml:changes/{change_index}/predecessorRefs/"
                            f"{ref_index}: retract predecessor {reference!r} must remain "
                            "in v2 with lifecycle retracted"
                        )
            if change.get("operation") == "rename" and "aliasProof" in change:
                predecessors = change.get("predecessorRefs", [])
                successors = change.get("successorRefs", [])
                if len(predecessors) == 1 and len(successors) == 1:
                    actual_old = old_definitions.get(predecessors[0])
                    actual_new = new_definitions.get(successors[0])
                    if change.get("originalDefinition") != actual_old:
                        errors.append(
                            f"migration.yaml:changes/{change_index}/originalDefinition: "
                            "does not match actual v1 definition"
                        )
                    if change.get("newDefinition") != actual_new:
                        errors.append(
                            f"migration.yaml:changes/{change_index}/newDefinition: "
                            "does not match actual v2 definition"
                        )
                    actual_change = dict(change)
                    actual_change["originalDefinition"] = actual_old
                    actual_change["newDefinition"] = actual_new
                    if not _valid_alias_proof(actual_change):
                        errors.append(
                            f"migration.yaml:changes/{change_index}/aliasProof: "
                            "actual package diff is not display-only; rename requires major"
                        )
                        errors.extend(validate_version_bump(old_version, new_version, "major"))
            for field, allowed, version_label in (
                ("predecessorRefs", old_ids, "v1"),
                ("successorRefs", new_ids, "v2"),
            ):
                for ref_index, reference in enumerate(change.get(field, [])):
                    if reference not in allowed:
                        errors.append(
                            f"migration.yaml:changes/{change_index}/{field}/{ref_index}: "
                            f"unknown {version_label} reference {reference!r}"
                        )
            for ref_index, reference in enumerate(change.get("evidenceRefs", [])):
                if reference not in evidence_ids:
                    errors.append(
                        f"migration.yaml:changes/{change_index}/evidenceRefs/{ref_index}: "
                        f"unknown cross-version evidence {reference!r}"
                    )
            proof = change.get("aliasProof")
            if isinstance(proof, dict):
                for ref_index, reference in enumerate(proof.get("evidenceRefs", [])):
                    if reference not in evidence_ids:
                        errors.append(
                            f"migration.yaml:changes/{change_index}/aliasProof/"
                            f"evidenceRefs/{ref_index}: unknown cross-version evidence "
                            f"{reference!r}"
                        )
        for lineage_index, entry in enumerate(migration_document.get("lineage", [])):
            if entry.get("operation") != "retract":
                continue
            for ref_index, reference in enumerate(entry.get("predecessorRefs", [])):
                if target_lifecycles.get(reference) != "retracted":
                    errors.append(
                        f"migration.yaml:lineage/{lineage_index}/predecessorRefs/"
                        f"{ref_index}: retract predecessor {reference!r} must remain "
                        "in v2 with lifecycle retracted"
                    )
        errors.extend(
            f"migration.yaml:{error}"
            for error in validate_lineage(
                old_ids,
                new_ids,
                migration_document.get("changes", []),
                migration_document.get("lineage", []),
            )
        )
    return sorted(set(errors))
