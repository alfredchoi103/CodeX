from pathlib import Path

import pytest
from pyshacl.errors import ReportableRuntimeError
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS

from scripts.validate_package import load_structured
from scripts.validate_rdf import validate_rdf


ROOT = Path(__file__).parents[1]
SHAPES = ROOT / "spec/v1/ontology.shacl.ttl"
EBO = Namespace("https://w3id.org/executable-business-ontology#")
OPS = Namespace("https://example.org/ontology/service-operations/")


PREFIXES = """
@prefix ebo: <https://w3id.org/executable-business-ontology#> .
@prefix ex: <https://example.org/test/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""


def validate_turtle(tmp_path: Path, turtle: str) -> tuple[bool, str]:
    candidate = tmp_path / "candidate.ttl"
    candidate.write_text(PREFIXES + turtle, encoding="utf-8")
    return validate_rdf(candidate, SHAPES)


def assert_single_violation(report: str, message_term: str) -> None:
    assert report.count("Constraint Violation") == 1, report
    assert message_term in report


def test_service_operations_rdf_conforms() -> None:
    conforms, report = validate_rdf(
        ROOT / "examples/service-operations/ontology.ttl", SHAPES
    )
    assert conforms, report


def test_object_without_stable_id_is_rejected() -> None:
    conforms, report = validate_rdf(
        ROOT / "examples/service-operations/ontology-invalid.ttl", SHAPES
    )
    assert not conforms
    assert_single_violation(report, "stableId")


def test_duplicate_stable_id_is_rejected(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:first a ebo:PropertyType ;
    ebo:stableId "duplicate.id" ;
    rdfs:label "First" ;
    ebo:valueType "string" .
ex:second a ebo:PropertyType ;
    ebo:stableId "duplicate.id" ;
    rdfs:label "Second" ;
    ebo:valueType "string" .
""",
    )

    assert not conforms
    assert_single_violation(report, "duplicate stableId")
    assert 'Value Node: Literal("duplicate.id")' in report


def test_link_endpoint_must_be_an_object_type(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:key a ebo:PropertyType ;
    ebo:stableId "Object.key" ;
    rdfs:label "Object key" ;
    ebo:valueType "string" .
ex:object a ebo:ObjectType ;
    ebo:stableId "Object" ;
    rdfs:label "Object" ;
    ebo:key ex:key .
ex:link a ebo:LinkType ;
    ebo:stableId "Object.invalidEndpoint.Object" ;
    rdfs:label "Invalid endpoint link" ;
    ebo:source ex:key ;
    ebo:target ex:object ;
    ebo:cardinality "one-to-one" .
""",
    )

    assert not conforms
    assert_single_violation(report, "declared ObjectType")


def test_literal_link_endpoint_reports_one_node_kind_violation(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:key a ebo:PropertyType ;
    ebo:stableId "Object.key" ;
    rdfs:label "Object key" ;
    ebo:valueType "string" .
ex:object a ebo:ObjectType ;
    ebo:stableId "Object" ;
    rdfs:label "Object" ;
    ebo:key ex:key .
ex:link a ebo:LinkType ;
    ebo:stableId "Object.literalEndpoint.Object" ;
    rdfs:label "Literal endpoint link" ;
    ebo:source "not an IRI" ;
    ebo:target ex:object ;
    ebo:cardinality "one-to-one" .
""",
    )

    assert not conforms
    assert_single_violation(report, "source ObjectType")


def test_action_without_audit_rule_is_rejected(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:action a ebo:ActionType ;
    ebo:stableId "action.withoutAudit" ;
    rdfs:label "Action without audit rule" ;
    ebo:precondition "Object is ready" ;
    ebo:effect "state changes" .
""",
    )

    assert not conforms
    assert_single_violation(report, "auditRule")


def test_claim_confidence_above_100_is_rejected(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.invalidConfidence" ;
    rdfs:label "Invalid confidence claim" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence 101 ;
    ebo:grade "A" ;
    ebo:falsifier "Contradicting source evidence" ;
    ebo:counterEvidenceAssessment "No counter-evidence found" ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )

    assert not conforms
    assert_single_violation(report, "confidence")


def test_property_value_type_must_be_a_string(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:property a ebo:PropertyType ;
    ebo:stableId "Object.property" ;
    rdfs:label "Object property" ;
    ebo:valueType 42 .
""",
    )

    assert not conforms
    assert_single_violation(report, "valueType")


def test_action_effect_must_be_a_string(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:action a ebo:ActionType ;
    ebo:stableId "action.numericEffect" ;
    rdfs:label "Action with numeric effect" ;
    ebo:precondition "Object is ready" ;
    ebo:effect 42 ;
    ebo:auditRule ex:audit .
""",
    )

    assert not conforms
    assert_single_violation(report, "effect")


def test_action_precondition_must_be_a_string_when_present(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:action a ebo:ActionType ;
    ebo:stableId "action.numericPrecondition" ;
    rdfs:label "Action with numeric precondition" ;
    ebo:precondition 42 ;
    ebo:effect "Object changes" ;
    ebo:auditRule ex:audit .
""",
    )

    assert not conforms
    assert_single_violation(report, "precondition")


def test_action_audit_rule_must_be_an_iri(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:action a ebo:ActionType ;
    ebo:stableId "action.literalAudit" ;
    rdfs:label "Action with literal audit" ;
    ebo:effect "Object changes" ;
    ebo:auditRule "audit" .
""",
    )

    assert not conforms
    assert_single_violation(report, "auditRule")


def test_action_without_precondition_conforms(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:action a ebo:ActionType ;
    ebo:stableId "action.noPrecondition" ;
    rdfs:label "Action without precondition" ;
    ebo:effect "Object changes" ;
    ebo:auditRule ex:audit .
""",
    )

    assert conforms, report


def test_claim_supporting_evidence_must_be_an_iri(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.literalEvidence" ;
    rdfs:label "Claim with literal evidence" ;
    ebo:supportingEvidence "evidence" ;
    ebo:confidence 50 ;
    ebo:grade "C" ;
    ebo:falsifier "Contradicting evidence" ;
    ebo:counterEvidenceAssessment "None found" ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )

    assert not conforms
    assert_single_violation(report, "supportingEvidence")


def test_claim_falsifier_must_be_a_string(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.numericFalsifier" ;
    rdfs:label "Claim with numeric falsifier" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence 50 ;
    ebo:grade "C" ;
    ebo:falsifier 42 ;
    ebo:counterEvidenceAssessment "None found" ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )

    assert not conforms
    assert_single_violation(report, "falsifier")


def test_claim_confidence_must_be_an_integer(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.decimalConfidence" ;
    rdfs:label "Claim with decimal confidence" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence 50.5 ;
    ebo:grade "C" ;
    ebo:falsifier "Contradicting evidence" ;
    ebo:counterEvidenceAssessment "None found" ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )

    assert not conforms
    assert_single_violation(report, "confidence")


@pytest.mark.parametrize(("confidence", "grade"), [(0, "D"), (100, "A")])
def test_claim_confidence_boundaries_conform(
    tmp_path: Path, confidence: int, grade: str
) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        f"""
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.boundary{confidence}" ;
    rdfs:label "Boundary confidence claim" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence {confidence} ;
    ebo:grade "{grade}" ;
    ebo:falsifier "Contradicting evidence" ;
    ebo:counterEvidenceAssessment "None found" ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )

    assert conforms, report


def test_claim_grade_must_match_confidence(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.badGrade" ;
    rdfs:label "Bad grade" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence 100 ;
    ebo:grade "D" ;
    ebo:falsifier "Contradiction" ;
    ebo:counterEvidenceAssessment "None" ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )
    assert not conforms
    assert "grade" in report


def test_counter_evidence_level_must_match_score(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.badCounter" ;
    rdfs:label "Bad counter score" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence 100 ;
    ebo:grade "A" ;
    ebo:falsifier "Contradiction" ;
    ebo:counterEvidenceAssessment "Core contradiction" ;
    ebo:counterEvidenceLevel "coreContradiction" ;
    ebo:counterEvidenceScore 100 .
""",
    )
    assert not conforms
    assert "counter" in report.lower()


def test_claim_requires_counter_evidence_level_and_score(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.missingCounterFields" ;
    rdfs:label "Missing counter fields" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence 100 ;
    ebo:grade "A" ;
    ebo:falsifier "Contradiction" ;
    ebo:counterEvidenceAssessment "None" .
""",
    )
    assert not conforms
    assert "counterEvidenceLevel" in report
    assert "counterEvidenceScore" in report


def test_counter_evidence_assessment_must_be_a_string(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.numericCounterAssessment" ;
    rdfs:label "Numeric counter assessment" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence 100 ;
    ebo:grade "A" ;
    ebo:falsifier "Contradiction" ;
    ebo:counterEvidenceAssessment 42 ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )
    assert not conforms
    assert "counterEvidenceAssessment" in report


def test_claim_confidence_below_zero_is_rejected(tmp_path: Path) -> None:
    conforms, report = validate_turtle(
        tmp_path,
        """
ex:claim a ebo:DiscoveryClaim ;
    ebo:stableId "claim.negativeConfidence" ;
    rdfs:label "Negative confidence claim" ;
    ebo:supportingEvidence ex:evidence ;
    ebo:confidence -1 ;
    ebo:grade "D" ;
    ebo:falsifier "Contradicting evidence" ;
    ebo:counterEvidenceAssessment "None found" ;
    ebo:counterEvidenceLevel "none" ;
    ebo:counterEvidenceScore 100 .
""",
    )

    assert not conforms
    assert_single_violation(report, "confidence")


def test_yaml_claims_are_the_source_for_rdf_claims() -> None:
    evidence = load_structured(ROOT / "examples/service-operations/evidence.yaml")
    yaml_claim_ids = {claim["id"] for claim in evidence["discoveryClaims"]}
    graph = Graph().parse(
        ROOT / "examples/service-operations/ontology.ttl", format="turtle"
    )
    rdf_claim_ids = {
        str(graph.value(subject, EBO.stableId))
        for subject in graph.subjects(RDF.type, EBO.DiscoveryClaim)
    }

    assert rdf_claim_ids == yaml_claim_ids

    for claim in evidence["discoveryClaims"]:
        subject = next(graph.subjects(EBO.stableId, Literal(claim["id"])))
        assert str(graph.value(subject, RDFS.label)) == claim["label"]
        assert str(graph.value(subject, EBO.claimStatement)) == claim["statement"]
        assert int(graph.value(subject, EBO.confidence)) == claim["confidence"]
        assert str(graph.value(subject, EBO.grade)) == claim["grade"]
        assert {
            str(value) for value in graph.objects(subject, EBO.falsifier)
        } == set(claim["falsifiers"])
        assert str(
            graph.value(subject, EBO.counterEvidenceAssessment)
        ) == claim["counterEvidenceAssessment"]
        assert str(graph.value(subject, EBO.counterEvidenceLevel)) == claim["counterEvidenceLevel"]
        assert int(graph.value(subject, EBO.counterEvidenceScore)) == claim[
            "confidenceDimensions"
        ]["counterEvidenceAssessment"]
        assert {
            str(graph.value(value, EBO.stableId))
            for value in graph.objects(subject, EBO.supportingEvidence)
        } == set(claim["evidenceRefs"])


def test_yaml_categories_are_exactly_projected_to_rdf_classes() -> None:
    semantics = load_structured(ROOT / "examples/service-operations/semantics.yaml")
    kinetics = load_structured(ROOT / "examples/service-operations/kinetics.yaml")
    evidence = load_structured(ROOT / "examples/service-operations/evidence.yaml")
    expected_by_class = {
        EBO.ObjectType: {item["id"] for item in semantics["objectTypes"]},
        EBO.PropertyType: {
            prop["id"]
            for object_type in semantics["objectTypes"]
            for prop in object_type["properties"]
        },
        EBO.LinkType: {item["id"] for item in semantics["links"]},
        EBO.ActionType: {item["id"] for item in kinetics["actions"]},
        EBO.QueryType: {item["id"] for item in kinetics["queries"]},
        EBO.StateMachine: {item["id"] for item in kinetics["stateMachines"]},
        EBO.DomainEventType: {item["id"] for item in kinetics["domainEvents"]},
        EBO.InterfaceType: {item["id"] for item in semantics["interfaces"]},
        EBO.Invariant: {item["id"] for item in semantics["invariants"]},
        EBO.BusinessTerm: {item["id"] for item in semantics["businessTerms"]},
        EBO.DiscoveryClaim: {
            item["id"] for item in evidence["discoveryClaims"]
        },
    }
    graph = Graph().parse(
        ROOT / "examples/service-operations/ontology.ttl", format="turtle"
    )

    for rdf_class, expected_ids in expected_by_class.items():
        actual_ids = {
            str(graph.value(subject, EBO.stableId))
            for subject in graph.subjects(RDF.type, rdf_class)
        }
        assert actual_ids == expected_ids, {
            "class": str(rdf_class),
            "missing": expected_ids - actual_ids,
            "extra": actual_ids - expected_ids,
        }


def test_rdf_ontology_metadata_matches_manifest() -> None:
    manifest = load_structured(ROOT / "examples/service-operations/manifest.yaml")
    graph = Graph().parse(
        ROOT / "examples/service-operations/ontology.ttl", format="turtle"
    )
    predicates = {
        "ontologyId": EBO.ontologyId,
        "ontologyVersion": EBO.ontologyVersion,
        "specVersion": EBO.specVersion,
        "contentDigest": EBO.contentDigest,
    }

    actual = {
        field: str(graph.value(OPS.ontology, predicate))
        for field, predicate in predicates.items()
    }
    expected = {field: str(manifest[field]) for field in predicates}
    assert actual == expected


def test_invalid_shapes_graph_is_rejected_by_meta_shacl(tmp_path: Path) -> None:
    data = tmp_path / "data.ttl"
    data.write_text(PREFIXES, encoding="utf-8")
    invalid_shapes = tmp_path / "invalid-shapes.ttl"
    invalid_shapes.write_text(
        PREFIXES
        + """
@prefix sh: <http://www.w3.org/ns/shacl#> .
ex:InvalidShape a sh:NodeShape ;
    sh:targetClass ex:Thing ;
    sh:closed "not-a-boolean" .
""",
        encoding="utf-8",
    )

    with pytest.raises(ReportableRuntimeError, match="SHACL File does not validate"):
        validate_rdf(data, invalid_shapes)
