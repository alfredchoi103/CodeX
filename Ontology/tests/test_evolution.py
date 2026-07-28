from copy import deepcopy
from pathlib import Path
import shutil

import pytest
import yaml

from scripts.evolution import (
    classify_change,
    collect_accepted_stable_ids,
    parse_semver,
    required_bump,
    validate_evolution,
    validate_lineage,
    validate_migration,
    validate_version_bump,
)
from scripts.validate_package import load_structured, validate_document, validate_package


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "spec/v1/ontology-package.schema.json"
EVOLUTION = ROOT / "examples/evolution"


@pytest.mark.parametrize(
    "operations, expected",
    [
        ([{"operation": "metadata"}], "patch"),
        ([{"operation": "add"}], "minor"),
        ([{"operation": "metadata"}, {"operation": "add"}], "minor"),
        ([{"operation": "add"}, {"operation": "split"}], "major"),
    ],
)
def test_change_classification_uses_highest_impact(
    operations: list[dict[str, str]], expected: str
) -> None:
    assert classify_change(operations) == expected
    assert required_bump(operations) == expected


@pytest.mark.parametrize(
    "operation", ["rename", "retype", "split", "merge", "relink", "supersede", "retract"]
)
def test_correction_operations_default_to_major(operation: str) -> None:
    assert classify_change([{"operation": operation}]) == "major"


def test_explicit_compatibility_cannot_understate_operation() -> None:
    assert classify_change([{"operation": "split", "compatibility": "patch"}]) == "major"


def test_rename_alias_proof_may_reduce_impact_to_minor() -> None:
    proof = {
        "stableIdPreserved": True,
        "consumerIdentifiersUnchanged": True,
        "evidenceRefs": ["evidence.alias-review"],
    }
    rename = {
        "operation": "rename",
        "originalDefinition": {"id": "Actor", "label": "Actor"},
        "newDefinition": {"id": "Actor", "label": "Party"},
    }
    assert classify_change([{**rename, "aliasProof": proof}]) == "minor"
    assert classify_change([{**rename, "aliasProof": dict(proof, stableIdPreserved=False)}]) == "major"
    assert classify_change([{**rename, "aliasProof": {"stableIdPreserved": True, "consumerIdentifiersUnchanged": True, "evidenceRefs": []}}]) == "major"
    assert classify_change([{**rename, "operation": "retype", "aliasProof": proof}]) == "major"


@pytest.mark.parametrize(
    "before, after, bump",
    [("1.2.3", "1.2.4", "patch"), ("1.2.3", "1.3.0", "minor"), ("1.2.3", "2.0.0", "major")],
)
def test_semver_bump_accepts_exact_required_boundary(before: str, after: str, bump: str) -> None:
    assert validate_version_bump(before, after, bump) == []


@pytest.mark.parametrize(
    "before, after, bump",
    [
        ("1.2.3", "1.2.3", "patch"),
        ("1.2.3", "1.2.2", "patch"),
        ("1.2.3", "1.3.0", "patch"),
        ("1.2.3", "2.0.0", "minor"),
        ("2.0.0", "1.0.0", "major"),
    ],
)
def test_semver_bump_rejects_noop_downgrade_and_wrong_boundary(
    before: str, after: str, bump: str
) -> None:
    assert validate_version_bump(before, after, bump)


def test_parse_semver_accepts_only_three_number_core() -> None:
    assert parse_semver("12.3.40") == (12, 3, 40)
    for invalid in ("1.0", "v1.0.0", "1.0.0-alpha", "1.0.0+build", "01.0.0"):
        with pytest.raises(ValueError):
            parse_semver(invalid)


def test_collect_accepted_ids_honors_inherited_and_explicit_lifecycle() -> None:
    documents = {
        "manifest": {"status": "accepted"},
        "semantics": {
            "objectTypes": [
                {"id": "Accepted", "properties": [{"id": "Accepted.id"}]},
                {
                    "id": "Retracted",
                    "status": "retracted",
                    "properties": [{"id": "Retracted.id"}],
                },
            ],
            "links": [],
            "interfaces": [],
            "invariants": [],
            "businessTerms": [],
        },
        "kinetics": {"actions": [], "queries": [], "stateMachines": [], "domainEvents": []},
        "policies": {
            "authorizationPolicies": [],
            "auditPolicies": [],
            "qualityPolicies": [],
            "compliancePolicies": [],
        },
    }
    assert collect_accepted_stable_ids(documents) == {"Accepted", "Accepted.id"}


def _valid_migration() -> dict:
    return {
        "fromVersion": "1.0.0",
        "toVersion": "2.0.0",
        "changes": [
            {
                "id": "change.actor-split",
                "operation": "split",
                "compatibility": "major",
                "predecessorRefs": ["Actor"],
                "successorRefs": ["Person", "Organization"],
                "originalDefinition": {"kind": "objectType", "id": "Actor"},
                "newDefinition": {"kind": "objectTypes", "ids": ["Person", "Organization"]},
                "errorCause": "Conflicting evidence showed that Actor conflated people and organizations.",
                "evidenceRefs": ["evidence.actor-conflict"],
                "impactAnalysis": {
                    "data": ["actor rows require deterministic classification"],
                    "api": ["actor payload becomes person or organization"],
                    "action": [],
                    "query": ["actor queries use a compatibility view"],
                    "policy": [],
                    "document": ["glossary references change"],
                    "audit": ["historic Actor IDs remain resolvable"],
                    "consumers": ["identity service"],
                },
                "migrationStrategy": ["coexist", "dual-read", "backfill"],
                "backfill": "Classify Actor rows from organization registration evidence.",
                "rollback": {
                    "procedure": ["Restore reads from the immutable v1 snapshot."],
                    "triggerConditions": ["Mismatch rate exceeds the approved threshold."],
                    "verificationSteps": ["Verify legacy Actor lookup and audit continuity."],
                },
                "compatibilityWindow": "2026-08-01/2026-10-31",
                "dualRead": {"enabled": True, "description": "Compare v1 and v2 resolution."},
                "dualWrite": {"enabled": False, "description": "Avoid divergent authoritative writes."},
                "acceptanceEvidence": ["test://evolution/actor-split"],
            }
        ],
        "lineage": [
            {"predecessorRefs": ["Actor"], "successorRefs": ["Person", "Organization"], "operation": "split"}
        ],
    }


def test_breaking_migration_requires_complete_operational_safety_record() -> None:
    baseline = _valid_migration()
    assert validate_migration(baseline) == []
    required = (
        "impactAnalysis",
        "migrationStrategy",
        "backfill",
        "rollback",
        "compatibilityWindow",
        "acceptanceEvidence",
        "dualRead",
        "dualWrite",
        "originalDefinition",
        "newDefinition",
    )
    for field in required:
        candidate = deepcopy(baseline)
        del candidate["changes"][0][field]
        assert any(f"changes/0/{field}" in error for error in validate_migration(candidate))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda migration: [],
        lambda migration: {**migration, "changes": [1]},
        lambda migration: {
            **migration,
            "changes": [{**migration["changes"][0], "predecessorRefs": True}],
        },
    ],
)
def test_validate_evolution_returns_schema_errors_for_malformed_migrations(mutate) -> None:
    errors = validate_evolution(
        EVOLUTION / "v1", EVOLUTION / "v2", mutate(_valid_migration())
    )
    assert errors
    assert any(error.startswith("migration.yaml:") for error in errors)


def test_same_ontology_version_always_requires_a_new_release() -> None:
    manifest = {
        "ontologyId": "org.example.identity",
        "ontologyVersion": "1.0.0",
        "contentDigest": "sha256:" + "1" * 64,
    }
    migration = _valid_migration()
    migration.update(fromVersion="1.0.0", toVersion="1.0.0")
    errors = validate_evolution(manifest, dict(manifest), migration)
    assert "version: same ontologyVersion is forbidden; a new release is required" in errors


def test_retract_requires_cause_evidence_and_impact() -> None:
    candidate = _valid_migration()
    change = candidate["changes"][0]
    change.update(operation="retract", successorRefs=[])
    for field in ("errorCause", "evidenceRefs", "impactAnalysis"):
        invalid = deepcopy(candidate)
        del invalid["changes"][0][field]
        assert any(f"changes/0/{field}" in error for error in validate_migration(invalid))


def test_lineage_preserves_rename_identity_and_split_merge_edges() -> None:
    old_ids = {"Stable", "Actor", "LegacyPerson", "LegacyOrg"}
    new_ids = {"Stable", "Person", "Organization", "Party"}
    changes = [
        {"operation": "rename", "predecessorRefs": ["Stable"], "successorRefs": ["Stable"]},
        {"operation": "split", "predecessorRefs": ["Actor"], "successorRefs": ["Person", "Organization"]},
        {"operation": "merge", "predecessorRefs": ["LegacyPerson", "LegacyOrg"], "successorRefs": ["Party"]},
    ]
    lineage = [
        {"operation": "rename", "predecessorRefs": ["Stable"], "successorRefs": ["Stable"]},
        {"operation": "split", "predecessorRefs": ["Actor"], "successorRefs": ["Person", "Organization"]},
        {"operation": "merge", "predecessorRefs": ["LegacyPerson", "LegacyOrg"], "successorRefs": ["Party"]},
    ]
    assert validate_lineage(old_ids, new_ids, changes, lineage) == []


def test_accepted_disappearance_requires_successor_or_retract() -> None:
    errors = validate_lineage({"Actor"}, set(), [], [])
    assert errors == ["lineage: accepted element 'Actor' disappeared without successor or retract"]


def test_pure_retract_lineage_has_nonempty_predecessors_and_no_successor() -> None:
    changes = [{"operation": "retract", "predecessorRefs": ["Actor"], "successorRefs": []}]
    lineage = [{"operation": "retract", "predecessorRefs": ["Actor"], "successorRefs": []}]
    assert validate_lineage({"Actor"}, set(), changes, lineage) == []
    assert any("predecessorRefs" in error for error in validate_lineage({"Actor"}, set(), changes, [{"operation": "retract", "predecessorRefs": [], "successorRefs": []}]))
    assert any("successorRefs" in error for error in validate_lineage({"Actor"}, {"Replacement"}, changes, [{"operation": "retract", "predecessorRefs": ["Actor"], "successorRefs": ["Replacement"]}]))


def test_lineage_rejects_duplicate_edges_and_shared_change_coverage() -> None:
    change = {"operation": "retype", "predecessorRefs": ["Old"], "successorRefs": ["New"]}
    edge = {"operation": "retype", "predecessorRefs": ["Old"], "successorRefs": ["New"]}
    duplicate_edge_errors = validate_lineage({"Old"}, {"New"}, [change], [edge, deepcopy(edge)])
    assert any("duplicate lineage" in error for error in duplicate_edge_errors)
    duplicate_change_errors = validate_lineage({"Old"}, {"New"}, [change, deepcopy(change)], [edge])
    assert any("one-to-one" in error for error in duplicate_change_errors)


def test_lineage_rejects_extra_edge_without_matching_correction_change() -> None:
    edge = {
        "operation": "retype",
        "predecessorRefs": ["Old"],
        "successorRefs": ["New"],
    }
    errors = validate_lineage({"Old"}, {"New"}, [], [edge])
    assert any("lineage/0" in error and "matching correction change" in error for error in errors)


@pytest.mark.parametrize(
    "lineage",
    [
        [{"operation": "retype", "predecessorRefs": ["A"], "successorRefs": ["A"]}],
        [
            {"operation": "retype", "predecessorRefs": ["A"], "successorRefs": ["B"]},
            {"operation": "retype", "predecessorRefs": ["B"], "successorRefs": ["A"]},
        ],
    ],
)
def test_lineage_rejects_directed_cycles(lineage: list[dict]) -> None:
    assert any("cycle" in error for error in validate_lineage({"A", "B"}, {"A", "B"}, [], lineage))


def test_published_version_is_immutable_by_version_and_digest() -> None:
    v1 = {"ontologyId": "org.example", "ontologyVersion": "1.0.0", "contentDigest": "sha256:" + "1" * 64}
    modified = dict(v1, contentDigest="sha256:" + "2" * 64)
    migration = _valid_migration()
    migration.update(fromVersion="1.0.0", toVersion="1.0.0")
    errors = validate_evolution(v1, modified, migration)
    assert any("immutable" in error and "contentDigest" in error for error in errors)


def test_evolution_rejects_change_refs_outside_the_two_versions() -> None:
    migration = load_structured(EVOLUTION / "migration.yaml")
    migration["changes"][0]["predecessorRefs"] = ["MissingOld"]
    migration["changes"][0]["successorRefs"] = ["MissingNew"]
    migration["changes"][0]["evidenceRefs"] = ["evidence.missing"]
    errors = validate_evolution(EVOLUTION / "v1", EVOLUTION / "v2", migration)
    assert "migration.yaml:changes/0/predecessorRefs/0: unknown v1 reference 'MissingOld'" in errors
    assert "migration.yaml:changes/0/successorRefs/0: unknown v2 reference 'MissingNew'" in errors
    assert "migration.yaml:changes/0/evidenceRefs/0: unknown cross-version evidence 'evidence.missing'" in errors


@pytest.mark.parametrize("operation", ["split", "relink", "retract"])
def test_breaking_change_requires_independent_matching_lineage(operation: str) -> None:
    migration = load_structured(EVOLUTION / "migration.yaml")
    migration["lineage"] = [entry for entry in migration["lineage"] if entry["operation"] != operation]
    errors = validate_evolution(EVOLUTION / "v1", EVOLUTION / "v2", migration)
    assert any(
        error.startswith("migration.yaml:changes/") and "matching lineage" in error
        for error in errors
    )


def test_alias_proof_evidence_must_exist_across_versions() -> None:
    migration = load_structured(EVOLUTION / "migration.yaml")
    migration["changes"][0]["operation"] = "rename"
    migration["changes"][0]["predecessorRefs"] = ["Actor"]
    migration["changes"][0]["successorRefs"] = ["Actor"]
    migration["changes"][0]["compatibility"] = "minor"
    migration["changes"][0]["aliasProof"] = {
        "stableIdPreserved": True,
        "consumerIdentifiersUnchanged": True,
        "evidenceRefs": ["evidence.missing-alias-proof"],
    }
    errors = validate_evolution(EVOLUTION / "v1", EVOLUTION / "v2", migration)
    assert "migration.yaml:changes/0/aliasProof/evidenceRefs/0: unknown cross-version evidence 'evidence.missing-alias-proof'" in errors


def test_validate_evolution_enforces_closed_migration_schema() -> None:
    migration = load_structured(EVOLUTION / "migration.yaml")
    migration["changes"][0]["unreviewedEscapeHatch"] = True
    errors = validate_evolution(EVOLUTION / "v1", EVOLUTION / "v2", migration)
    assert any(
        error.startswith("migration.yaml:changes/0:")
        and "unreviewedEscapeHatch" in error
        for error in errors
    )


def test_retract_predecessor_must_remain_retracted_in_target_package(tmp_path: Path) -> None:
    target = tmp_path / "v2"
    shutil.copytree(EVOLUTION / "v2", target)
    semantics = load_structured(target / "semantics.yaml")
    actor = next(item for item in semantics["objectTypes"] if item["id"] == "Actor")
    actor["properties"] = [
        item for item in actor["properties"] if item["id"] != "Actor.actorId"
    ]
    (target / "semantics.yaml").write_text(
        yaml.safe_dump(semantics, sort_keys=False), encoding="utf-8"
    )
    errors = validate_evolution(EVOLUTION / "v1", target, EVOLUTION / "migration.yaml")
    assert "migration.yaml:changes/2/predecessorRefs/0: retract predecessor 'Actor.actorId' must remain in v2 with lifecycle retracted" in errors


def test_lineage_only_retract_cannot_bypass_change_evidence_or_history(
    tmp_path: Path,
) -> None:
    target = tmp_path / "v2"
    shutil.copytree(EVOLUTION / "v2", target)
    semantics = load_structured(target / "semantics.yaml")
    actor = next(item for item in semantics["objectTypes"] if item["id"] == "Actor")
    actor["properties"] = [
        item for item in actor["properties"] if item["id"] != "Actor.actorId"
    ]
    (target / "semantics.yaml").write_text(
        yaml.safe_dump(semantics, sort_keys=False), encoding="utf-8"
    )
    migration = load_structured(EVOLUTION / "migration.yaml")
    migration["changes"] = [
        change for change in migration["changes"] if change["operation"] != "retract"
    ]
    errors = validate_evolution(EVOLUTION / "v1", target, migration)
    assert any("lineage/4" in error and "matching correction change" in error for error in errors)
    assert any("lineage/4" in error and "must remain in v2" in error for error in errors)


def _actual_alias_evolution(tmp_path: Path, change_property_type: bool) -> tuple[Path, dict]:
    target = tmp_path / "v1.1"
    shutil.copytree(EVOLUTION / "v1", target)
    manifest = load_structured(target / "manifest.yaml")
    manifest["ontologyVersion"] = "1.1.0"
    (target / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    traceability = load_structured(target / "traceability.yaml")
    traceability["ontologyVersion"] = "1.1.0"
    (target / "traceability.yaml").write_text(
        yaml.safe_dump(traceability, sort_keys=False), encoding="utf-8"
    )

    old_semantics = load_structured(EVOLUTION / "v1/semantics.yaml")
    old_actor = deepcopy(next(item for item in old_semantics["objectTypes"] if item["id"] == "Actor"))
    semantics = load_structured(target / "semantics.yaml")
    actor = next(item for item in semantics["objectTypes"] if item["id"] == "Actor")
    actor["label"] = "Identity party"
    reported_new_actor = deepcopy(actor)
    if change_property_type:
        given_name = next(item for item in actor["properties"] if item["id"] == "Actor.givenName")
        given_name["valueType"] = {"kind": "primitive", "primitive": "integer"}
    (target / "semantics.yaml").write_text(
        yaml.safe_dump(semantics, sort_keys=False), encoding="utf-8"
    )

    migration = _valid_migration()
    migration.update(fromVersion="1.0.0", toVersion="1.1.0")
    change = migration["changes"][0]
    change.update(
        id="change.actor-label",
        operation="rename",
        compatibility="minor",
        predecessorRefs=["Actor"],
        successorRefs=["Actor"],
        originalDefinition=old_actor,
        newDefinition=reported_new_actor,
        evidenceRefs=["evidence.v1-model"],
        aliasProof={
            "stableIdPreserved": True,
            "consumerIdentifiersUnchanged": True,
            "evidenceRefs": ["evidence.v1-model"],
        },
    )
    migration["lineage"] = [
        {"operation": "rename", "predecessorRefs": ["Actor"], "successorRefs": ["Actor"]}
    ]
    return target, migration


def test_alias_minor_is_bound_to_actual_package_display_diff(tmp_path: Path) -> None:
    target, migration = _actual_alias_evolution(tmp_path, change_property_type=False)
    assert validate_evolution(EVOLUTION / "v1", target, migration) == []


def test_alias_cannot_hide_actual_property_type_change(tmp_path: Path) -> None:
    target, migration = _actual_alias_evolution(tmp_path, change_property_type=True)
    errors = validate_evolution(EVOLUTION / "v1", target, migration)
    assert any("newDefinition" in error and "actual v2 definition" in error for error in errors)
    assert any("actual package diff is not display-only" in error for error in errors)


def test_validate_document_rejects_definition_pointer_injection(tmp_path: Path) -> None:
    candidate = tmp_path / "document.yaml"
    candidate.write_text("value: harmless\n", encoding="utf-8")
    assert validate_document(candidate, SCHEMA, "manifest/../evidence") == [
        "<schema>: unknown definition 'manifest/../evidence'"
    ]


def test_rename_alias_proof_requires_a_real_display_only_diff() -> None:
    proof = {
        "stableIdPreserved": True,
        "consumerIdentifiersUnchanged": True,
        "evidenceRefs": ["evidence.alias-review"],
    }
    valid = {
        "operation": "rename",
        "originalDefinition": {"id": "Actor", "label": "Actor", "descriptions": {"en": "Old"}},
        "newDefinition": {"id": "Actor", "label": "Party", "descriptions": {"en": "New"}},
        "aliasProof": proof,
    }
    assert classify_change([valid]) == "minor"
    for new_definition in (
        valid["originalDefinition"],
        {"id": "Actor", "label": "Party", "properties": [{"id": "Actor.kind"}]},
        {"ids": ["Person", "Organization"], "label": "Party"},
    ):
        invalid = {**valid, "newDefinition": new_definition}
        assert classify_change([invalid]) == "major"

    misclassified = _valid_migration()
    misclassified["changes"][0].update(
        operation="rename",
        compatibility="minor",
        predecessorRefs=["Actor"],
        successorRefs=["Actor"],
        originalDefinition={"id": "Actor", "properties": ["old"]},
        newDefinition={"id": "Actor", "properties": ["new"]},
        aliasProof=proof,
    )
    assert any("misclassified alias" in error for error in validate_migration(misclassified))


def test_rollback_and_enabled_dual_write_require_operational_safety() -> None:
    invalid_rollback = _valid_migration()
    invalid_rollback["changes"][0]["rollback"] = "restore it"
    assert any("rollback" in error for error in validate_migration(invalid_rollback))

    enabled = _valid_migration()
    enabled["changes"][0]["dualWrite"] = {
        "enabled": True,
        "description": "Temporary synchronized writes.",
    }
    errors = validate_migration(enabled)
    assert any("idempotencyKey" in error for error in errors)
    assert any("temporary-dual-write" in error for error in errors)

    enabled["changes"][0]["dualWrite"].update(
        idempotencyKey="actorMigrationId",
        ordering="old-before-new with monotonic sequence",
        conflictAuthority="v2 identity registry",
        stopConditions=["Any divergent identity ownership is observed."],
    )
    enabled["changes"][0]["migrationStrategy"].append("temporary-dual-write")
    assert validate_migration(enabled) == []


@pytest.mark.parametrize("version", ["1.0.0-alpha", "1.0.0+build"])
def test_ontology_versions_use_core_semver_in_schema(tmp_path: Path, version: str) -> None:
    manifest = load_structured(EVOLUTION / "v1/manifest.yaml")
    manifest["ontologyVersion"] = version
    candidate = tmp_path / "manifest.yaml"
    candidate.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    assert validate_document(candidate, SCHEMA, "manifest")

    migration = _valid_migration()
    migration["fromVersion"] = version
    candidate.write_text(yaml.safe_dump(migration, sort_keys=False), encoding="utf-8")
    assert validate_document(candidate, SCHEMA, "evolutionMigration")


def test_v1_v2_packages_and_migration_form_a_valid_evolution() -> None:
    v1 = EVOLUTION / "v1"
    v2 = EVOLUTION / "v2"
    migration = EVOLUTION / "migration.yaml"
    assert validate_package(v1, SCHEMA) == []
    assert validate_package(v2, SCHEMA) == []
    assert validate_document(migration, SCHEMA, "evolutionMigration") == []
    assert validate_evolution(v1, v2, migration) == []


def test_evolution_migration_schema_requires_machine_versions_and_closed_impacts(
    tmp_path: Path,
) -> None:
    import yaml

    valid = _valid_migration()
    candidate = tmp_path / "migration.yaml"
    candidate.write_text(yaml.safe_dump(valid, sort_keys=False), encoding="utf-8")
    assert validate_document(candidate, SCHEMA, "evolutionMigration") == []

    del valid["fromVersion"]
    valid["changes"][0]["impactAnalysis"]["unknown"] = []
    candidate.write_text(yaml.safe_dump(valid, sort_keys=False), encoding="utf-8")
    errors = validate_document(candidate, SCHEMA, "evolutionMigration")
    assert any("fromVersion" in error for error in errors)
    assert any("unknown" in error for error in errors)


def test_change_schema_exposes_all_correction_operations() -> None:
    schema = load_structured(SCHEMA)
    assert schema["$defs"]["change"]["properties"]["operation"]["enum"] == [
        "add",
        "metadata",
        "rename",
        "retype",
        "split",
        "merge",
        "relink",
        "supersede",
        "retract",
    ]
    assert schema["$defs"]["change"]["properties"]["compatibility"]["enum"] == [
        "patch",
        "minor",
        "major",
    ]


def test_lineage_schema_requires_plural_edges_and_allows_empty_successors_only_for_retract(
    tmp_path: Path,
) -> None:
    import yaml

    migration = _valid_migration()
    candidate = tmp_path / "migration.yaml"
    migration["lineage"] = [
        {"operation": "retract", "predecessorRefs": ["Actor"], "successorRefs": []}
    ]
    candidate.write_text(yaml.safe_dump(migration, sort_keys=False), encoding="utf-8")
    assert validate_document(candidate, SCHEMA, "evolutionMigration") == []

    migration["lineage"][0]["predecessorRefs"] = []
    migration["lineage"][0]["successorRefs"] = ["Person"]
    candidate.write_text(yaml.safe_dump(migration, sort_keys=False), encoding="utf-8")
    errors = validate_document(candidate, SCHEMA, "evolutionMigration")
    assert any("predecessorRefs" in error for error in errors)
    assert any("successorRefs" in error for error in errors)


def test_alias_proof_schema_is_closed_and_requires_true_flags_and_internal_evidence(
    tmp_path: Path,
) -> None:
    import yaml

    migration = _valid_migration()
    change = migration["changes"][0]
    change["operation"] = "rename"
    change["compatibility"] = "minor"
    change["successorRefs"] = ["Actor"]
    change["aliasProof"] = {
        "stableIdPreserved": True,
        "consumerIdentifiersUnchanged": True,
        "evidenceRefs": ["evidence.actor-conflict"],
    }
    candidate = tmp_path / "migration.yaml"
    candidate.write_text(yaml.safe_dump(migration, sort_keys=False), encoding="utf-8")
    assert validate_document(candidate, SCHEMA, "evolutionMigration") == []

    change["aliasProof"]["stableIdPreserved"] = False
    change["aliasProof"]["unknown"] = True
    candidate.write_text(yaml.safe_dump(migration, sort_keys=False), encoding="utf-8")
    errors = validate_document(candidate, SCHEMA, "evolutionMigration")
    assert any("stableIdPreserved" in error for error in errors)
    assert any("unknown" in error for error in errors)


def test_evolution_examples_retain_error_history_instead_of_silent_deletion() -> None:
    v1_semantics = load_structured(EVOLUTION / "v1/semantics.yaml")
    v2_semantics = load_structured(EVOLUTION / "v2/semantics.yaml")
    v1_ids = {item["id"] for item in v1_semantics["objectTypes"] + v1_semantics["links"]}
    v2_by_id = {item["id"]: item for item in v2_semantics["objectTypes"] + v2_semantics["links"]}
    assert {"Actor", "Actor.relatedTo.Actor"} <= v1_ids
    assert v2_by_id["Actor"]["status"] == "retracted"
    assert v2_by_id["Actor.relatedTo.Actor"]["status"] == "retracted"
