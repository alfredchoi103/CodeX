# Executable Business Ontology MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a coherent Chinese-first Ontology standard with machine-readable JSON Schema and SHACL, forward/reverse methodology, explainable discovery claims, versioned correction rules, and validated examples.

**Architecture:** Treat an immutable Ontology Package as the single source of truth and derive documentation, semantic-web, and future runtime projections from it. Keep the normative schema, SHACL constraints, examples, and prose synchronized through automated validation and traceability tests.

**Tech Stack:** Markdown, YAML 1.2, JSON Schema Draft 2020-12, RDF/Turtle, OWL 2, SHACL, Python 3.11+, pytest, jsonschema, PyYAML, RDFLib, pySHACL.

---

## File map

| Path | Responsibility |
|---|---|
| `README.md` | Project purpose, quick start, navigation, scope and validation command |
| `pyproject.toml` | Validation tool and test dependencies |
| `docs/index.md` | Ordered documentation map and reading paths |
| `docs/architecture.md` | Four-layer architecture and single-source/multi-projection model |
| `docs/metamodel.md` | Normative semantic, kinetic, binding and governance element reference |
| `docs/forward-engineering.md` | Ontology-to-system construction method and traceability contract |
| `docs/reverse-engineering.md` | System-to-candidate-Ontology evidence fusion method |
| `docs/discovery-confidence.md` | DiscoveryClaim, explainability, confidence and falsification standard |
| `docs/evolution-governance.md` | Version, proposal, correction, migration and optimization process |
| `docs/conformance.md` | L0–L3 validation, quality gates and acceptance checklist |
| `docs/interoperability.md` | Palantir, Microsoft, RDF/OWL, SHACL and OpenAPI concept mappings |
| `spec/v1/ontology-package.schema.json` | Normative structure for all seven package documents |
| `spec/v1/ontology.shacl.ttl` | Normative graph-semantic constraints |
| `examples/service-operations/` | Complete cross-industry neutral Ontology Package |
| `examples/discovery/` | Evidence Graph and A–D DiscoveryClaim examples |
| `examples/evolution/` | Erroneous v1, corrected v2 and lineage/migration example |
| `scripts/validate_package.py` | Package loading, JSON Schema validation, digest and report logic |
| `scripts/validate_rdf.py` | RDF parsing and SHACL validation logic |
| `tests/test_schema.py` | Valid and invalid package structure tests |
| `tests/test_discovery.py` | Confidence calculation and claim completeness tests |
| `tests/test_evolution.py` | Version, correction and lineage tests |
| `tests/test_docs.py` | Documentation navigation, terminology and traceability tests |
| `tests/test_shacl.py` | Valid and invalid RDF graph validation tests |

## Task 1: Establish the validation harness and package skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `scripts/__init__.py`
- Create: `scripts/validate_package.py`
- Create: `tests/test_schema.py`
- Create: `spec/v1/ontology-package.schema.json`
- Create: `examples/service-operations/manifest.yaml`

- [ ] **Step 1: Add the Python validation toolchain**

Create `pyproject.toml` with this complete configuration:

```toml
[project]
name = "executable-business-ontology"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "jsonschema>=4.23,<5",
  "PyYAML>=6.0,<7",
  "rdflib>=7.1,<8",
  "pyshacl>=0.30,<1",
]

[project.optional-dependencies]
dev = ["pytest>=8.3,<9"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Write the first failing manifest validation test**

Create `tests/test_schema.py`:

```python
from pathlib import Path

from scripts.validate_package import validate_document


ROOT = Path(__file__).parents[1]


def test_service_operations_manifest_is_valid() -> None:
    errors = validate_document(
        ROOT / "examples/service-operations/manifest.yaml",
        ROOT / "spec/v1/ontology-package.schema.json",
        definition="manifest",
    )
    assert errors == []


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
```

- [ ] **Step 3: Run the test and verify the missing module failure**

Run: `python -m pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.validate_package'`.

- [ ] **Step 4: Implement document loading and definition-scoped validation**

Create empty `scripts/__init__.py`, then create `scripts/validate_package.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


def load_structured(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        if path.suffix == ".json":
            return json.load(stream)
        return yaml.safe_load(stream)


def validate_document(path: Path, schema_path: Path, definition: str) -> list[str]:
    document = load_structured(path)
    schema = load_structured(schema_path)
    validator = Draft202012Validator(schema["$defs"][definition])
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    ]
```

- [ ] **Step 5: Add the initial normative manifest definition**

Create `spec/v1/ontology-package.schema.json` with Draft 2020-12 metadata, a closed `manifest` definition, SemVer patterns, URI-safe `ontologyId`, SHA-256 `contentDigest`, owner records and the seven required file names. Root validation must use `oneOf` references to named document definitions so later tasks can extend the same file without changing the validation API.

Create `examples/service-operations/manifest.yaml` with:

```yaml
ontologyId: org.example.service-operations
ontologyVersion: 1.0.0
specVersion: 1.0.0
namespace: https://example.org/ontology/service-operations/
status: accepted
owners:
  - role: owner
    name: Ontology Standards Team
documents:
  semantics: semantics.yaml
  kinetics: kinetics.yaml
  bindings: bindings.yaml
  policies: policies.yaml
  evidence: evidence.yaml
  migrations: migrations.yaml
contentDigest: sha256:0000000000000000000000000000000000000000000000000000000000000000
```

- [ ] **Step 6: Run the focused tests**

Run: `python -m pytest tests/test_schema.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit the harness**

```bash
git add pyproject.toml scripts tests/test_schema.py spec/v1/ontology-package.schema.json examples/service-operations/manifest.yaml
git commit -m "build: add ontology package validation harness"
```

## Task 2: Define the complete Ontology Package schema and neutral example

**Files:**
- Modify: `spec/v1/ontology-package.schema.json`
- Create: `examples/service-operations/semantics.yaml`
- Create: `examples/service-operations/kinetics.yaml`
- Create: `examples/service-operations/bindings.yaml`
- Create: `examples/service-operations/policies.yaml`
- Create: `examples/service-operations/evidence.yaml`
- Create: `examples/service-operations/migrations.yaml`
- Modify: `tests/test_schema.py`
- Modify: `scripts/validate_package.py`

- [ ] **Step 1: Add failing tests for all seven package documents**

Extend `tests/test_schema.py` with a parameterized test over the exact pairs `manifest`, `semantics`, `kinetics`, `bindings`, `policies`, `evidence`, and `migrations`. Add invalid fixtures asserting rejection of a missing object key, a dangling link endpoint, an action without effects, and a binding without evidence references.

- [ ] **Step 2: Run the tests and verify incomplete-definition failures**

Run: `python -m pytest tests/test_schema.py -v`
Expected: FAIL because six documents and their `$defs` do not exist.

- [ ] **Step 3: Complete the normative JSON Schema definitions**

Extend `ontology-package.schema.json` with closed definitions for:

- Stable identifiers, labels, localized descriptions and lifecycle state.
- Primitive, enum, structured, reference, temporal, spatial and measured value types.
- Object types, properties, keys, links, interfaces, invariants and business terms.
- Actions, queries, parameters, preconditions, effects, state machines, domain events, side effects and compensations.
- Data, API, code and event bindings; identity, synchronization and consistency policies.
- Authorization, audit, quality and compliance policies.
- Evidence references, observations, DiscoveryClaim records and approvals.
- Version changes, compatibility classification, correction operation, lineage, migration, rollback and acceptance evidence.

Every object definition must set `additionalProperties: false`. Every cross-document reference must use a stable-ID string pattern; cross-reference existence is enforced by `validate_package`, not JSON Schema.

- [ ] **Step 4: Author the complete service-operations package**

Model a domain-neutral service workflow containing `Party`, `ServiceRequest`, `ServiceOffering`, `WorkItem` and `Resource`. Include stable keys, typed properties, specific verb relationships, `submitServiceRequest`, `assignWorkItem`, and `completeWorkItem` actions, request/work state machines, queries, domain events, database/API/event bindings, permission rules, audit rules and evidence references.

The example must demonstrate all four architecture layers without assuming a specific industry.

- [ ] **Step 5: Add package-level reference and digest validation**

Add to `scripts/validate_package.py`:

```python
DOCUMENTS = {
    "manifest": "manifest.yaml",
    "semantics": "semantics.yaml",
    "kinetics": "kinetics.yaml",
    "bindings": "bindings.yaml",
    "policies": "policies.yaml",
    "evidence": "evidence.yaml",
    "migrations": "migrations.yaml",
}


def validate_package(package_dir: Path, schema_path: Path) -> list[str]:
    errors: list[str] = []
    documents: dict[str, Any] = {}
    for definition, filename in DOCUMENTS.items():
        path = package_dir / filename
        if not path.exists():
            errors.append(f"{filename}: required document is missing")
            continue
        documents[definition] = load_structured(path)
        errors.extend(
            f"{filename}: {message}"
            for message in validate_document(path, schema_path, definition)
        )
    if errors:
        return errors
    errors.extend(validate_references(documents))
    errors.extend(validate_digest(package_dir, documents["manifest"]))
    return sorted(errors)
```

Implement `validate_references` by collecting every declared element ID and checking all `*Ref` and `*Refs` fields. Implement `validate_digest` using SHA-256 over canonical JSON for the six non-manifest documents, sorted by document name and JSON key; the manifest digest is excluded to avoid recursion.

- [ ] **Step 6: Replace the zero digest with the calculated digest**

Run: `python -m scripts.validate_package examples/service-operations`
Expected first run: a single digest mismatch that prints the calculated value. Update `manifest.yaml` with that exact value.

- [ ] **Step 7: Verify the complete package**

Run: `python -m pytest tests/test_schema.py -v`
Expected: all schema and reference tests pass.

- [ ] **Step 8: Commit the normative package**

```bash
git add spec/v1 examples/service-operations scripts/validate_package.py tests/test_schema.py
git commit -m "feat: define ontology package specification"
```

## Task 3: Add RDF/OWL projection and SHACL conformance

**Files:**
- Create: `spec/v1/ontology.shacl.ttl`
- Create: `examples/service-operations/ontology.ttl`
- Create: `examples/service-operations/ontology-invalid.ttl`
- Create: `scripts/validate_rdf.py`
- Create: `tests/test_shacl.py`

- [ ] **Step 1: Write failing SHACL tests**

Create `tests/test_shacl.py`:

```python
from pathlib import Path

from scripts.validate_rdf import validate_rdf


ROOT = Path(__file__).parents[1]
SHAPES = ROOT / "spec/v1/ontology.shacl.ttl"


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
    assert "stableId" in report
```

- [ ] **Step 2: Run the test and verify the missing validator failure**

Run: `python -m pytest tests/test_shacl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.validate_rdf'`.

- [ ] **Step 3: Implement the RDF validator**

Create `scripts/validate_rdf.py`:

```python
from pathlib import Path

from pyshacl import validate
from rdflib import Graph


def validate_rdf(data_path: Path, shapes_path: Path) -> tuple[bool, str]:
    data = Graph().parse(data_path, format="turtle")
    shapes = Graph().parse(shapes_path, format="turtle")
    conforms, _, report = validate(
        data_graph=data,
        shacl_graph=shapes,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )
    return bool(conforms), str(report)
```

- [ ] **Step 4: Define the normative SHACL shapes**

Create shapes for ObjectType, PropertyType, LinkType, ActionType and DiscoveryClaim. Enforce stable ID, human label, object key, link endpoints and cardinality, action preconditions/effects/audit rule, and claim evidence/confidence/falsifier fields. Add SPARQL constraints for duplicate stable IDs and link endpoints that do not identify declared object types.

- [ ] **Step 5: Author valid and invalid Turtle fixtures**

Project the service-operations semantics and kinetics into `ontology.ttl` using an `ebo:` namespace. Create `ontology-invalid.ttl` with one `ebo:ObjectType` lacking `ebo:stableId`; keep every other required property valid so the failure is specific.

- [ ] **Step 6: Run SHACL tests**

Run: `python -m pytest tests/test_shacl.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit semantic-web conformance**

```bash
git add spec/v1/ontology.shacl.ttl examples/service-operations/*.ttl scripts/validate_rdf.py tests/test_shacl.py
git commit -m "feat: add RDF projection and SHACL validation"
```

## Task 4: Document the architecture, metamodel and documentation/runtime relationship

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/metamodel.md`
- Create: `tests/test_docs.py`

- [ ] **Step 1: Write failing documentation contract tests**

Create `tests/test_docs.py` to assert that both files exist, use the normative terms `MUST`, `SHOULD`, and `MAY` with Chinese definitions, link to the schema, and contain headings for Semantics, Kinetics, Binding & Runtime, Governance & Evolution, traceability, projection digest and Extension Point.

- [ ] **Step 2: Run the documentation tests**

Run: `python -m pytest tests/test_docs.py -v`
Expected: FAIL because both documents are absent.

- [ ] **Step 3: Write `docs/architecture.md`**

Cover the purpose, non-goals, four layers, Ontology Package boundaries, single-source/multi-projection flow, content digest, extension points, authoring/publishing lifecycle, failure boundaries and the difference between a conceptual ontology and an operational ontology. Include the rule that direct edits to generated projections are non-conformant.

- [ ] **Step 4: Write `docs/metamodel.md`**

Document every schema element with its purpose, required fields, invariants, dependencies and one YAML fragment drawn from the service-operations example. Clearly distinguish ObjectType from instance, LinkType from foreign key, ActionType from endpoint, DomainEvent from command, Policy from validation, and Evidence from inference.

- [ ] **Step 5: Run documentation and full tests**

Run: `python -m pytest tests/test_docs.py tests/test_schema.py tests/test_shacl.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit architecture documentation**

```bash
git add docs/architecture.md docs/metamodel.md tests/test_docs.py
git commit -m "docs: explain ontology architecture and metamodel"
```

## Task 5: Document forward engineering and traceability

**Files:**
- Create: `docs/forward-engineering.md`
- Create: `examples/service-operations/traceability.yaml`
- Modify: `tests/test_docs.py`
- Modify: `spec/v1/ontology-package.schema.json`

- [ ] **Step 1: Add failing traceability tests**

Require each traceability record to contain `elementRef`, `documentationRef`, at least one of `runtimeRef` or `extensionPointRef`, `evidenceRefs`, and `verificationRefs`. Assert that every accepted semantic and kinetic element has a traceability record.

- [ ] **Step 2: Run the focused test and verify missing traceability failures**

Run: `python -m pytest tests/test_docs.py -k traceability -v`
Expected: FAIL because the schema and example do not define traceability.

- [ ] **Step 3: Add the traceability schema and example matrix**

Add a closed `traceabilityRecord` definition and a traceability document definition to the schema. Author records for all service-operations objects, links, actions, queries and policies. Runtime references use technology-neutral component URIs such as `runtime://service-request/command/submit`.

- [ ] **Step 4: Write `docs/forward-engineering.md`**

Specify the six stages: goals/capability questions, semantics, kinetics, bindings, system projections and scenario acceptance. For each stage define inputs, activities, output artifacts, quality gate and rejection conditions. Include system boundary generation, API/storage/policy projection rules, extension-point policy, normal/denied/compensated action scenarios and the exact criteria for claiming that a system implements an Ontology.

- [ ] **Step 5: Validate traceability and documentation**

Run: `python -m pytest tests/test_docs.py tests/test_schema.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit forward-engineering guidance**

```bash
git add docs/forward-engineering.md examples/service-operations/traceability.yaml spec/v1/ontology-package.schema.json tests
git commit -m "docs: define ontology-driven system construction"
```

## Task 6: Specify reverse discovery, self-evidence and confidence

**Files:**
- Create: `docs/reverse-engineering.md`
- Create: `docs/discovery-confidence.md`
- Create: `examples/discovery/evidence-graph.yaml`
- Create: `examples/discovery/claims.yaml`
- Create: `scripts/confidence.py`
- Create: `tests/test_discovery.py`
- Modify: `spec/v1/ontology-package.schema.json`

- [ ] **Step 1: Write failing confidence tests**

Create `tests/test_discovery.py` with exact boundary tests for 85/A, 84/B, 70/B, 69/C, 50/C and 49/D; verify that missing counterevidence assessment, alternatives, falsifiers or validation questions makes a claim invalid.

- [ ] **Step 2: Run the tests and verify the missing implementation failure**

Run: `python -m pytest tests/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.confidence'`.

- [ ] **Step 3: Implement deterministic confidence scoring**

Create `scripts/confidence.py`:

```python
WEIGHTS = {
    "crossSourceAgreement": 0.25,
    "evidenceCoverage": 0.20,
    "runtimeSupport": 0.20,
    "semanticSpecificity": 0.15,
    "constraintConsistency": 0.10,
    "counterEvidenceAssessment": 0.10,
}


def confidence_score(dimensions: dict[str, int]) -> int:
    if set(dimensions) != set(WEIGHTS):
        missing = sorted(set(WEIGHTS) - set(dimensions))
        extra = sorted(set(dimensions) - set(WEIGHTS))
        raise ValueError(f"invalid dimensions; missing={missing}, extra={extra}")
    if any(value < 0 or value > 100 for value in dimensions.values()):
        raise ValueError("dimension scores must be between 0 and 100")
    return round(sum(dimensions[name] * weight for name, weight in WEIGHTS.items()))


def confidence_grade(score: int) -> str:
    if not 0 <= score <= 100:
        raise ValueError("confidence score must be between 0 and 100")
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"
```

- [ ] **Step 4: Author Evidence Graph and DiscoveryClaim examples**

Create database, OpenAPI, code/config and event-log observations with source URI, location, timestamp, hash and extractor version. Create four claims representing grades A–D. Each claim includes reasoning rules, support, counterevidence assessment, alternatives, dimension scores, calculated result, falsifiers, validation questions, capability questions and provenance. At least one claim must remain unaccepted despite grade A to demonstrate that confidence does not bypass governance.

- [ ] **Step 5: Write the reverse-engineering documents**

`docs/reverse-engineering.md` defines acquisition, normalization, Evidence Graph, deterministic inference, semantic-assisted matching, conflict retention, human adjudication and Baseline Ontology generation. `docs/discovery-confidence.md` normatively defines DiscoveryClaim, the seven self-understanding questions, scoring weights, grades, evidence admissibility, LLM limitations, falsification and promotion rules.

- [ ] **Step 6: Run discovery and schema tests**

Run: `python -m pytest tests/test_discovery.py tests/test_schema.py tests/test_docs.py -v`
Expected: all tests pass.

- [ ] **Step 7: Commit reverse discovery standards**

```bash
git add docs/reverse-engineering.md docs/discovery-confidence.md examples/discovery scripts/confidence.py spec/v1/ontology-package.schema.json tests
git commit -m "docs: specify explainable ontology discovery"
```

## Task 7: Specify versioning, initial-error correction and evolution

**Files:**
- Create: `docs/evolution-governance.md`
- Create: `examples/evolution/v1/`
- Create: `examples/evolution/v2/`
- Create: `examples/evolution/migration.yaml`
- Create: `tests/test_evolution.py`
- Modify: `scripts/validate_package.py`

- [ ] **Step 1: Write failing evolution tests**

Test that published packages are treated as immutable, Patch/Minor/Major classification selects the highest impact, accepted elements cannot disappear without lineage, rename preserves stable ID, split and merge list predecessor/successor IDs, retract records cause/evidence/impact, and every breaking change has migrate/backfill/rollback/acceptance fields.

- [ ] **Step 2: Run the tests and verify missing fixtures and rules**

Run: `python -m pytest tests/test_evolution.py -v`
Expected: FAIL because evolution packages and validation functions are absent.

- [ ] **Step 3: Create an intentionally wrong v1 and corrected v2**

In v1, model a broad `Actor` object that incorrectly combines organization and individual semantics, and a vague `relatedTo` link. In v2, split it into `Person` and `Organization`, replace the vague link with specific role relationships, retract the false claim, and retain predecessor/successor lineage. Both versions must be internally valid packages; the error is epistemic/semantic, not malformed syntax.

- [ ] **Step 4: Author the migration record**

Include the original/new definitions, error cause, new supporting evidence, correction operations, impact on data/API/action/policy/document consumers, deterministic classification rule, backfill query description, rollback conditions, compatibility window, dual-read comparison, acceptance results and lineage.

- [ ] **Step 5: Implement evolution validation**

Add `classify_change`, `validate_lineage` and `validate_migration` to `validate_package.py`. Use the impact order `patch < minor < major`; classify rename/retype/split/merge/relink/supersede/retract as major unless an explicit stable-ID alias rule proves the change does not alter any consumer-facing identifier.

- [ ] **Step 6: Write `docs/evolution-governance.md`**

Define `specVersion`, `ontologyVersion`, `elementRevision`, lifecycle states, Branch → Proposal → Impact Analysis → Review → L0–L3 Validation → Release → Observation, all correction operations, coexistence/alias/dual-read/temporary-dual-write/backfill/rollback strategies, proposal triggers and version-over-version optimization metrics.

- [ ] **Step 7: Run evolution and full package tests**

Run: `python -m pytest tests/test_evolution.py tests/test_schema.py -v`
Expected: all tests pass.

- [ ] **Step 8: Commit evolution governance**

```bash
git add docs/evolution-governance.md examples/evolution scripts/validate_package.py tests/test_evolution.py
git commit -m "docs: define ontology evolution and correction"
```

## Task 8: Publish conformance and interoperability mappings

**Files:**
- Create: `docs/conformance.md`
- Create: `docs/interoperability.md`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Add failing completeness tests**

Require L0–L3 definitions, release-blocking error classes, quality gates and mappings for Palantir Object/Link/Action/Query/Transaction/Branch, Microsoft Entity/Relationship/Data Binding/RDF import-export, and RDF/OWL/SHACL/OpenAPI.

- [ ] **Step 2: Run the focused documentation tests**

Run: `python -m pytest tests/test_docs.py -k 'conformance or interoperability' -v`
Expected: FAIL because both documents are absent.

- [ ] **Step 3: Write `docs/conformance.md`**

Define L0 Syntactic, L1 Semantic, L2 Behavioral and L3 Operational inputs, checks, failure reports and pass criteria. Include the complete release checklist and clarify that MVP L3 validates binding descriptions statically because it contains no live runtime connectors.

- [ ] **Step 4: Write `docs/interoperability.md`**

Create exact concept tables with columns Source Concept, EBO Concept, Mapping Type, Information Loss and Notes. Mark direct, partial and extension mappings. State that Palantir implementation details are not reproduced, the secondary impact essay is interpretive, Microsoft visualization is deferred, and RDF/OWL cannot natively express every kinetic/runtime concept without the EBO extension vocabulary.

- [ ] **Step 5: Run documentation tests**

Run: `python -m pytest tests/test_docs.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit conformance and mappings**

```bash
git add docs/conformance.md docs/interoperability.md tests/test_docs.py
git commit -m "docs: publish conformance and interoperability mappings"
```

## Task 9: Complete navigation, verification and release readiness

**Files:**
- Create: `README.md`
- Create: `docs/index.md`
- Modify: `scripts/validate_package.py`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Add failing repository-level acceptance tests**

Require every documentation file to be linked from `docs/index.md`, every index entry to resolve, README to include the one-command validation workflow, no normative file to contain unresolved relative links, and no tracked document or schema to contain unresolved content markers.

- [ ] **Step 2: Add the validation CLI**

Add an argparse entry point to `validate_package.py` accepting a package path, defaulting the schema path to `spec/v1/ontology-package.schema.json`, printing one error per line, returning exit code 1 on failure and `PASS <ontologyId>@<ontologyVersion> L0-L3-static` on success.

- [ ] **Step 3: Write `docs/index.md`**

Provide three reading paths: decision maker, ontology designer, and system/reverse engineer. Link the design rationale, normative standard, guides, mappings, examples and validation commands in dependency order.

- [ ] **Step 4: Write `README.md`**

State the project goal, four capabilities, four-layer model, MVP boundary, repository map, installation, `python -m scripts.validate_package examples/service-operations`, `python -m pytest`, example walkthrough and source acknowledgements.

- [ ] **Step 5: Run all automated verification**

Run: `python -m pytest -v`
Expected: all tests pass.

Run: `python -m scripts.validate_package examples/service-operations`
Expected: `PASS org.example.service-operations@1.0.0 L0-L3-static`.

Run: `python -m scripts.validate_package examples/evolution/v1`
Expected: `PASS org.example.identity-baseline@1.0.0 L0-L3-static`.

Run: `python -m scripts.validate_package examples/evolution/v2`
Expected: `PASS org.example.identity-baseline@2.0.0 L0-L3-static`.

- [ ] **Step 6: Run repository hygiene checks**

Run: `git diff --check`
Expected: no output and exit code 0.

Run: `rg -n 'T[B]D|T[O]DO|F[I]XME|待[定]|稍[后]补充' README.md docs spec examples scripts tests`
Expected: no output and exit code 1.

- [ ] **Step 7: Perform design-to-delivery coverage review**

Check each section of `docs/superpowers/specs/2026-07-27-ontology-framework-design.md` against at least one documentation section, schema rule, example and/or test. Record the completed mapping in `docs/index.md` under “Design coverage”; every one of the four requested capabilities must have all four artifact types where applicable.

- [ ] **Step 8: Commit the complete MVP**

```bash
git add README.md docs scripts tests spec examples pyproject.toml
git commit -m "docs: complete executable ontology standard MVP"
```

## Final acceptance checkpoint

- [ ] All tests and three package validations pass from a clean checkout.
- [ ] The service-operations example demonstrates Semantics, Kinetics, Binding & Runtime, and Governance & Evolution.
- [ ] Documentation and machine-readable fields use the same names and lifecycle semantics.
- [ ] Discovery examples demonstrate evidence, counterevidence, alternatives, confidence, falsifiers and human approval.
- [ ] Evolution examples prove that an initially accepted but wrong model can be split, retracted, migrated and historically explained.
- [ ] Every generated/projection artifact carries or references the same ontology identity, version and content digest.
- [ ] Source mappings distinguish direct facts, implementation-derived signals and secondary interpretation.
