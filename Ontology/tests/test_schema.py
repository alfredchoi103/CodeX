from pathlib import Path
import shutil

import pytest
import yaml
from jsonschema import Draft202012Validator

from scripts.validate_package import (
    calculate_digest,
    load_structured,
    main as validate_main,
    validate_document,
    validate_package,
    validate_references,
)


ROOT = Path(__file__).parents[1]


def write_yaml(path: Path, document: object) -> None:
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def copy_example_package(tmp_path: Path) -> Path:
    package_dir = tmp_path / "service-operations"
    shutil.copytree(ROOT / "examples/service-operations", package_dir)
    return package_dir


def test_state_machine_requires_subject_ref(tmp_path: Path) -> None:
    kinetics = load_structured(ROOT / "examples/service-operations/kinetics.yaml")
    kinetics["stateMachines"][0].pop("subjectRef", None)
    candidate = tmp_path / "kinetics.yaml"
    write_yaml(candidate, kinetics)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "kinetics"
    )

    assert any("subjectRef" in error and "required property" in error for error in errors)


def test_yaml_loader_uses_core_boolean_semantics(tmp_path: Path) -> None:
    candidate = tmp_path / "values.yaml"
    candidate.write_text("default: ON\nenabled: true\n", encoding="utf-8")

    document = load_structured(candidate)

    assert document == {"default": "ON", "enabled": True}


def test_yaml_loader_rejects_unhashable_complex_keys_without_traceback(tmp_path: Path) -> None:
    candidate = tmp_path / "malformed.yaml"
    candidate.write_text("? [a, b]\n: value\n", encoding="utf-8")

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "manifest"
    )

    assert len(errors) == 1
    assert "cannot load document" in errors[0]
    assert "unhashable" in errors[0]


def test_yaml_loader_uses_yaml_1_2_core_scalars_without_global_pollution(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "scalars.yaml"
    candidate.write_text(
        "decimal: 012\n"
        "octal: 0o12\n"
        "date: 2026-07-27\n"
        "legacyBool: ON\n"
        "boolean: true\n"
        "float: 1.\n"
        "nothing: null\n",
        encoding="utf-8",
    )

    document = load_structured(candidate)

    assert document == {
        "decimal": 12,
        "octal": 10,
        "date": "2026-07-27",
        "legacyBool": "ON",
        "boolean": True,
        "float": 1.0,
        "nothing": None,
    }
    assert yaml.safe_load("value: ON") == {"value": True}


@pytest.mark.parametrize(
    "source,key",
    [
        ("name: first\nname: second\n", "name"),
        ("outer:\n  value: first\n  value: second\n", "value"),
    ],
)
def test_yaml_loader_rejects_duplicate_keys_at_any_depth(
    tmp_path: Path, source: str, key: str
) -> None:
    candidate = tmp_path / "duplicate.yaml"
    candidate.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match=rf"Duplicate key ['\"]{key}['\"]"):
        load_structured(candidate)


def test_duplicate_key_detection_preserves_yaml_merge_and_safe_loader(tmp_path: Path) -> None:
    candidate = tmp_path / "merge.yaml"
    candidate.write_text(
        "defaults: &defaults\n  enabled: true\n  label: inherited\n"
        "item:\n  <<: *defaults\n  label: override\n",
        encoding="utf-8",
    )

    assert load_structured(candidate)["item"] == {"enabled": True, "label": "override"}
    assert yaml.safe_load("name: first\nname: second\n") == {"name": "second"}


def test_validators_report_duplicate_keys_without_crashing(tmp_path: Path) -> None:
    package_dir = copy_example_package(tmp_path)
    manifest = package_dir / "manifest.yaml"
    manifest.write_text("ontologyId: duplicate\n" + manifest.read_text(encoding="utf-8"), encoding="utf-8")

    document_errors = validate_document(
        manifest, ROOT / "spec/v1/ontology-package.schema.json", "manifest"
    )
    package_errors = validate_package(
        package_dir, ROOT / "spec/v1/ontology-package.schema.json"
    )

    assert document_errors == ["manifest.yaml: cannot load document: Duplicate key 'ontologyId'"]
    assert any(error == "manifest.yaml: cannot load document: Duplicate key 'ontologyId'" for error in package_errors)


def test_validate_package_cli_does_not_claim_conformance_level(capsys) -> None:
    result = validate_main([
        str(ROOT / "examples/service-operations"),
        "--schema", str(ROOT / "spec/v1/ontology-package.schema.json"),
    ])

    assert result == 0
    assert "L3" not in capsys.readouterr().out


def test_on_property_default_remains_a_string(tmp_path: Path) -> None:
    document = load_structured(ROOT / "examples/service-operations/semantics.yaml")
    document["objectTypes"][0]["properties"][0]["default"] = "ON"
    candidate = tmp_path / "semantics.yaml"
    write_yaml(candidate, document)

    loaded = load_structured(candidate)

    assert loaded["objectTypes"][0]["properties"][0]["default"] == "ON"
    assert validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "semantics"
    ) == []


def test_package_schema_is_valid_draft_2020_12() -> None:
    schema = load_structured(ROOT / "spec/v1/ontology-package.schema.json")
    Draft202012Validator.check_schema(schema)


def test_validate_document_reports_non_object_schema_root(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("[]\n", encoding="utf-8")
    document_path = tmp_path / "document.yaml"
    document_path.write_text("value: example\n", encoding="utf-8")

    errors = validate_document(document_path, schema_path, "manifest")

    assert errors == ["<schema>: schema root must be an object"]


def test_service_operations_manifest_is_valid() -> None:
    errors = validate_document(
        ROOT / "examples/service-operations/manifest.yaml",
        ROOT / "spec/v1/ontology-package.schema.json",
        definition="manifest",
    )
    assert errors == []


@pytest.mark.parametrize(
    "definition,filename",
    [
        ("manifest", "manifest.yaml"),
        ("semantics", "semantics.yaml"),
        ("kinetics", "kinetics.yaml"),
        ("bindings", "bindings.yaml"),
        ("policies", "policies.yaml"),
        ("evidence", "evidence.yaml"),
        ("migrations", "migrations.yaml"),
    ],
)
def test_service_operations_documents_are_valid(
    definition: str, filename: str
) -> None:
    errors = validate_document(
        ROOT / "examples/service-operations" / filename,
        ROOT / "spec/v1/ontology-package.schema.json",
        definition=definition,
    )
    assert errors == []


@pytest.mark.parametrize("confidence", [0, 100])
def test_discovery_claim_confidence_accepts_integer_boundaries(
    tmp_path: Path, confidence: int
) -> None:
    document = load_structured(ROOT / "examples/service-operations/evidence.yaml")
    claim = valid_discovery_claim()
    claim["confidence"] = confidence
    document["discoveryClaims"] = [claim]
    candidate = tmp_path / "evidence.yaml"
    write_yaml(candidate, document)

    assert validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "evidence"
    ) == []


@pytest.mark.parametrize("confidence", [-1, 101, 50.5])
def test_discovery_claim_confidence_rejects_out_of_range_or_non_integer(
    tmp_path: Path, confidence: float
) -> None:
    document = load_structured(ROOT / "examples/service-operations/evidence.yaml")
    claim = valid_discovery_claim()
    claim["confidence"] = confidence
    document["discoveryClaims"] = [claim]
    candidate = tmp_path / "evidence.yaml"
    write_yaml(candidate, document)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "evidence"
    )

    assert any("confidence" in error for error in errors)


def valid_discovery_claim() -> dict[str, object]:
    return {
        "id": "claim.schemaContract",
        "label": "Schema contract claim",
        "statement": "The claim schema preserves authoritative projection fields.",
        "status": "proposed",
        "reasoningRules": ["rule.schemaContract"],
        "evidenceRefs": ["evidence.domain-model"],
        "counterEvidenceRefs": [],
        "counterEvidenceLevel": "none",
        "counterEvidenceAssessment": "No counter-evidence found.",
        "alternatives": ["The source may only describe a projection."],
        "confidenceDimensions": {
            "crossSourceAgreement": 90,
            "evidenceCoverage": 90,
            "runtimeSupport": 90,
            "semanticSpecificity": 90,
            "constraintConsistency": 90,
            "counterEvidenceAssessment": 90,
        },
        "confidenceRationale": {
            dimension: {
                "score": 90,
                "rationale": "Schema fixture rationale.",
                "evidenceRefs": ["evidence.domain-model"],
                "deductions": ["Schema fixture deduction."],
            }
            for dimension in (
                "crossSourceAgreement",
                "evidenceCoverage",
                "runtimeSupport",
                "semanticSpecificity",
                "constraintConsistency",
                "counterEvidenceAssessment",
            )
        },
        "confidence": 90,
        "grade": "A",
        "falsifiers": ["A reviewed source contradicts the claim."],
        "validationQuestions": ["Does the source preserve stable identity?"],
        "capabilityQuestions": ["Can the ontology explain the projection?"],
        "provenance": {
            "extractorVersion": "schema-test-1",
            "ruleSetVersion": "schema-rules-1",
            "generatedAt": "2026-07-27T10:00:00Z",
        },
    }


@pytest.mark.parametrize(
    "field", ["label", "grade", "falsifiers", "counterEvidenceAssessment"]
)
def test_discovery_claim_requires_authoritative_projection_fields(
    tmp_path: Path, field: str
) -> None:
    document = load_structured(ROOT / "examples/service-operations/evidence.yaml")
    claim = valid_discovery_claim()
    del claim[field]
    document["discoveryClaims"] = [claim]
    candidate = tmp_path / "evidence.yaml"
    write_yaml(candidate, document)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "evidence"
    )

    assert any(field in error and "required" in error for error in errors)


def test_discovery_claim_rejects_invalid_grade(tmp_path: Path) -> None:
    document = load_structured(ROOT / "examples/service-operations/evidence.yaml")
    claim = valid_discovery_claim()
    claim["grade"] = "E"
    document["discoveryClaims"] = [claim]
    candidate = tmp_path / "evidence.yaml"
    write_yaml(candidate, document)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "evidence"
    )

    assert any("grade" in error and "one of" in error for error in errors)


def test_discovery_claim_rejects_empty_falsifiers(tmp_path: Path) -> None:
    document = load_structured(ROOT / "examples/service-operations/evidence.yaml")
    claim = valid_discovery_claim()
    claim["falsifiers"] = []
    document["discoveryClaims"] = [claim]
    candidate = tmp_path / "evidence.yaml"
    write_yaml(candidate, document)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "evidence"
    )

    assert any("falsifiers" in error and "non-empty" in error for error in errors)


def test_object_type_requires_key(tmp_path: Path) -> None:
    document = load_structured(ROOT / "examples/service-operations/semantics.yaml")
    del document["objectTypes"][0]["key"]
    candidate = tmp_path / "semantics.yaml"
    write_yaml(candidate, document)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "semantics"
    )

    assert any("key" in error and "required" in error for error in errors)


def test_action_requires_an_effect(tmp_path: Path) -> None:
    document = load_structured(ROOT / "examples/service-operations/kinetics.yaml")
    document["actions"][0]["effects"] = []
    candidate = tmp_path / "kinetics.yaml"
    write_yaml(candidate, document)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "kinetics"
    )

    assert any("effects" in error and "non-empty" in error for error in errors)


def test_binding_requires_evidence_refs(tmp_path: Path) -> None:
    document = load_structured(ROOT / "examples/service-operations/bindings.yaml")
    del document["dataBindings"][0]["evidenceRefs"]
    candidate = tmp_path / "bindings.yaml"
    write_yaml(candidate, document)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "bindings"
    )

    assert any("evidenceRefs" in error and "required" in error for error in errors)


def test_package_rejects_unknown_link_endpoint(tmp_path: Path) -> None:
    package_dir = copy_example_package(tmp_path)
    semantics = load_structured(package_dir / "semantics.yaml")
    semantics["links"][0]["targetRef"] = "UnknownObject"
    write_yaml(package_dir / "semantics.yaml", semantics)

    errors = validate_package(
        package_dir, ROOT / "spec/v1/ontology-package.schema.json"
    )

    assert any("UnknownObject" in error and "targetRef" in error for error in errors)


def test_open_default_id_does_not_declare_an_ontology_id() -> None:
    documents = {
        "semantics": {
            "objectTypes": [
                {
                    "id": "Known",
                    "properties": [
                        {"id": "Known.value", "default": {"id": "Ghost"}}
                    ],
                }
            ],
            "links": [{"id": "link", "sourceRef": "Ghost", "targetRef": "Known"}],
        }
    }

    errors = validate_references(documents)

    assert any("sourceRef" in error and "Ghost" in error for error in errors)


def test_reference_like_key_inside_open_default_is_literal_payload() -> None:
    documents = {
        "semantics": {
            "objectTypes": [
                {
                    "id": "Known",
                    "properties": [
                        {
                            "id": "Known.value",
                            "default": {"customerRef": "literal-value"},
                        }
                    ],
                }
            ]
        }
    }

    assert validate_references(documents) == []


def test_descriptions_mapping_does_not_contribute_ids_or_references() -> None:
    documents = {
        "semantics": {
            "objectTypes": [
                {
                    "id": "Known",
                    "descriptions": {
                        "id": "Ghost",
                        "customerRef": "literal-value",
                    },
                }
            ],
            "links": [{"id": "link", "sourceRef": "Ghost", "targetRef": "Known"}],
        }
    }

    errors = validate_references(documents)

    assert any("sourceRef" in error and "Ghost" in error for error in errors)
    assert not any("customerRef" in error for error in errors)


def test_metadata_mapping_does_not_contribute_ids_or_references() -> None:
    documents = {
        "semantics": {
            "metadata": {"id": "MetadataGhost", "ownerRef": "literal-owner"},
            "objectTypes": [{"id": "Known"}],
            "links": [
                {"id": "link", "sourceRef": "MetadataGhost", "targetRef": "Known"}
            ],
        }
    }

    errors = validate_references(documents)

    assert any("sourceRef" in error and "MetadataGhost" in error for error in errors)
    assert not any("ownerRef" in error for error in errors)


def test_duplicate_property_ids_report_both_locations() -> None:
    documents = {
        "semantics": {
            "objectTypes": [
                {
                    "id": "Known",
                    "properties": [
                        {"id": "Known.duplicate"},
                        {"id": "Known.duplicate"},
                    ],
                }
            ]
        }
    }

    errors = validate_references(documents)

    duplicate = next(error for error in errors if "duplicate" in error)
    assert "objectTypes/0/properties/0/id" in duplicate
    assert "objectTypes/0/properties/1/id" in duplicate


def test_package_allows_explicit_external_policy_reference(tmp_path: Path) -> None:
    package_dir = copy_example_package(tmp_path)
    policies = load_structured(package_dir / "policies.yaml")
    policies["compliancePolicies"][0]["targetRefs"] = [
        "runtime://retention/service-operations"
    ]
    write_yaml(package_dir / "policies.yaml", policies)

    errors = validate_package(
        package_dir, ROOT / "spec/v1/ontology-package.schema.json"
    )

    assert not any("runtime://retention/service-operations" in error for error in errors)


@pytest.mark.parametrize(
    "external_ref", ["external:catalogItem", "runtime://component/x"]
)
def test_policy_accepts_well_formed_external_references(
    tmp_path: Path, external_ref: str
) -> None:
    policies = load_structured(ROOT / "examples/service-operations/policies.yaml")
    policies["compliancePolicies"][0]["targetRefs"] = [external_ref]
    candidate = tmp_path / "policies.yaml"
    write_yaml(candidate, policies)

    assert validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "policies"
    ) == []


def test_policy_rejects_malformed_external_uri(tmp_path: Path) -> None:
    policies = load_structured(ROOT / "examples/service-operations/policies.yaml")
    policies["compliancePolicies"][0]["targetRefs"] = [
        "http://bad external ref"
    ]
    candidate = tmp_path / "policies.yaml"
    write_yaml(candidate, policies)

    errors = validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "policies"
    )

    assert any("http://bad external ref" in error for error in errors)


def test_colon_stable_id_is_valid_and_resolves(tmp_path: Path) -> None:
    semantics = {
        "objectTypes": [
            {
                "id": "domain:Known",
                "label": "Known",
                "key": ["domain:Known.id"],
                "properties": [
                    {
                        "id": "domain:Known.id",
                        "label": "Identifier",
                        "valueType": {"kind": "primitive", "primitive": "string"},
                    }
                ],
            }
        ],
        "links": [
            {
                "id": "domain:selfLink",
                "label": "Self link",
                "sourceRef": "domain:Known",
                "targetRef": "domain:Known",
                "cardinality": "one-to-one",
            }
        ],
        "interfaces": [],
        "invariants": [],
        "businessTerms": [],
    }
    candidate = tmp_path / "semantics.yaml"
    write_yaml(candidate, semantics)

    assert validate_document(
        candidate, ROOT / "spec/v1/ontology-package.schema.json", "semantics"
    ) == []
    assert validate_references({"semantics": semantics}) == []


def test_missing_colon_stable_id_is_not_treated_as_external() -> None:
    documents = {
        "semantics": {
            "objectTypes": [{"id": "domain:Known"}],
            "links": [
                {
                    "id": "domain:link",
                    "sourceRef": "domain:Known",
                    "targetRef": "domain:Missing",
                }
            ],
        },
        "policies": {
            "targetRefs": ["external:catalogItem", "runtime://component/x"]
        },
    }

    errors = validate_references(documents)

    assert len(errors) == 1
    assert "domain:Missing" in errors[0]


def test_package_rejects_missing_required_document(tmp_path: Path) -> None:
    package_dir = copy_example_package(tmp_path)
    (package_dir / "policies.yaml").unlink()

    errors = validate_package(
        package_dir, ROOT / "spec/v1/ontology-package.schema.json"
    )

    assert any("policies.yaml" in error and "missing" in error for error in errors)


def test_package_returns_manifest_structure_errors_without_crashing(
    tmp_path: Path,
) -> None:
    package_dir = copy_example_package(tmp_path)
    write_yaml(package_dir / "manifest.yaml", ["not", "an", "object"])

    errors = validate_package(
        package_dir, ROOT / "spec/v1/ontology-package.schema.json"
    )

    assert isinstance(errors, list)
    assert any("manifest.yaml" in error and "object" in error for error in errors)


def test_package_rejects_digest_mismatch(tmp_path: Path) -> None:
    package_dir = copy_example_package(tmp_path)
    manifest = load_structured(package_dir / "manifest.yaml")
    manifest["contentDigest"] = "sha256:" + "0" * 64
    write_yaml(package_dir / "manifest.yaml", manifest)

    errors = validate_package(
        package_dir, ROOT / "spec/v1/ontology-package.schema.json"
    )

    assert any(
        "contentDigest" in error and "expected" in error and "actual" in error
        for error in errors
    )


def test_service_operations_package_is_valid() -> None:
    package_dir = ROOT / "examples/service-operations"
    assert calculate_digest(package_dir).startswith("sha256:")
    assert validate_package(
        package_dir, ROOT / "spec/v1/ontology-package.schema.json"
    ) == []


def test_digest_is_independent_of_mapping_key_order(tmp_path: Path) -> None:
    package_dir = copy_example_package(tmp_path)
    original = calculate_digest(package_dir)
    semantics = load_structured(package_dir / "semantics.yaml")
    reordered = dict(reversed(list(semantics.items())))
    write_yaml(package_dir / "semantics.yaml", reordered)

    assert calculate_digest(package_dir) == original


def test_digest_excludes_all_manifest_fields(tmp_path: Path) -> None:
    package_dir = copy_example_package(tmp_path)
    original = calculate_digest(package_dir)
    manifest = load_structured(package_dir / "manifest.yaml")
    manifest["status"] = "deprecated"
    manifest["owners"][0]["name"] = "Changed Owner"
    manifest["contentDigest"] = "sha256:" + "f" * 64
    write_yaml(package_dir / "manifest.yaml", manifest)

    assert calculate_digest(package_dir) == original


def test_manifest_rejects_missing_content_digest(tmp_path: Path) -> None:
    invalid = tmp_path / "manifest.yaml"
    invalid.write_text(
        "ontologyId: org.example.invalid\n"
        "ontologyVersion: 1.0.0\n"
        "specVersion: 1.0.0\n",
        encoding="utf-8",
    )
    errors = validate_document(
        invalid,
        ROOT / "spec/v1/ontology-package.schema.json",
        definition="manifest",
    )

    assert any("contentDigest" in error for error in errors)


@pytest.mark.parametrize("field", ["ontologyVersion", "specVersion"])
def test_manifest_rejects_numeric_prerelease_with_leading_zero(
    tmp_path: Path, field: str
) -> None:
    manifest = (ROOT / "examples/service-operations/manifest.yaml").read_text(
        encoding="utf-8"
    )
    invalid = tmp_path / "manifest.yaml"
    invalid.write_text(
        manifest.replace(f"{field}: 1.0.0", f"{field}: 1.0.0-01"),
        encoding="utf-8",
    )

    errors = validate_document(
        invalid,
        ROOT / "spec/v1/ontology-package.schema.json",
        definition="manifest",
    )

    assert any(field in error for error in errors)


def test_manifest_rejects_invalid_namespace_uri(tmp_path: Path) -> None:
    manifest = (ROOT / "examples/service-operations/manifest.yaml").read_text(
        encoding="utf-8"
    )
    invalid = tmp_path / "manifest.yaml"
    invalid.write_text(
        manifest.replace(
            "namespace: https://example.org/ontology/service-operations/",
            "namespace: not a uri",
        ),
        encoding="utf-8",
    )

    errors = validate_document(
        invalid,
        ROOT / "spec/v1/ontology-package.schema.json",
        definition="manifest",
    )

    assert any("namespace" in error or "uri" in error for error in errors)


@pytest.mark.parametrize(
    "version",
    [
        "1.2.3-alpha.1+build.5",
        "2.0.0-rc.1+sha.abcdef",
    ],
)
def test_manifest_spec_version_accepts_valid_semver_prerelease_and_build(
    tmp_path: Path, version: str
) -> None:
    manifest = (ROOT / "examples/service-operations/manifest.yaml").read_text(
        encoding="utf-8"
    )
    candidate = tmp_path / "manifest.yaml"
    candidate.write_text(
        manifest.replace("specVersion: 1.0.0", f"specVersion: {version}"),
        encoding="utf-8",
    )

    errors = validate_document(
        candidate,
        ROOT / "spec/v1/ontology-package.schema.json",
        definition="manifest",
    )

    assert errors == []


@pytest.mark.parametrize("version", ["01.0.0", "1.01.0", "1.0.01"])
def test_manifest_rejects_core_semver_with_leading_zero(
    tmp_path: Path, version: str
) -> None:
    manifest = (ROOT / "examples/service-operations/manifest.yaml").read_text(
        encoding="utf-8"
    )
    invalid = tmp_path / "manifest.yaml"
    invalid.write_text(
        manifest.replace("ontologyVersion: 1.0.0", f"ontologyVersion: {version}"),
        encoding="utf-8",
    )

    errors = validate_document(
        invalid,
        ROOT / "spec/v1/ontology-package.schema.json",
        definition="manifest",
    )

    assert any("ontologyVersion" in error for error in errors)
