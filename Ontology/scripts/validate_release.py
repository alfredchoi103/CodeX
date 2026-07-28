from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

import yaml
from rdflib import Graph, Namespace
from rdflib.exceptions import ParserError
from rdflib.namespace import OWL, RDF, RDFS
from rdflib.plugins.parsers.notation3 import BadSyntax
from pyshacl.errors import ReportableRuntimeError

from scripts.validate_package import (
    DOCUMENTS,
    calculate_digest,
    load_structured,
    validate_claim_confidences,
    validate_claim_evidence_types,
    validate_document,
    validate_documentation_refs,
    validate_references,
    validate_traceability_coverage,
    validate_traceability_evidence_types,
    validate_traceability_identity,
    validate_traceability_profile,
    _accepted_traceable_ids,
)
from scripts.validate_rdf import validate_rdf
from scripts.evolution import validate_package_migrations


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "spec/v1/ontology-package.schema.json"
DEFAULT_SHAPES = ROOT / "spec/v1/ontology.shacl.ttl"
EBO = Namespace("https://w3id.org/executable-business-ontology#")
BINDING_TARGET_CLASSES = {
    "dataBindings": frozenset({"ObjectType"}),
    "apiBindings": frozenset({"ActionType", "QueryType"}),
    "eventBindings": frozenset({"DomainEventType"}),
    "codeBindings": frozenset(
        {
            "ObjectType", "PropertyType", "LinkType", "InterfaceType", "Invariant",
            "BusinessTerm", "ActionType", "QueryType", "StateMachine", "DomainEventType",
        }
    ),
}


@dataclass(frozen=True)
class Finding:
    error_class: str
    element_id: str
    path: str
    rule: str
    fix: str
    message: str


@dataclass(frozen=True)
class LevelResult:
    level: str
    status: str
    findings: list[Finding]

    @property
    def errors(self) -> list[str]:
        return [f"{finding.path}: {finding.message}" for finding in self.findings]

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True)
class ReleaseReport:
    ontology_id: str | None
    ontology_version: str | None
    levels: list[LevelResult]
    scope_note: str = (
        "L0-L3-static performs static validation only; it does not execute runtime "
        "behavior or connect to live systems."
    )

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.levels)


_ERROR_CLASSES = {
    "L0": "structural",
    "L1": "semantic",
    "L2": "behavioral",
    "L3-static": "evidence",
}


def _finding(level: str, error: str) -> Finding:
    path, separator, message = error.partition(": ")
    if not separator:
        path, message = "package", error
    rule = {
        "L0": "EBO-L0-STRUCTURE",
        "L1": "EBO-L1-SEMANTIC",
        "L2": "EBO-L2-BEHAVIOR",
        "L3-static": "EBO-L3-STATIC",
    }[level]
    if "permission-type" in path:
        rule = "EBO-L2-ACTION-PERMISSION-TYPE"
    elif "audit-type" in path:
        rule = "EBO-L2-ACTION-AUDIT-TYPE"
    elif "compensation-type" in path:
        rule = "EBO-L2-ACTION-COMPENSATION-TYPE"
    elif "permissionRefs" in path:
        rule = "EBO-L2-ACTION-PERMISSION"
    elif "auditRefs" in path:
        rule = "EBO-L2-ACTION-AUDIT"
    elif "compensationRefs" in path:
        rule = "EBO-L2-ACTION-COMPENSATION"
    elif "subjectRef" in path:
        rule = "EBO-L2-STATE-SUBJECT"
    elif "transition-precondition" in path:
        rule = "EBO-L2-TRANSITION-PRECONDITION"
    elif "transition-effect" in path:
        rule = "EBO-L2-TRANSITION-EFFECT"
    elif "transition-contract" in path:
        rule = "EBO-L2-TRANSITION-CONTRACT"
    elif "rdf-parity" in path:
        rule = "EBO-L1-RDF-PARITY"
    elif "rdf-containment" in path:
        rule = "EBO-L1-RDF-CONTAINMENT"
    elif "binding-path" in path:
        rule = "EBO-L3-BINDING-PATH"
    elif "binding-target-type" in path:
        rule = "EBO-L3-BINDING-TARGET-TYPE"
    elif "approval-coverage" in path:
        rule = "EBO-L3-APPROVAL-COVERAGE"
    elif path.startswith("migrations.yaml"):
        rule = "EBO-L3-PACKAGE-MIGRATION"
    element_id = "package"
    if match := re.search(r"(?:action|transition|machine|binding|approval) '([^']+)'", message):
        element_id = match.group(1)
    fix = {
        "L0": "correct the package document and recompute canonical digests",
        "L1": "restore resolvable semantic references or a conforming RDF projection",
        "L2": "complete the action and state-machine behavioral contract",
        "L3-static": "restore evidence, traceability, binding, and projection consistency",
    }[level]
    error_class = _ERROR_CLASSES[level]
    if level == "L3-static":
        if "digest" in path:
            error_class = "integrity"
        elif path.startswith("bindings.yaml"):
            error_class = "binding"
        elif path.startswith("traceability.yaml"):
            error_class = "traceability"
        elif "approval" in path:
            error_class = "governance"
        elif path.startswith("migrations.yaml"):
            error_class = "evolution"
        elif path.startswith("ontology.ttl"):
            error_class = "integrity"
    return Finding(
        error_class=error_class,
        element_id=element_id,
        path=path,
        rule=rule,
        fix=fix,
        message=message,
    )


def _level(level: str, errors: list[str]) -> LevelResult:
    return LevelResult(level, "fail" if errors else "pass", [_finding(level, error) for error in errors])


def _blocked(level: str) -> LevelResult:
    return LevelResult(level, "blocked", [])


def _load_documents(package_dir: Path) -> tuple[dict[str, Any], list[str]]:
    documents: dict[str, Any] = {}
    errors: list[str] = []
    package_root = package_dir.resolve()
    for definition, filename in DOCUMENTS.items():
        path = package_dir / filename
        if path.is_symlink():
            errors.append(f"{filename}: symlinked package documents are forbidden")
            continue
        if not path.is_file():
            errors.append(f"{filename}: missing required document")
            continue
        if not path.resolve().is_relative_to(package_root):
            errors.append(f"{filename}: package document escapes package root")
            continue
        try:
            documents[definition] = load_structured(path)
        except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
            errors.append(f"{filename}: cannot load document: {exc}")
    return documents, errors


def _validate_l0(
    package_dir: Path, schema_path: Path, documents: dict[str, Any], load_errors: list[str]
) -> list[str]:
    errors = list(load_errors)
    for definition, filename in DOCUMENTS.items():
        if definition in documents:
            errors.extend(
                f"{filename}:{error}"
                for error in validate_document(package_dir / filename, schema_path, definition)
            )
    if not load_errors and all(name in documents for name in DOCUMENTS):
        try:
            expected = calculate_digest(package_dir)
        except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
            errors.append(f"package digest cannot be calculated: {exc}")
        else:
            actual = documents["manifest"].get("contentDigest")
            if actual != expected:
                errors.append(
                    f"manifest.yaml:contentDigest: expected {expected}, actual {actual}"
                )
    return sorted(set(errors))


def _validate_rdf_projection(
    package_dir: Path, shapes_path: Path
) -> tuple[Graph | None, list[str]]:
    rdf_path = package_dir / "ontology.ttl"
    package_root = package_dir.resolve()
    if rdf_path.is_symlink():
        return None, ["ontology.ttl:rdf-containment: symlinked RDF projection is forbidden"]
    if not rdf_path.is_file():
        return None, ["ontology.ttl: missing required RDF projection"]
    if not rdf_path.resolve().is_relative_to(package_root):
        return None, ["ontology.ttl:rdf-containment: RDF projection escapes package root"]
    try:
        graph = Graph().parse(rdf_path, format="turtle")
        conforms, report = validate_rdf(rdf_path, shapes_path)
    except (OSError, ValueError, ParserError, BadSyntax, ReportableRuntimeError) as exc:
        return None, [f"ontology.ttl: invalid Turtle or SHACL input: {exc}"]
    if not conforms:
        return graph, [f"ontology.ttl: SHACL validation failed: {report}"]
    return graph, []


def _validate_rdf_profile(
    graph: Graph, schema: Any, documents: dict[str, Any]
) -> list[str]:
    profile = schema.get("x-rdf-projection-profile") if isinstance(schema, dict) else None
    if not isinstance(profile, dict) or profile.get("version") != "1.0":
        return ["ontology.ttl:rdf-parity/profile: missing versioned x-rdf-projection-profile"]
    collections = profile.get("collections")
    definitions = schema.get("$defs", {})
    if not isinstance(collections, list) or not collections:
        return ["ontology.ttl:rdf-parity/profile: collections must be a non-empty array"]
    expected: dict[str, dict[str, str]] = {}
    errors: list[str] = []

    def collect(owner: Any, owner_definition: str, collection: Any, location: str) -> None:
        if not isinstance(collection, dict):
            errors.append(f"ontology.ttl:rdf-parity/profile/{location}: collection must be an object")
            return
        path = collection.get("path")
        definition = collection.get("definition")
        rdf_class = collection.get("rdfClass")
        if not all(isinstance(item, str) for item in (path, definition, rdf_class)):
            errors.append(f"ontology.ttl:rdf-parity/profile/{location}: path, definition and rdfClass are required")
            return
        if definition not in definitions:
            errors.append(f"ontology.ttl:rdf-parity/profile/{location}: unknown definition {definition!r}")
            return
        try:
            item_ref = definitions[owner_definition]["properties"][path]["items"]["$ref"]
        except (KeyError, TypeError):
            errors.append(f"ontology.ttl:rdf-parity/profile/{location}: {owner_definition}.{path} is not a schema array")
            return
        if item_ref != f"#/$defs/{definition}":
            errors.append(
                f"ontology.ttl:rdf-parity/profile/{location}: {owner_definition}.{path} "
                f"does not reference {definition}"
            )
            return
        if not isinstance(owner, dict) or not isinstance(owner.get(path), list):
            errors.append(f"ontology.ttl:rdf-parity/profile/{location}: document path {path!r} is not an array")
            return
        bucket = expected.setdefault(rdf_class, {})
        for item in owner[path]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("label"), str):
                errors.append(f"ontology.ttl:rdf-parity/profile/{location}: projected items require id and label")
                continue
            bucket[item["id"]] = item["label"]
            for index, nested in enumerate(collection.get("nested", [])):
                collect(item, definition, nested, f"{location}/nested/{index}")

    for index, collection in enumerate(collections):
        document = collection.get("document") if isinstance(collection, dict) else None
        if document not in documents:
            errors.append(f"ontology.ttl:rdf-parity/profile/{index}: unknown document {document!r}")
            continue
        collect(documents[document], document, collection, str(index))
    if errors:
        return errors
    for rdf_class, expected_items in expected.items():
        actual: dict[str, str] = {}
        for node in graph.subjects(RDF.type, EBO[rdf_class]):
            ids = [str(value) for value in graph.objects(node, EBO.stableId)]
            labels = [str(value) for value in graph.objects(node, RDFS.label)]
            if len(ids) != 1 or len(labels) != 1:
                errors.append(f"ontology.ttl:rdf-parity/{rdf_class}: each projected node requires one stableId and label")
                continue
            actual[ids[0]] = labels[0]
        missing = sorted(set(expected_items) - set(actual))
        extra = sorted(set(actual) - set(expected_items))
        if missing:
            errors.append(f"ontology.ttl:rdf-parity/{rdf_class}: missing IDs {', '.join(missing)}")
        if extra:
            errors.append(f"ontology.ttl:rdf-parity/{rdf_class}: unexpected IDs {', '.join(extra)}")
        for identifier in sorted(set(expected_items) & set(actual)):
            if actual[identifier] != expected_items[identifier]:
                errors.append(
                    f"ontology.ttl:rdf-parity/{rdf_class}/{identifier}: label {actual[identifier]!r} "
                    f"does not match package label {expected_items[identifier]!r}"
                )
    return errors


def _validate_l1(
    package_dir: Path, schema_path: Path, shapes_path: Path, documents: dict[str, Any]
) -> tuple[Graph | None, list[str]]:
    errors = validate_references(documents)
    errors.extend(validate_claim_evidence_types(documents))
    graph, rdf_errors = _validate_rdf_projection(package_dir, shapes_path)
    errors.extend(rdf_errors)
    if graph is not None:
        try:
            schema = load_structured(schema_path)
        except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
            errors.append(f"ontology.ttl:rdf-parity/profile: cannot load schema: {exc}")
        else:
            errors.extend(_validate_rdf_profile(graph, schema, documents))
    return graph, sorted(set(errors))


def _validate_state_machines(documents: dict[str, Any]) -> list[str]:
    kinetics = documents.get("kinetics", {})
    object_ids = {
        item.get("id")
        for item in documents.get("semantics", {}).get("objectTypes", [])
        if isinstance(item, dict)
    }
    actions = [
        action for action in kinetics.get("actions", []) if isinstance(action, dict)
    ]
    action_by_id = {action.get("id"): action for action in actions}
    action_ids = {
        action.get("id")
        for action in actions
    }
    policies = documents.get("policies", {})
    authorization_ids = {
        item.get("id") for item in policies.get("authorizationPolicies", [])
        if isinstance(item, dict)
    }
    audit_ids = {
        item.get("id") for item in policies.get("auditPolicies", [])
        if isinstance(item, dict)
    }
    subject_states: dict[str, set[str]] = {}
    for machine in kinetics.get("stateMachines", []):
        if isinstance(machine, dict) and isinstance(machine.get("subjectRef"), str):
            subject_states.setdefault(machine["subjectRef"], set()).update(
                state.get("id") for state in machine.get("states", [])
                if isinstance(state, dict) and isinstance(state.get("id"), str)
            )
    errors: list[str] = []
    for index, action in enumerate(actions):
        action_id = action.get("id")
        for field in ("permissionRefs", "auditRefs"):
            if not action.get(field):
                errors.append(
                    f"kinetics.yaml:actions/{index}/{field}: action {action_id!r} "
                    f"requires at least one {field} entry"
                )
        if not action.get("effects"):
            errors.append(
                f"kinetics.yaml:actions/{index}/effects: action {action_id!r} has no effects"
            )
        if action.get("sideEffectRefs") and not action.get("compensationRefs"):
            errors.append(
                f"kinetics.yaml:actions/{index}/compensationRefs: action {action_id!r} "
                "with sideEffectRefs requires at least one compensation action"
            )
        for field, allowed, marker in (
            ("permissionRefs", authorization_ids, "permission-type"),
            ("auditRefs", audit_ids, "audit-type"),
            ("compensationRefs", action_ids, "compensation-type"),
        ):
            for reference in action.get(field, []):
                if reference not in allowed:
                    errors.append(
                        f"kinetics.yaml:{marker}/actions/{index}/{field}: action {action_id!r} "
                        f"reference {reference!r} has the wrong type"
                    )
        for contract_index, contract in enumerate(action.get("stateTransitions", [])):
            if not isinstance(contract, dict):
                continue
            subject_ref = contract.get("subjectRef")
            states = subject_states.get(subject_ref)
            if subject_ref not in object_ids or states is None:
                errors.append(
                    f"kinetics.yaml:transition-contract/actions/{index}/stateTransitions/{contract_index}: "
                    f"action {action_id!r} contract subject {subject_ref!r} has no StateMachine"
                )
                continue
            for field in ("fromStateRef", "toStateRef"):
                if contract.get(field) not in states:
                    errors.append(
                        f"kinetics.yaml:transition-contract/actions/{index}/stateTransitions/{contract_index}/{field}: "
                        f"action {action_id!r} contract state {contract.get(field)!r} is not in subject machine"
                    )
    for machine in kinetics.get("stateMachines", []):
        if not isinstance(machine, dict):
            continue
        machine_id = machine.get("id", "<unknown>")
        subject = machine.get("subjectRef")
        if subject not in object_ids:
            errors.append(
                f"kinetics.yaml:stateMachines/{machine_id}/subjectRef: machine "
                f"{machine_id!r} subjectRef {subject!r} must reference an ObjectType"
            )
        states = [state for state in machine.get("states", []) if isinstance(state, dict)]
        state_ids = {state.get("id") for state in states}
        initial = machine.get("initialStateRef")
        if not states:
            errors.append(f"kinetics.yaml: state machine {machine_id!r} has no states")
            continue
        if initial not in state_ids:
            errors.append(
                f"kinetics.yaml: state machine {machine_id!r} initial state {initial!r} is unknown"
            )
            reachable: set[object] = set()
        else:
            reachable = {initial}
        transitions = machine.get("transitions", [])
        for transition in transitions:
            if not isinstance(transition, dict):
                continue
            for field in ("fromRef", "toRef"):
                if transition.get(field) not in state_ids:
                    errors.append(
                        f"kinetics.yaml: state machine {machine_id!r} transition "
                        f"{transition.get('id')!r} has unknown {field} {transition.get(field)!r}"
                    )
            if transition.get("actionRef") not in action_ids:
                errors.append(
                    f"kinetics.yaml: state machine {machine_id!r} transition "
                    f"{transition.get('id')!r} has unknown Action {transition.get('actionRef')!r}"
                )
                continue
            action = action_by_id[transition.get("actionRef")]
            expected_contract = {
                "subjectRef": subject,
                "fromStateRef": transition.get("fromRef"),
                "toStateRef": transition.get("toRef"),
            }
            if expected_contract not in action.get("stateTransitions", []):
                errors.append(
                    f"kinetics.yaml:transition-contract/{transition.get('id')}: "
                    f"transition {transition.get('id')!r} action {transition.get('actionRef')!r} "
                    f"lacks exact stateTransitions tuple {expected_contract!r}"
                )
        changed = True
        while changed:
            changed = False
            for transition in transitions:
                if not isinstance(transition, dict):
                    continue
                if transition.get("fromRef") in reachable and transition.get("toRef") not in reachable:
                    reachable.add(transition.get("toRef"))
                    changed = True
        for state_id in sorted(item for item in state_ids - reachable if isinstance(item, str)):
            errors.append(
                f"kinetics.yaml: state machine {machine_id!r} has unreachable state {state_id!r}"
            )
    return errors


def _validate_l2(documents: dict[str, Any]) -> list[str]:
    errors = _validate_state_machines(documents)
    errors.extend(validate_claim_confidences(documents))
    return sorted(set(errors))


def _rdf_identity_errors(graph: Graph | None, documents: dict[str, Any]) -> list[str]:
    if graph is None:
        return []
    manifest = documents.get("manifest", {})
    ontology_nodes = list(graph.subjects(RDF.type, OWL.Ontology))
    if len(ontology_nodes) != 1:
        return [f"ontology.ttl: expected exactly one owl:Ontology, got {len(ontology_nodes)}"]
    ontology = ontology_nodes[0]
    fields = {
        "ontologyId": EBO.ontologyId,
        "ontologyVersion": EBO.ontologyVersion,
        "specVersion": EBO.specVersion,
        "contentDigest": EBO.contentDigest,
    }
    errors: list[str] = []
    for field, predicate in fields.items():
        values = [str(value) for value in graph.objects(ontology, predicate)]
        expected = manifest.get(field)
        if values != [expected]:
            errors.append(
                f"ontology.ttl:{field}: {values!r} does not match manifest.yaml:{field} {expected!r}"
            )
    return errors


def _validate_binding_evidence(documents: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    evidence_ids = {
        item.get("id")
        for item in documents.get("evidence", {}).get("evidenceRecords", [])
        if isinstance(item, dict)
    }
    errors: list[str] = []
    bindings = documents.get("bindings", {})
    semantic_kinetic_ids: set[str] = set()

    def collect_ids(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("id"), str):
                semantic_kinetic_ids.add(value["id"])
            for child in value.values():
                collect_ids(child)
        elif isinstance(value, list):
            for child in value:
                collect_ids(child)

    for document_name in ("semantics", "kinetics"):
        collect_ids(documents.get(document_name, {}))
    typed_ids: dict[str, set[str]] = {}

    def collect_profile(owner: Any, collection: Any) -> None:
        if not isinstance(owner, dict) or not isinstance(collection, dict):
            return
        path = collection.get("path")
        rdf_class = collection.get("rdfClass")
        if not isinstance(path, str) or not isinstance(rdf_class, str):
            return
        for item in owner.get(path, []):
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("id"), str):
                typed_ids.setdefault(rdf_class, set()).add(item["id"])
            for nested in collection.get("nested", []):
                collect_profile(item, nested)

    for collection in schema.get("x-rdf-projection-profile", {}).get("collections", []):
        if isinstance(collection, dict):
            collect_profile(documents.get(collection.get("document"), {}), collection)
    for collection in ("dataBindings", "apiBindings", "codeBindings", "eventBindings"):
        for binding_index, binding in enumerate(bindings.get(collection, [])):
            if not isinstance(binding, dict):
                continue
            allowed_classes = BINDING_TARGET_CLASSES[collection]
            allowed_targets = set().union(
                *(typed_ids.get(class_name, set()) for class_name in allowed_classes)
            )
            if binding.get("targetRef") not in allowed_targets:
                errors.append(
                    f"bindings.yaml:binding-target-type/{collection}/{binding_index}/targetRef: "
                    f"binding {binding.get('id')!r} targetRef {binding.get('targetRef')!r} "
                    f"must reference {', '.join(sorted(allowed_classes))}"
                )
            refs = binding.get("evidenceRefs", [])
            if not refs:
                errors.append(f"bindings.yaml: {binding.get('id')!r} has no evidenceRefs")
            for reference in refs:
                if reference not in evidence_ids:
                    errors.append(
                        f"bindings.yaml: {binding.get('id')!r} evidenceRef {reference!r} is not traceable"
                    )
            for mapping_index, mapping in enumerate(binding.get("mappings", [])):
                if isinstance(mapping, dict) and mapping.get("ontologyPath") not in semantic_kinetic_ids:
                    errors.append(
                        f"bindings.yaml:binding-path/{collection}/{binding_index}/mappings/{mapping_index}/ontologyPath: "
                        f"binding {binding.get('id')!r} ontologyPath {mapping.get('ontologyPath')!r} is unresolved"
                    )
    return errors


def _validate_l3(
    package_dir: Path,
    schema_path: Path,
    documents: dict[str, Any],
    graph: Graph | None,
) -> list[str]:
    errors: list[str] = []
    try:
        schema = load_structured(schema_path)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return [f"<schema>: cannot load schema: {exc}"]
    profile, profile_errors = validate_traceability_profile(schema)
    errors.extend(profile_errors)
    if profile is not None:
        errors.extend(validate_traceability_coverage(documents, profile))
        expected_approvals = _accepted_traceable_ids(documents, profile)
        approved: set[str] = set()
        for approval in documents.get("evidence", {}).get("approvals", []):
            if isinstance(approval, dict) and approval.get("decision") == "approved":
                approved.update(approval.get("approvedElementRefs", []))
        if missing_approvals := sorted(expected_approvals - approved):
            errors.append(
                "evidence.yaml:approval-coverage: approval 'release' is missing accepted "
                f"elements: {', '.join(missing_approvals)}"
            )
    errors.extend(validate_traceability_identity(documents))
    errors.extend(validate_traceability_evidence_types(documents))
    errors.extend(validate_documentation_refs(documents, schema_path.resolve().parents[2]))
    errors.extend(_validate_binding_evidence(documents, schema))
    errors.extend(
        f"migrations.yaml:{error}"
        for error in validate_package_migrations(documents.get("migrations", {}))
    )
    errors.extend(_rdf_identity_errors(graph, documents))

    policies = documents.get("policies", {})
    for collection in (
        "authorizationPolicies", "auditPolicies", "qualityPolicies", "compliancePolicies"
    ):
        if not policies.get(collection):
            errors.append(f"policies.yaml:{collection}: at least one policy is required for release")

    if all(name in documents for name in DOCUMENTS):
        expected = calculate_digest(package_dir)
        trace_digest = documents["traceability"].get("sourceDigest")
        if trace_digest != expected:
            errors.append(
                f"traceability.yaml:sourceDigest: expected {expected}, actual {trace_digest}"
            )
    return sorted(set(errors))


def validate_release(
    package_dir: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    shapes_path: Path = DEFAULT_SHAPES,
) -> ReleaseReport:
    documents, load_errors = _load_documents(package_dir)
    manifest = documents.get("manifest", {})
    l0 = _validate_l0(package_dir, schema_path, documents, load_errors)
    if l0:
        return ReleaseReport(
            ontology_id=manifest.get("ontologyId") if isinstance(manifest, dict) else None,
            ontology_version=manifest.get("ontologyVersion") if isinstance(manifest, dict) else None,
            levels=[
                _level("L0", l0),
                _blocked("L1"),
                _blocked("L2"),
                _blocked("L3-static"),
            ],
        )
    graph, l1 = _validate_l1(package_dir, schema_path, shapes_path, documents)
    if l1:
        return ReleaseReport(
            ontology_id=manifest.get("ontologyId") if isinstance(manifest, dict) else None,
            ontology_version=manifest.get("ontologyVersion") if isinstance(manifest, dict) else None,
            levels=[_level("L0", []), _level("L1", l1), _blocked("L2"), _blocked("L3-static")],
        )
    l2 = _validate_l2(documents)
    if l2:
        return ReleaseReport(
            ontology_id=manifest.get("ontologyId") if isinstance(manifest, dict) else None,
            ontology_version=manifest.get("ontologyVersion") if isinstance(manifest, dict) else None,
            levels=[_level("L0", []), _level("L1", []), _level("L2", l2), _blocked("L3-static")],
        )
    l3 = _validate_l3(package_dir, schema_path, documents, graph)
    return ReleaseReport(
        ontology_id=manifest.get("ontologyId") if isinstance(manifest, dict) else None,
        ontology_version=manifest.get("ontologyVersion") if isinstance(manifest, dict) else None,
        levels=[
            _level("L0", l0),
            _level("L1", l1),
            _level("L2", l2),
            _level("L3-static", l3),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a static ontology release without live connectors"
    )
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--shapes", type=Path, default=DEFAULT_SHAPES)
    args = parser.parse_args(argv)
    report = validate_release(args.package_dir, args.schema, args.shapes)
    if report.passed:
        print(f"PASS {report.ontology_id}@{report.ontology_version} L0-L3-static")
        return 0
    for result in report.levels:
        if result.status == "blocked":
            print(f"level={result.level} status=blocked")
            continue
        for finding in result.findings:
            print(
                f"level={result.level} class={finding.error_class} "
                f"rule={finding.rule} path={json.dumps(finding.path)} "
                f"element={json.dumps(finding.element_id)} "
                f"message={json.dumps(finding.message)} fix={json.dumps(finding.fix)}"
            )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
