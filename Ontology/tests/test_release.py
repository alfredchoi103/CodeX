from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml
import pytest
from rdflib import Graph, Namespace
from rdflib.namespace import OWL, RDF, RDFS

from scripts.validate_package import calculate_digest, load_structured
from scripts.validate_release import Finding, ReleaseReport, validate_release


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/service-operations"


def _copy_package(tmp_path: Path) -> Path:
    candidate = tmp_path / "service-operations"
    shutil.copytree(EXAMPLE, candidate)
    return candidate


def _write_yaml(path: Path, document: object) -> None:
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def _refresh_package_digest(package_dir: Path) -> None:
    digest = calculate_digest(package_dir)
    manifest = load_structured(package_dir / "manifest.yaml")
    traceability = load_structured(package_dir / "traceability.yaml")
    manifest["contentDigest"] = digest
    traceability["sourceDigest"] = digest
    _write_yaml(package_dir / "manifest.yaml", manifest)
    _write_yaml(package_dir / "traceability.yaml", traceability)


def _errors(report: ReleaseReport, level: str) -> list[str]:
    return next(result.errors for result in report.levels if result.level == level)


def _findings(report: ReleaseReport, level: str) -> list[Finding]:
    return next(result.findings for result in report.levels if result.level == level)


def _assert_complete_finding(finding: Finding, error_class: str) -> None:
    assert finding.error_class == error_class
    assert finding.element_id
    assert finding.path
    assert finding.rule
    assert finding.fix
    assert finding.message


def test_valid_service_package_passes_all_static_release_levels() -> None:
    report = validate_release(EXAMPLE)

    assert isinstance(report, ReleaseReport)
    assert report.passed
    assert report.ontology_id == "org.example.service-operations"
    assert report.ontology_version == "1.0.0"
    assert [result.level for result in report.levels] == ["L0", "L1", "L2", "L3-static"]
    assert all(result.passed and result.errors == [] and result.findings == [] for result in report.levels)
    assert [result.status for result in report.levels] == ["pass"] * 4
    assert "runtime" in report.scope_note.lower()
    assert "live" in report.scope_note.lower()


def test_missing_ontology_ttl_fails_l1(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    (candidate / "ontology.ttl").unlink()

    report = validate_release(candidate)

    assert not report.passed
    assert any("ontology.ttl" in error and "missing" in error for error in _errors(report, "L1"))
    _assert_complete_finding(_findings(report, "L1")[0], "semantic")
    assert [result.status for result in report.levels] == ["pass", "fail", "blocked", "blocked"]


def test_empty_rdf_projection_fails_exact_parity_and_blocks_higher_levels(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    manifest = load_structured(candidate / "manifest.yaml")
    (candidate / "ontology.ttl").write_text(
        "@prefix ebo: <https://w3id.org/executable-business-ontology#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix ex: <https://example.org/empty/> .\n"
        f'ex:o a owl:Ontology ; ebo:ontologyId "{manifest["ontologyId"]}" ; '
        f'ebo:ontologyVersion "{manifest["ontologyVersion"]}" ; '
        f'ebo:specVersion "{manifest["specVersion"]}" ; '
        f'ebo:contentDigest "{manifest["contentDigest"]}" .\n',
        encoding="utf-8",
    )

    report = validate_release(candidate)

    assert report.levels[1].status == "fail"
    assert any(item.rule == "EBO-L1-RDF-PARITY" for item in _findings(report, "L1"))
    assert report.levels[2].status == report.levels[3].status == "blocked"


def test_unreachable_state_fails_l2_after_l0_digest_is_refreshed(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    kinetics["stateMachines"][0]["transitions"][0]["fromRef"] = "request.submitted"
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    assert any("unreachable" in error and "request.submitted" in error for error in _errors(report, "L2"))


def test_trace_identity_mismatch_fails_l3_static(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    traceability = load_structured(candidate / "traceability.yaml")
    traceability["ontologyVersion"] = "2.0.0"
    _write_yaml(candidate / "traceability.yaml", traceability)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    assert any("ontologyVersion" in error and "manifest" in error for error in _errors(report, "L3-static"))
    finding = next(item for item in _findings(report, "L3-static") if "ontologyVersion" in item.path)
    _assert_complete_finding(finding, "traceability")


def test_action_without_permission_refs_fails_l2(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    del kinetics["actions"][0]["permissionRefs"]
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    finding = next(item for item in _findings(report, "L2") if "permissionRefs" in item.path)
    _assert_complete_finding(finding, "behavioral")
    assert finding.element_id == "submitServiceRequest"


@pytest.mark.parametrize(
    ("field", "wrong_ref", "rule"),
    [
        ("permissionRefs", "ServiceRequest", "EBO-L2-ACTION-PERMISSION-TYPE"),
        ("auditRefs", "ServiceRequest", "EBO-L2-ACTION-AUDIT-TYPE"),
        ("compensationRefs", "ServiceRequest", "EBO-L2-ACTION-COMPENSATION-TYPE"),
    ],
)
def test_action_governance_refs_have_exact_types(
    tmp_path: Path, field: str, wrong_ref: str, rule: str
) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    kinetics["actions"][0][field] = [wrong_ref]
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    finding = next(item for item in _findings(report, "L2") if item.rule == rule)
    assert finding.element_id == "submitServiceRequest"
    assert field in finding.path


def test_action_without_audit_refs_fails_l2(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    del kinetics["actions"][0]["auditRefs"]
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    assert any("auditRefs" in item.path for item in _findings(report, "L2"))


def test_action_with_side_effects_without_compensation_fails_l2(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    kinetics["actions"][0].pop("compensationRefs", None)
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    assert any("compensationRefs" in item.path for item in _findings(report, "L2"))


def test_transition_closure_does_not_depend_on_expression_substrings(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    action = next(item for item in kinetics["actions"] if item["id"] == "assignWorkItem")
    action["preconditions"] = [
        item for item in action["preconditions"] if "ServiceRequest" not in item
    ]
    action["effects"] = [
        item for item in action["effects"] if item["targetRef"] != "ServiceRequest"
    ]
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    assert _findings(report, "L2") == []


def test_transition_requires_exact_structured_action_contract(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    action = next(item for item in kinetics["actions"] if item["id"] == "assignWorkItem")
    action["stateTransitions"] = [
        item for item in action.get("stateTransitions", [])
        if item.get("subjectRef") != "ServiceRequest"
    ]
    action["preconditions"].append("NotServiceRequest.status == 'submitted'")
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert any(
        item.rule == "EBO-L2-TRANSITION-CONTRACT"
        for item in _findings(report, "L2")
    )


def test_state_machine_subject_ref_must_reference_an_object_type(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    kinetics = load_structured(candidate / "kinetics.yaml")
    kinetics["stateMachines"][0]["subjectRef"] = "submitServiceRequest"
    _write_yaml(candidate / "kinetics.yaml", kinetics)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    finding = next(
        item for item in _findings(report, "L2")
        if item.rule == "EBO-L2-STATE-SUBJECT"
    )
    _assert_complete_finding(finding, "behavioral")


def test_release_cli_prints_only_the_contract_success_line() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.validate_release", "examples/service-operations"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert completed.stdout == "PASS org.example.service-operations@1.0.0 L0-L3-static\n"
    assert completed.stderr == ""


def test_release_cli_groups_failures_by_stage(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    (candidate / "ontology.ttl").write_text("not turtle", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.validate_release", str(candidate)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "level=L1 class=semantic" in completed.stdout
    assert "rule=" in completed.stdout
    assert "path=" in completed.stdout
    assert "element=" in completed.stdout
    assert "message=" in completed.stdout
    assert "fix=" in completed.stdout
    assert "ontology.ttl" in completed.stdout
    assert "PASS " not in completed.stdout


def test_rdf_projection_symlink_is_rejected_without_following_it(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    outside = tmp_path / "outside.ttl"
    outside.write_text((candidate / "ontology.ttl").read_text(encoding="utf-8"), encoding="utf-8")
    (candidate / "ontology.ttl").unlink()
    (candidate / "ontology.ttl").symlink_to(outside)

    report = validate_release(candidate)

    finding = next(item for item in _findings(report, "L1") if "symlink" in item.message)
    assert finding.rule == "EBO-L1-RDF-CONTAINMENT"
    assert report.levels[2].status == report.levels[3].status == "blocked"


def test_binding_path_failure_has_actionable_binding_class(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    bindings = load_structured(candidate / "bindings.yaml")
    bindings["dataBindings"][0]["mappings"][0]["ontologyPath"] = "Unknown.path"
    _write_yaml(candidate / "bindings.yaml", bindings)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    finding = next(item for item in _findings(report, "L3-static") if item.error_class == "binding")
    assert finding.element_id == "binding.serviceRequestTable"
    assert finding.rule == "EBO-L3-BINDING-PATH"


@pytest.mark.parametrize(
    "collection",
    ["dataBindings", "apiBindings", "codeBindings", "eventBindings"],
)
def test_binding_target_ref_rejects_governance_ids(
    tmp_path: Path, collection: str
) -> None:
    candidate = _copy_package(tmp_path)
    bindings = load_structured(candidate / "bindings.yaml")
    bindings[collection][0]["targetRef"] = "approval.initial"
    _write_yaml(candidate / "bindings.yaml", bindings)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    finding = next(item for item in _findings(report, "L3-static") if item.rule == "EBO-L3-BINDING-TARGET-TYPE")
    assert finding.error_class == "binding"
    assert finding.element_id == bindings[collection][0]["id"]
    assert "targetRef" in finding.path


def test_binding_ontology_path_rejects_governance_ids(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    bindings = load_structured(candidate / "bindings.yaml")
    bindings["dataBindings"][0]["mappings"][0]["ontologyPath"] = "approval.initial"
    _write_yaml(candidate / "bindings.yaml", bindings)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert any(item.rule == "EBO-L3-BINDING-PATH" for item in _findings(report, "L3-static"))


def test_schema_valid_invalid_split_fails_l3_evolution(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    source = load_structured(ROOT / "examples/evolution/migration.yaml")["changes"][0]
    change = dict(source)
    change.update(
        id="change.invalid-split",
        predecessorRefs=["ServiceRequest"],
        successorRefs=["WorkItem"],
        evidenceRefs=["evidence.process"],
    )
    migrations = {"version": "1.0.0", "changes": [change], "lineage": [
        {"operation": "split", "predecessorRefs": ["ServiceRequest"], "successorRefs": ["WorkItem"]}
    ]}
    _write_yaml(candidate / "migrations.yaml", migrations)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    finding = next(item for item in _findings(report, "L3-static") if item.error_class == "evolution")
    assert finding.rule == "EBO-L3-PACKAGE-MIGRATION"
    assert "split requires" in finding.message


@pytest.mark.parametrize("coverage", ["empty", "partial"])
def test_incomplete_approval_coverage_fails_l3_governance(
    tmp_path: Path, coverage: str
) -> None:
    candidate = _copy_package(tmp_path)
    evidence = load_structured(candidate / "evidence.yaml")
    if coverage == "empty":
        evidence["approvals"] = []
    else:
        evidence["approvals"][0]["approvedElementRefs"] = ["ServiceOperationsInterface"]
    _write_yaml(candidate / "evidence.yaml", evidence)
    _refresh_package_digest(candidate)

    report = validate_release(candidate)

    assert _errors(report, "L0") == []
    finding = next(item for item in _findings(report, "L3-static") if item.rule == "EBO-L3-APPROVAL-COVERAGE")
    assert finding.error_class == "governance"


def test_structurally_invalid_document_reports_l0_instead_of_crashing(tmp_path: Path) -> None:
    candidate = _copy_package(tmp_path)
    (candidate / "kinetics.yaml").write_text("[]\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.validate_release", str(candidate)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "level=L0 class=structural" in completed.stdout
    assert "is not of type 'object'" in completed.stdout
    assert "Traceback" not in completed.stderr


def test_component_package_cli_does_not_claim_a_conformance_level() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.validate_package", "examples/service-operations"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "Valid ontology package:" in completed.stdout
    assert "L3" not in completed.stdout
