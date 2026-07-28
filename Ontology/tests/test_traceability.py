from collections import Counter
import json
from pathlib import Path
import re
import shutil

import pytest
import yaml

from scripts.validate_package import (
    DOCUMENTS,
    calculate_digest,
    load_structured,
    validate_document,
    validate_package,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "service-operations"
SCHEMA = ROOT / "spec" / "v1" / "ontology-package.schema.json"


def _write_yaml(path: Path, value: object) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _copy_package(tmp_path: Path) -> Path:
    destination = tmp_path / "service-operations"
    shutil.copytree(EXAMPLE, destination)
    return destination


def _synchronize_digests(package_dir: Path) -> None:
    digest = calculate_digest(package_dir)
    manifest = load_structured(package_dir / "manifest.yaml")
    traceability = load_structured(package_dir / "traceability.yaml")
    manifest["contentDigest"] = digest
    traceability["sourceDigest"] = digest
    _write_yaml(package_dir / "manifest.yaml", manifest)
    _write_yaml(package_dir / "traceability.yaml", traceability)


def _traceable_ids(package_dir: Path) -> set[str]:
    schema = load_structured(SCHEMA)
    profile = schema["x-traceability-profile"]
    manifest = load_structured(package_dir / "manifest.yaml")
    ids: set[str] = set()

    def collect(items: list[dict], nested: list[dict], inherited: str) -> None:
        for item in items:
            status = item.get("status", inherited)
            if status != "accepted":
                continue
            ids.add(item["id"])
            for child in nested:
                collect(item[child["path"]], child.get("nested", []), status)

    for collection in profile["collections"]:
        document = load_structured(package_dir / DOCUMENTS[collection["document"]])
        collect(
            document[collection["path"]],
            collection.get("nested", []),
            manifest["status"],
        )
    return ids


def _anchor_ids(markdown: str) -> set[str]:
    return set(re.findall(r'<a\s+id="([a-z0-9-]+)"\s*></a>', markdown))


def test_traceability_document_exists_and_matches_schema() -> None:
    path = EXAMPLE / "traceability.yaml"
    assert path.is_file()
    assert validate_document(path, SCHEMA, "traceability") == []


@pytest.mark.parametrize(
    "field", ["elementRef", "documentationRef", "evidenceRefs", "verificationRefs"]
)
def test_traceability_record_requires_core_fields(tmp_path: Path, field: str) -> None:
    document = load_structured(EXAMPLE / "traceability.yaml")
    del document["records"][0][field]
    candidate = tmp_path / "traceability.yaml"
    _write_yaml(candidate, document)

    errors = validate_document(candidate, SCHEMA, "traceability")

    assert any(field in error and "required" in error for error in errors)


def test_traceability_record_requires_runtime_or_extension_point(tmp_path: Path) -> None:
    document = load_structured(EXAMPLE / "traceability.yaml")
    record = document["records"][0]
    record.pop("runtimeRef", None)
    record.pop("extensionPointRef", None)
    candidate = tmp_path / "traceability.yaml"
    _write_yaml(candidate, document)

    errors = validate_document(candidate, SCHEMA, "traceability")

    assert errors
    assert any("not valid under any" in error for error in errors)


def test_traceability_record_is_closed_and_refs_are_nonempty(tmp_path: Path) -> None:
    document = load_structured(EXAMPLE / "traceability.yaml")
    document["records"][0]["invented"] = True
    document["records"][1]["evidenceRefs"] = []
    document["records"][2]["verificationRefs"] = []
    candidate = tmp_path / "traceability.yaml"
    _write_yaml(candidate, document)

    errors = validate_document(candidate, SCHEMA, "traceability")

    assert any("invented" in error and "unexpected" in error for error in errors)
    assert any("evidenceRefs" in error and "non-empty" in error for error in errors)
    assert any("verificationRefs" in error and "non-empty" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("documentationRef", "https://example.org/docs"),
        ("runtimeRef", "https://example.org/runtime"),
        ("extensionPointRef", "runtime://wrong-scheme"),
        ("verificationRefs", ["https://example.org/test"]),
    ],
)
def test_traceability_ref_schemes_are_constrained(
    tmp_path: Path, field: str, invalid: object
) -> None:
    document = load_structured(EXAMPLE / "traceability.yaml")
    record = document["records"][0]
    record[field] = invalid
    if field == "runtimeRef":
        record.pop("extensionPointRef", None)
    candidate = tmp_path / "traceability.yaml"
    _write_yaml(candidate, document)

    assert validate_document(candidate, SCHEMA, "traceability")


def test_manifest_registers_traceability_as_required_eighth_document() -> None:
    manifest = load_structured(EXAMPLE / "manifest.yaml")
    assert manifest["documents"]["traceability"] == "traceability.yaml"
    assert len(manifest["documents"]) == 7


def test_package_rejects_missing_traceability_document(tmp_path: Path) -> None:
    package_dir = _copy_package(tmp_path)
    (package_dir / "traceability.yaml").unlink()

    errors = validate_package(package_dir, SCHEMA)

    assert any("traceability.yaml" in error and "missing" in error for error in errors)


def test_traceability_exactly_covers_all_accepted_semantic_and_kinetic_elements() -> None:
    traceability = load_structured(EXAMPLE / "traceability.yaml")
    counts = Counter(record["elementRef"] for record in traceability["records"])
    expected = _traceable_ids(EXAMPLE)

    assert set(counts) == expected
    assert all(count == 1 for count in counts.values())
    assert len(expected) == 45
    assert not ({"submit.requestId", "event.requestId"} & set(counts)), (
        "Parameter and Effect are intentionally outside the v1 traceability coverage set"
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_package_rejects_inexact_traceability_coverage(
    tmp_path: Path, mutation: str
) -> None:
    package_dir = _copy_package(tmp_path)
    traceability = load_structured(package_dir / "traceability.yaml")
    if mutation == "missing":
        traceability["records"].pop()
    elif mutation == "duplicate":
        traceability["records"].append(dict(traceability["records"][0]))
    else:
        traceability["records"][0]["elementRef"] = "Unknown.traceableElement"
    _write_yaml(package_dir / "traceability.yaml", traceability)

    errors = validate_package(package_dir, SCHEMA)

    assert any("traceability coverage" in error for error in errors)


def test_traceability_documentation_paths_and_explicit_anchors_resolve() -> None:
    traceability = load_structured(EXAMPLE / "traceability.yaml")
    for record in traceability["records"]:
        relative_path, anchor = record["documentationRef"].split("#", maxsplit=1)
        target = ROOT / relative_path
        assert target.is_file(), record["documentationRef"]
        assert anchor in _anchor_ids(target.read_text(encoding="utf-8")), record[
            "documentationRef"
        ]


def test_example_uses_extension_points_without_claiming_runtime_implementation() -> None:
    traceability = load_structured(EXAMPLE / "traceability.yaml")
    assert all("extensionPointRef" in record for record in traceability["records"])
    assert all("runtimeRef" not in record for record in traceability["records"])


def test_traceability_internal_refs_resolve_but_external_refs_are_not_internal() -> None:
    assert validate_package(EXAMPLE, SCHEMA) == []


def test_digest_includes_traceability_records_but_normalizes_source_digest(
    tmp_path: Path,
) -> None:
    package_dir = _copy_package(tmp_path)
    original = calculate_digest(package_dir)
    traceability = load_structured(package_dir / "traceability.yaml")
    traceability["sourceDigest"] = "sha256:" + "0" * 64
    _write_yaml(package_dir / "traceability.yaml", traceability)
    assert calculate_digest(package_dir) == original

    traceability["records"][0]["verificationRefs"].append(
        "scenario://contract/trace-mutation"
    )
    _write_yaml(package_dir / "traceability.yaml", traceability)
    assert calculate_digest(package_dir) != original


def test_package_rejects_stale_traceability_source_digest(tmp_path: Path) -> None:
    package_dir = _copy_package(tmp_path)
    traceability = load_structured(package_dir / "traceability.yaml")
    traceability["sourceDigest"] = "sha256:" + "0" * 64
    _write_yaml(package_dir / "traceability.yaml", traceability)

    errors = validate_package(package_dir, SCHEMA)

    assert any("traceability.yaml:sourceDigest" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "different"),
    [
        ("ontologyId", "org.example.different-ontology"),
        ("ontologyVersion", "2.0.0"),
    ],
)
def test_package_rejects_traceability_identity_mismatch(
    tmp_path: Path, field: str, different: str
) -> None:
    package_dir = _copy_package(tmp_path)
    traceability = load_structured(package_dir / "traceability.yaml")
    traceability[field] = different
    _write_yaml(package_dir / "traceability.yaml", traceability)
    _synchronize_digests(package_dir)

    errors = validate_package(package_dir, SCHEMA)

    assert any(
        f"traceability.yaml:{field}" in error and "does not match manifest.yaml" in error
        for error in errors
    )


@pytest.mark.parametrize(
    "external_evidence", ["external:catalog-evidence", "runtime://evidence/source"]
)
def test_traceability_evidence_refs_must_be_internal_stable_ids(
    tmp_path: Path, external_evidence: str
) -> None:
    package_dir = _copy_package(tmp_path)
    traceability = load_structured(package_dir / "traceability.yaml")
    traceability["records"][0]["evidenceRefs"] = [external_evidence]
    _write_yaml(package_dir / "traceability.yaml", traceability)
    _synchronize_digests(package_dir)

    errors = validate_package(package_dir, SCHEMA)

    assert any("evidenceRefs" in error and external_evidence in error for error in errors)


def test_traceability_evidence_refs_must_point_to_evidence_records(
    tmp_path: Path,
) -> None:
    package_dir = _copy_package(tmp_path)
    traceability = load_structured(package_dir / "traceability.yaml")
    traceability["records"][0]["evidenceRefs"] = ["Party"]
    _write_yaml(package_dir / "traceability.yaml", traceability)
    _synchronize_digests(package_dir)

    errors = validate_package(package_dir, SCHEMA)

    assert any(
        "traceability.yaml:records/0/evidenceRefs/0" in error
        and "expected EvidenceRecord" in error
        and "Party" in error
        for error in errors
    )


@pytest.mark.parametrize(
    ("documentation_ref", "expected_error"),
    [
        ("docs/not-present.md#missing", "file does not exist"),
        ("docs/forward-engineering.md#not-present", "anchor does not exist"),
        (
            "../../docs/forward-engineering.md#semantic-modeling",
            "escapes project root",
        ),
        ("../../etc/passwd", "escapes project root"),
    ],
)
def test_package_rejects_unresolvable_or_unsafe_documentation_ref(
    tmp_path: Path, documentation_ref: str, expected_error: str
) -> None:
    package_dir = _copy_package(tmp_path)
    traceability = load_structured(package_dir / "traceability.yaml")
    traceability["records"][0]["documentationRef"] = documentation_ref
    _write_yaml(package_dir / "traceability.yaml", traceability)
    _synchronize_digests(package_dir)

    errors = validate_package(package_dir, SCHEMA)

    assert any(
        "traceability.yaml:records/0/documentationRef" in error
        and expected_error in error
        for error in errors
    )


@pytest.mark.parametrize("definition,filename", list(DOCUMENTS.items()))
def test_package_rejects_symlinked_documents_without_reading_targets(
    tmp_path: Path, definition: str, filename: str
) -> None:
    package_dir = _copy_package(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / filename
    target.write_bytes((package_dir / filename).read_bytes())
    (package_dir / filename).unlink()
    (package_dir / filename).symlink_to(target)

    errors = validate_package(package_dir, SCHEMA)

    assert any(f"{filename}: symlinked package documents are forbidden" in error for error in errors)


def test_documentation_ref_rejects_project_internal_symlink_to_external_file(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    package_dir = project / "examples" / "service-operations"
    shutil.copytree(EXAMPLE, package_dir)
    schema = project / "spec" / "v1" / "ontology-package.schema.json"
    schema.parent.mkdir(parents=True)
    shutil.copy2(SCHEMA, schema)
    external = tmp_path / "external.md"
    external.write_text(
        '<a id="semantic-modeling"></a>\n<a id="behavior-modeling"></a>\n',
        encoding="utf-8",
    )
    docs = project / "docs"
    docs.mkdir()
    (docs / "forward-engineering.md").symlink_to(external)

    errors = validate_package(package_dir, schema)

    assert any(
        "documentationRef" in error and "escapes project root" in error
        for error in errors
    )


def test_traceability_profile_is_schema_consistent_and_derives_example_coverage() -> None:
    schema = load_structured(SCHEMA)
    profile = schema["x-traceability-profile"]
    assert profile["version"] == "1.0"
    assert _traceable_ids(EXAMPLE) == {
        record["elementRef"]
        for record in load_structured(EXAMPLE / "traceability.yaml")["records"]
    }

    def check_collection(document_definition: str, collection: dict) -> None:
        owner = schema["$defs"][document_definition]
        item_ref = owner["properties"][collection["path"]]["items"]["$ref"]
        assert item_ref == f'#/$defs/{collection["definition"]}'
        target = schema["$defs"][collection["definition"]]
        assert target["properties"]["id"]["$ref"] == "#/$defs/stableId"
        for child in collection.get("nested", []):
            check_collection(collection["definition"], child)

    for collection in profile["collections"]:
        assert collection["document"] in DOCUMENTS
        check_collection(collection["document"], collection)


@pytest.mark.parametrize("mutation", ["missing", "invalid"])
def test_package_reports_invalid_traceability_profile_configuration(
    tmp_path: Path, mutation: str
) -> None:
    schema = load_structured(SCHEMA)
    if mutation == "missing":
        del schema["x-traceability-profile"]
    else:
        schema["x-traceability-profile"]["collections"][0]["definition"] = "linkType"
    candidate = tmp_path / "ontology-package.schema.json"
    _write_json(candidate, schema)

    errors = validate_package(EXAMPLE, candidate)

    assert any("traceability profile configuration" in error for error in errors)
