from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from scripts.confidence import (
    WEIGHTS,
    confidence_grade,
    confidence_score,
    verify_claim_confidence,
)
from scripts.validate_package import (
    load_structured,
    validate_discovery_bundle,
    validate_adjudication,
    validate_document,
    validate_package,
)


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "spec/v1/ontology-package.schema.json"
DIMENSION_KEYS = {
    "crossSourceAgreement",
    "evidenceCoverage",
    "runtimeSupport",
    "semanticSpecificity",
    "constraintConsistency",
    "counterEvidenceAssessment",
}


def test_weights_are_the_normative_exact_values() -> None:
    assert WEIGHTS == {
        "crossSourceAgreement": pytest.approx(0.25),
        "evidenceCoverage": pytest.approx(0.20),
        "runtimeSupport": pytest.approx(0.20),
        "semanticSpecificity": pytest.approx(0.15),
        "constraintConsistency": pytest.approx(0.10),
        "counterEvidenceAssessment": pytest.approx(0.10),
    }


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "D"), (49, "D"), (50, "C"), (69, "C"), (70, "B"),
     (84, "B"), (85, "A"), (100, "A")],
)
def test_grade_boundaries(score: int, expected: str) -> None:
    assert confidence_grade(score) == expected


def test_confidence_score_uses_decimal_half_up_rounding() -> None:
    dimensions = dict.fromkeys(DIMENSION_KEYS, 0)
    dimensions["crossSourceAgreement"] = 2

    assert confidence_score(dimensions) == 1


@pytest.mark.parametrize("value", [-1, 101, 50.5, True, "50"])
def test_confidence_score_rejects_invalid_dimension_values(value: object) -> None:
    dimensions = dict.fromkeys(DIMENSION_KEYS, 50)
    dimensions["runtimeSupport"] = value

    with pytest.raises((TypeError, ValueError)):
        confidence_score(dimensions)


def test_confidence_score_requires_exact_dimension_keys() -> None:
    dimensions = dict.fromkeys(DIMENSION_KEYS, 50)
    dimensions.pop("runtimeSupport")
    dimensions["unexpected"] = 50

    with pytest.raises(ValueError, match="exactly"):
        confidence_score(dimensions)


@pytest.mark.parametrize("score", [-1, 101, 50.5, True])
def test_confidence_grade_rejects_invalid_scores(score: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        confidence_grade(score)  # type: ignore[arg-type]


def test_verify_claim_confidence_reports_score_and_grade_mismatches() -> None:
    claim = {
        "confidenceDimensions": dict.fromkeys(DIMENSION_KEYS, 90),
        "confidence": 89,
        "grade": "B",
    }

    errors = verify_claim_confidence(claim)

    assert any("confidence" in error and "expected 90" in error for error in errors)
    assert any("grade" in error and "expected 'A'" in error for error in errors)


def test_verify_claim_confidence_requires_matching_rationales_and_deductions() -> None:
    claim = load_structured(ROOT / "examples/discovery/claims.yaml")["claims"][0]
    claim = deepcopy(claim)
    claim["confidenceRationale"]["runtimeSupport"]["score"] -= 1
    claim["confidenceRationale"]["semanticSpecificity"]["score"] = 99
    claim["confidenceRationale"]["semanticSpecificity"]["deductions"] = []

    errors = verify_claim_confidence(claim)

    assert any("runtimeSupport" in error and "confidenceDimensions" in error for error in errors)
    assert any("semanticSpecificity" in error and "deductions" in error for error in errors)


def test_counter_evidence_dimension_uses_normative_rubric_scores() -> None:
    claim = load_structured(ROOT / "examples/discovery/claims.yaml")["claims"][0]
    claim = deepcopy(claim)
    claim["confidenceDimensions"]["counterEvidenceAssessment"] = 60
    claim["confidenceRationale"]["counterEvidenceAssessment"]["score"] = 60

    errors = verify_claim_confidence(claim)

    assert any("counterEvidenceAssessment" in error and "0, 25, 50, 75, 100" in error for error in errors)


def test_package_validation_recomputes_embedded_claim_confidence(tmp_path: Path) -> None:
    package_dir = tmp_path / "service-operations"
    shutil.copytree(ROOT / "examples/service-operations", package_dir)
    evidence_path = package_dir / "evidence.yaml"
    evidence = load_structured(evidence_path)
    evidence["discoveryClaims"][0]["confidence"] = 89
    import yaml
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")

    errors = validate_package(package_dir, SCHEMA)

    assert any("claim.projection-demo" in error and "expected 91" in error for error in errors)


def test_package_claim_evidence_refs_must_target_evidence_records(tmp_path: Path) -> None:
    package_dir = tmp_path / "service-operations"
    shutil.copytree(ROOT / "examples/service-operations", package_dir)
    evidence_path = package_dir / "evidence.yaml"
    evidence = load_structured(evidence_path)
    evidence["discoveryClaims"][0]["evidenceRefs"] = ["claim.projection-demo"]
    import yaml
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")

    errors = validate_package(package_dir, SCHEMA)

    assert any(
        "evidenceRefs" in error and "expected EvidenceRecord" in error
        for error in errors
    )


@pytest.mark.parametrize("reserved", ["external:record", "urn:record"])
def test_package_rejects_reserved_evidence_record_declaration_and_ref(
    tmp_path: Path, reserved: str
) -> None:
    package_dir = tmp_path / "service-operations"
    shutil.copytree(ROOT / "examples/service-operations", package_dir)
    evidence_path = package_dir / "evidence.yaml"
    evidence = load_structured(evidence_path)
    evidence["evidenceRecords"][0]["id"] = reserved
    evidence["discoveryClaims"][0]["evidenceRefs"] = [reserved]
    import yaml
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")

    errors = validate_package(package_dir, SCHEMA)

    assert any("evidenceRecords/0/id" in error for error in errors)
    assert any("discoveryClaims/0/evidenceRefs" in error for error in errors)


def test_discovery_examples_validate_against_closed_schemas() -> None:
    assert validate_document(
        ROOT / "examples/discovery/evidence-graph.yaml", SCHEMA, "evidenceGraph"
    ) == []
    assert validate_document(
        ROOT / "examples/discovery/claims.yaml", SCHEMA, "discoveryClaimsDocument"
    ) == []
    assert validate_document(
        ROOT / "examples/discovery/adjudication.yaml", SCHEMA, "adjudicationDocument"
    ) == []


def test_human_adjudication_exactly_covers_claims_and_preserves_snapshot() -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")
    adjudication = load_structured(ROOT / "examples/discovery/adjudication.yaml")

    assert validate_adjudication(graph, claims, adjudication, SCHEMA) == []
    assert len(adjudication["decisions"]) == len(claims["claims"]) == 4
    assert next(item for item in claims["claims"] if item["grade"] == "A")["status"] == "proposed"
    outcomes = {
        claim["grade"]: next(
            item["outcome"] for item in adjudication["decisions"]
            if item["claimRef"] == claim["id"]
        )
        for claim in claims["claims"]
    }
    assert outcomes == {"A": "accepted", "B": "needsRevision", "C": "deferred", "D": "rejected"}


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "external_evidence", "bad_outcome"])
def test_adjudication_rejects_invalid_decisions(mutation: str) -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")
    adjudication = load_structured(ROOT / "examples/discovery/adjudication.yaml")
    if mutation == "unknown":
        adjudication["decisions"][0]["claimRef"] = "claim.unknown"
    elif mutation == "duplicate":
        adjudication["decisions"][1]["claimRef"] = adjudication["decisions"][0]["claimRef"]
    elif mutation == "external_evidence":
        adjudication["decisions"][0]["evidenceRefs"] = ["https://example.org/external"]
    else:
        adjudication["decisions"][0]["outcome"] = "autoAccepted"

    assert validate_adjudication(graph, claims, adjudication, SCHEMA)


@pytest.mark.parametrize("field", ["evidenceRefs", "counterEvidenceRefs"])
def test_discovery_claim_schema_rejects_external_evidence_refs(
    tmp_path: Path, field: str
) -> None:
    document = load_structured(ROOT / "examples/discovery/claims.yaml")
    document["claims"][0][field] = ["https://example.org/not-an-observation"]
    candidate = tmp_path / "claims.yaml"
    import yaml
    candidate.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    errors = validate_document(candidate, SCHEMA, "discoveryClaimsDocument")

    assert any(field in error for error in errors)


@pytest.mark.parametrize(
    "reserved",
    [
        "external:source", "urn:source", "EXTERNAL:source", "UrN:source",
        "did:example:123", "foo:source",
    ],
)
@pytest.mark.parametrize("target", ["claimId", "evidenceRef", "observationId"])
def test_discovery_schema_rejects_reserved_uri_like_internal_ids(
    tmp_path: Path, reserved: str, target: str
) -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")
    if target == "claimId":
        claims["claims"][0]["id"] = reserved
        document, definition = claims, "discoveryClaimsDocument"
    elif target == "evidenceRef":
        claims["claims"][0]["evidenceRefs"] = [reserved]
        document, definition = claims, "discoveryClaimsDocument"
    else:
        graph["observations"][0]["id"] = reserved
        document, definition = graph, "evidenceGraph"
    candidate = tmp_path / "candidate.yaml"
    import yaml
    candidate.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    assert validate_document(candidate, SCHEMA, definition)


def test_internal_domain_prefix_remains_valid(tmp_path: Path) -> None:
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")
    claims["claims"][0]["counterEvidenceRefs"] = ["domain:Known"]
    candidate = tmp_path / "claims.yaml"
    import yaml
    candidate.write_text(yaml.safe_dump(claims, sort_keys=False), encoding="utf-8")

    assert validate_document(candidate, SCHEMA, "discoveryClaimsDocument") == []


def test_domain_prefixed_reference_is_internal_but_must_resolve() -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")
    claims["claims"][0]["counterEvidenceRefs"] = ["domain:Missing"]

    errors = validate_discovery_bundle(graph, claims, SCHEMA)

    assert any("domain:Missing" in error and "EvidenceObservation ID" in error for error in errors)


def test_discovery_examples_cover_sources_refs_grades_and_governance() -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    document = load_structured(ROOT / "examples/discovery/claims.yaml")
    observations = graph["observations"]
    claims = document["claims"]

    assert {item["kind"] for item in observations} >= {
        "database", "openapi", "code", "config", "eventLog"
    }
    observation_ids = {item["id"] for item in observations}
    assert {claim["grade"] for claim in claims} == {"A", "B", "C", "D"}
    assert all(set(claim["evidenceRefs"]) <= observation_ids for claim in claims)
    assert all(set(claim["counterEvidenceRefs"]) <= observation_ids for claim in claims)
    assert all(verify_claim_confidence(claim) == [] for claim in claims)
    assert all(claim["status"] == "proposed" for claim in claims)
    assert next(claim for claim in claims if claim["grade"] == "A")["status"] == "proposed"
    assert validate_discovery_bundle(graph, document, SCHEMA) == []
    assert all(len(set(claim["confidenceDimensions"].values())) > 1 for claim in claims)


@pytest.mark.parametrize(
    ("field", "reference"),
    [
        ("evidenceRefs", "observation.missing"),
        ("counterEvidenceRefs", "claim.serviceRequestEntity"),
        ("evidenceRefs", "https://example.org/external"),
    ],
)
def test_discovery_bundle_rejects_non_observation_claim_refs(
    field: str, reference: str
) -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    document = load_structured(ROOT / "examples/discovery/claims.yaml")
    document["claims"][0][field] = [reference]

    errors = validate_discovery_bundle(graph, document, SCHEMA)

    assert any(field in error and reference in error for error in errors)


def test_discovery_bundle_rejects_rationale_ref_to_claim() -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    document = load_structured(ROOT / "examples/discovery/claims.yaml")
    document["claims"][0]["confidenceRationale"]["evidenceCoverage"][
        "evidenceRefs"
    ] = ["claim.serviceRequestEntity"]

    errors = validate_discovery_bundle(graph, document, SCHEMA)

    assert any("confidenceRationale/evidenceCoverage/evidenceRefs" in error for error in errors)


def test_discovery_bundle_reports_confidence_rationale_mismatch() -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    document = load_structured(ROOT / "examples/discovery/claims.yaml")
    document["claims"][0]["confidenceRationale"]["runtimeSupport"]["score"] = 84

    errors = validate_discovery_bundle(graph, document, SCHEMA)

    assert any(
        "confidenceRationale/runtimeSupport/score" in error
        and "confidenceDimensions" in error
        for error in errors
    )


@pytest.mark.parametrize("invalid_graph", [[], {"extra": True}])
def test_discovery_bundle_rejects_invalid_graph_structure(invalid_graph: object) -> None:
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")

    errors = validate_discovery_bundle(invalid_graph, claims, SCHEMA)

    assert errors and any("evidenceGraph" in error for error in errors)


def test_discovery_bundle_rejects_non_array_claims_and_extra_observation_field() -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")
    graph["observations"][0]["extra"] = True
    claims["claims"] = {}

    errors = validate_discovery_bundle(graph, claims, SCHEMA)

    assert any("evidenceGraph/observations/0" in error for error in errors)
    assert any("discoveryClaimsDocument/claims" in error for error in errors)


def test_discovery_bundle_enforces_identity_and_unique_ids() -> None:
    graph = load_structured(ROOT / "examples/discovery/evidence-graph.yaml")
    claims = load_structured(ROOT / "examples/discovery/claims.yaml")
    claims["ontologyId"] = "org.example.other"
    graph["observations"].append(deepcopy(graph["observations"][0]))
    claims["claims"].append(deepcopy(claims["claims"][1]))
    claims["claims"][0]["id"] = graph["observations"][0]["id"]

    errors = validate_discovery_bundle(graph, claims, SCHEMA)

    assert any("ontologyId" in error for error in errors)
    assert any("duplicate EvidenceObservation ID" in error for error in errors)
    assert any("duplicate DiscoveryClaim ID" in error for error in errors)
    assert any("ID collision" in error for error in errors)


@pytest.mark.parametrize(
    ("level", "score"),
    [("none", 75), ("minor", 100), ("material", 25),
     ("strong", 50), ("coreContradiction", 100)],
)
def test_counter_evidence_level_must_match_score(level: str, score: int) -> None:
    claim = deepcopy(load_structured(ROOT / "examples/discovery/claims.yaml")["claims"][0])
    claim["counterEvidenceLevel"] = level
    claim["confidenceDimensions"]["counterEvidenceAssessment"] = score
    claim["confidenceRationale"]["counterEvidenceAssessment"]["score"] = score

    errors = verify_claim_confidence(claim)

    assert any("counterEvidenceLevel" in error for error in errors)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("confidence",), True),
        (("confidenceDimensions", "runtimeSupport"), 2.0),
        (("confidenceRationale", "runtimeSupport", "score"), True),
    ],
)
def test_verify_claim_confidence_rejects_python_numeric_subtypes(
    path: tuple[str, ...], value: object
) -> None:
    claim = deepcopy(load_structured(ROOT / "examples/discovery/claims.yaml")["claims"][0])
    target = claim
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value

    assert verify_claim_confidence(claim)


def test_verify_claim_confidence_rejects_extra_rationale_item_field() -> None:
    claim = deepcopy(load_structured(ROOT / "examples/discovery/claims.yaml")["claims"][0])
    claim["confidenceRationale"]["runtimeSupport"]["extra"] = True

    errors = verify_claim_confidence(claim)

    assert any("exactly" in error and "runtimeSupport" in error for error in errors)


def test_verify_claim_confidence_rejects_empty_rationale_text() -> None:
    claim = deepcopy(load_structured(ROOT / "examples/discovery/claims.yaml")["claims"][0])
    claim["confidenceRationale"]["runtimeSupport"]["rationale"] = ""

    errors = verify_claim_confidence(claim)

    assert any("runtimeSupport/rationale" in error and "non-empty" in error for error in errors)


@pytest.mark.parametrize(
    "field",
    [
        "counterEvidenceRefs",
        "counterEvidenceAssessment",
        "alternatives",
        "falsifiers",
        "validationQuestions",
        "capabilityQuestions",
    ],
)
def test_discovery_claim_rejects_missing_explainability_fields(
    tmp_path: Path, field: str
) -> None:
    document = load_structured(ROOT / "examples/discovery/claims.yaml")
    invalid = deepcopy(document)
    del invalid["claims"][0][field]
    candidate = tmp_path / "claims.yaml"
    import yaml
    candidate.write_text(yaml.safe_dump(invalid, sort_keys=False), encoding="utf-8")

    errors = validate_document(candidate, SCHEMA, "discoveryClaimsDocument")

    assert any(field in error and "required" in error for error in errors)


def test_discovery_documentation_covers_normative_contract() -> None:
    reverse = (ROOT / "docs/reverse-engineering.md").read_text(encoding="utf-8")
    confidence = (ROOT / "docs/discovery-confidence.md").read_text(encoding="utf-8")

    for phase in (
        "采集", "Evidence Graph", "deterministic inference",
        "semantic-assisted matching", "conflict retention",
        "human adjudication", "Baseline Ontology",
    ):
        assert phase in reverse
    for kind in ("database", "OpenAPI", "code", "config", "event log"):
        assert kind.casefold() in reverse.casefold()
    assert "observation" in reverse and "inference" in reverse
    assert reverse.count("输入") >= 7 and reverse.count("输出") >= 7
    assert reverse.count("门禁") >= 7

    for weight in ("25%", "20%", "15%", "10%"):
        assert weight in confidence
    assert "ROUND_HALF_UP" in confidence
    assert "LLM 不是证据" in confidence
    assert confidence.count("？") >= 7
    assert "../examples/discovery/evidence-graph.yaml" in confidence
    assert "../examples/discovery/claims.yaml" in confidence
    for score in ("100", "75", "50", "25", "0"):
        assert score in confidence
    for level in (
        "no material conflict", "minor unresolved", "material bounded",
        "strong unresolved", "core contradiction",
    ):
        assert level in confidence


def test_counter_evidence_weight_means_conflict_strength_and_penalty() -> None:
    confidence = (ROOT / "docs/discovery-confidence.md").read_text(encoding="utf-8")
    row = next(
        line
        for line in confidence.splitlines()
        if line.startswith("| `counterEvidenceAssessment`")
    )

    assert "反证" in row and "冲突强度" in row and "扣分" in row
    assert "是否系统检索并诚实处理反证" not in confidence


def test_discovery_examples_are_explicitly_synthetic_and_not_admissible() -> None:
    for path in (
        ROOT / "examples/discovery/evidence-graph.yaml",
        ROOT / "examples/discovery/claims.yaml",
        ROOT / "docs/reverse-engineering.md",
    ):
        text = path.read_text(encoding="utf-8").casefold()
        assert "synthetic" in text
        assert "not admissible" in text
        assert "not admissible" in text or "不可采信" in text
