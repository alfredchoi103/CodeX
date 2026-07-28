import re
from collections import Counter
import os
from pathlib import Path
import subprocess
import sys

import yaml

from scripts.validate_package import CoreLoader, load_structured


ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "metamodel.md",
    ROOT / "docs" / "forward-engineering.md",
)
CONFORMANCE = ROOT / "docs" / "conformance.md"
INTEROPERABILITY = ROOT / "docs" / "interoperability.md"
TASK8_DOCS = (CONFORMANCE, INTEROPERABILITY)
README = ROOT / "README.md"
INDEX = ROOT / "docs/index.md"
GITIGNORE = ROOT / ".gitignore"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing documentation file: {path.relative_to(ROOT)}"
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"empty documentation file: {path.relative_to(ROOT)}"
    return text


def _markdown_links(text: str) -> list[tuple[str, str]]:
    return re.findall(r"\[[^\]]+\]\(([^\s)#]+)(?:#([^\s)]+))?\)", text)


def _anchors(text: str) -> set[str]:
    explicit = set(re.findall(r'<a\s+id=["\']([^"\']+)["\']', text))
    headings = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*$", text, re.MULTILINE):
        plain = re.sub(r"[`*_]", "", heading).strip().lower()
        slug = re.sub(r"[^\w\-\u4e00-\u9fff ]", "", plain)
        headings.add(re.sub(r"[ _]+", "-", slug).strip("-"))
    return explicit | headings


def test_repository_navigation_files_exist_and_gitignore_build_artifacts():
    for path in (README, INDEX, GITIGNORE):
        _read(path)
    ignored = GITIGNORE.read_text(encoding="utf-8")
    for entry in (
        "__pycache__/", "*.py[cod]", ".pytest_cache/", ".venv/",
        "dist/", "build/", "*.egg-info/",
    ):
        assert entry in ignored


def test_docs_index_links_every_markdown_document():
    index = _read(INDEX)
    for document in sorted((ROOT / "docs").rglob("*.md")):
        if document == INDEX:
            continue
        relative = document.relative_to(INDEX.parent).as_posix()
        assert relative in index, f"docs/index.md does not link {relative}"


def test_all_repository_markdown_relative_links_and_anchors_resolve():
    for source in (README, *sorted((ROOT / "docs").rglob("*.md"))):
        for target_text, anchor in _markdown_links(_read(source)):
            if "://" in target_text or target_text.startswith(("mailto:", "#")):
                continue
            target = (source.parent / target_text).resolve()
            assert target.is_relative_to(ROOT), f"{source}: link escapes repository: {target_text}"
            assert target.exists(), f"{source}: broken link: {target_text}"
            if anchor and target.is_file() and target.suffix.lower() == ".md":
                assert anchor in _anchors(_read(target)), f"{source}: missing anchor {target_text}#{anchor}"


def test_readme_has_one_command_workflows_and_commands_execute():
    readme = _read(README)
    commands = (
        "python -m scripts.validate_package examples/service-operations",
        "python -m scripts.validate_release examples/service-operations",
        "python -m pytest",
    )
    for command in commands:
        assert command in readme
    if os.environ.get("EBO_README_COMMAND_TEST") == "1":
        return
    environment = os.environ.copy()
    environment["EBO_README_COMMAND_TEST"] = "1"
    for command in commands:
        completed = subprocess.run(
            command.split(), cwd=ROOT, text=True, capture_output=True, check=False,
            env=environment,
        )
        assert completed.returncode == 0, completed.stderr + completed.stdout


def test_normative_public_files_have_no_unresolved_content_markers():
    normative = [README, INDEX, *sorted((ROOT / "docs").glob("*.md")), ROOT / "spec/v1/ontology-package.schema.json", ROOT / "spec/v1/ontology.shacl.ttl"]
    forbidden = (
        "T" + "BD", "TO" + "DO", "FIX" + "ME", "place" + "holder",
        "待" + "定", "待" + "实施", "稍后" + "补充",
    )
    marker = re.compile("|".join(re.escape(item) for item in forbidden), re.I)
    for path in normative:
        match = marker.search(_read(path))
        assert match is None, f"{path.relative_to(ROOT)} contains unresolved marker {match.group(0)!r}"


def test_index_has_three_reading_paths_dependency_order_and_design_coverage():
    text = _read(INDEX)
    for audience in ("决策者", "Ontology Designer", "System / Reverse Engineer"):
        assert audience in text
    ordered = (
        "architecture.md", "metamodel.md", "forward-engineering.md",
        "reverse-engineering.md", "discovery-confidence.md", "evolution-governance.md",
        "conformance.md", "interoperability.md", "../examples/service-operations",
        "../spec/v1/ontology-package.schema.json", "superpowers/specs/2026-07-27-ontology-framework-design.md",
    )
    positions = [text.index(item) for item in ordered]
    assert positions == sorted(positions)
    for capability in ("设计 Ontology", "正向构建", "逆向发现", "持续纠错与优化"):
        row = next(line for line in text.splitlines() if capability in line)
        for artifact in ("文档", "Schema", "Example", "Test"):
            assert artifact in row


def test_readme_states_scope_architecture_installation_and_walkthroughs():
    text = _read(README)
    for term in (
        "Executable Business Ontology", "四种能力", "Semantics", "Kinetics",
        "Binding & Runtime", "Governance & Evolution", "单一事实源", "多投影",
        "Python 3.11", "python -m venv .venv", "pip install -e '.[dev]'",
        "service-operations", "Discovery", "Evolution", "不包含运行引擎", "来源致谢",
    ):
        assert term in text


def _heading_sections(text: str, level: int) -> dict[str, list[str]]:
    """Return Markdown heading bodies keyed by their exact, de-formatted title."""
    marks = "#" * level
    matches = list(re.finditer(rf"^{marks}\s+(.+?)\s*$", text, re.MULTILINE))
    sections: dict[str, list[str]] = {}
    for index, match in enumerate(matches):
        title = re.sub(r"[`*_]", "", match.group(1)).strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.setdefault(title, []).append(text[match.end():end])
    return sections


def _h3_sections(text: str) -> dict[str, list[str]]:
    return _heading_sections(text, 3)


def _section_named(sections: dict[str, list[str]], name: str) -> str:
    matches = [
        body
        for title, bodies in sections.items()
        if title.casefold() == name.casefold()
        for body in bodies
    ]
    assert len(matches) == 1, f"expected one independent ### {name} section, got {len(matches)}"
    return matches[0]


def _plain(text: str) -> str:
    return re.sub(r"[`*_（）()]", "", text)


def _markdown_table(section: str, headers: tuple[str, ...]) -> dict[str, dict[str, str]]:
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    for index, line in enumerate(lines):
        cells = tuple(cell.strip() for cell in line.strip("|").split("|"))
        if cells == headers:
            rows: dict[str, dict[str, str]] = {}
            for row_line in lines[index + 2:]:
                values = tuple(cell.strip() for cell in row_line.strip("|").split("|"))
                if len(values) != len(headers):
                    break
                rows[values[0]] = dict(zip(headers, values, strict=True))
            return rows
    raise AssertionError(f"missing Markdown table with headers {headers}")


def _required_fields_line(section: str) -> str:
    match = re.search(r"^- \*\*Required Fields[^\n]*", section, re.MULTILINE)
    assert match, "section missing Required Fields line"
    return match.group(0)


def _schema_reference_fields(schema: dict) -> set[str]:
    """Derive definition.field paths whose property accepts external references."""
    reference_defs = {
        "#/$defs/reference", "#/$defs/idRefs", "#/$defs/nonEmptyIdRefs"
    }
    found = set()

    def visit(node: object, definition: str | None = None) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if definition and isinstance(properties, dict):
                for field, field_schema in properties.items():
                    if isinstance(field_schema, dict) and field_schema.get("$ref") in reference_defs:
                        found.add(f"{definition}.{field}")
            for value in node.values():
                visit(value, definition)
        elif isinstance(node, list):
            for value in node:
                visit(value, definition)

    for definition, definition_schema in schema["$defs"].items():
        visit(definition_schema, definition)
    return found


def test_required_documentation_files_exist_and_are_nonempty():
    for path in DOCS:
        _read(path)


def test_conformance_and_interoperability_documents_exist_and_are_nonempty():
    for path in TASK8_DOCS:
        _read(path)


def test_conformance_defines_four_complete_dependent_levels_and_static_l3_scope():
    text = _read(CONFORMANCE)
    sections = _heading_sections(text, 2)
    levels = (
        "L0 Syntactic",
        "L1 Semantic",
        "L2 Behavioral",
        "L3 Operational",
    )
    for index, level in enumerate(levels):
        body = _section_named(sections, level)
        for label in ("Inputs", "Checks", "Failure Report", "Pass Criteria"):
            assert label in body, f"{level} missing {label}"
        if index:
            assert levels[index - 1].split()[0] in body, f"{level} must depend on prior level"
    l3 = _section_named(sections, "L3 Operational")
    assert "L3-static" in l3
    assert re.search(r"(?:no live connector|不(?:含|执行|连接).{0,30}(?:live|实时|外部))", l3, re.I)


def test_conformance_distinguishes_component_checks_from_unified_static_release_validation():
    conformance = _read(CONFORMANCE)
    architecture = _read(DOCS[0])
    for text in (conformance, architecture):
        assert "component-level" in text
        assert "python -m scripts.validate_release" in text
        assert "L0-L3-static" in text
        assert re.search(r"不(?:连接|执行|证明).{0,40}(?:live|runtime|外部系统)", text, re.I)
    assert re.search(r"L0.{0,30}部分 L1/L2/L3 evidence", conformance, re.S)
    assert "当前 MVP 只实现 **L3-static**" not in conformance
    assert "`L3-static pass`" not in conformance


def test_conformance_has_release_blockers_quality_gate_and_actionable_reports():
    text = _read(CONFORMANCE)
    for error_class in (
        "structural", "semantic", "behavioral", "binding", "evidence", "evolution",
    ):
        assert error_class in text.lower()
    for gate in (
        "命名", "单概念", "stable identity", "relationship", "action audit", "binding",
        "evidence", "orphan", "cycle", "breaking migration", "capability questions",
    ):
        assert gate.lower() in text.lower(), f"missing quality gate: {gate}"
    for field in ("class", "element", "path", "rule", "message", "fix"):
        assert field in text
    assert "errorClass" not in text
    assert "element ID" not in text
    for phrase in (
        "dataBindings → ObjectType", "apiBindings → ActionType / QueryType",
        "eventBindings → DomainEventType", "codeBindings", "Package migrations",
        "split", "merge", "retract", "one-to-one", "cycle",
    ):
        assert phrase in text
    assert "python -m scripts.validate_package" in text
    assert "pytest" in text
    assert "--level" not in text
    assert "../examples/service-operations/" in text
    assert "ontology-invalid.ttl" in text
    assert "../examples/discovery/" in text
    assert "../examples/evolution/" in text


def test_architecture_requires_extension_point_when_runtime_is_absent():
    text = _read(DOCS[0])
    assert "未实现时明确为空" not in text
    assert re.search(r"无 runtime 实现时.{0,80}不得填.{0,20}runtimeRef", text)
    assert "extensionPointRef" in text


def test_interoperability_tables_cover_products_standards_and_mapping_semantics():
    text = _read(INTEROPERABILITY)
    for heading in ("Source Concept", "EBO Concept", "Mapping Type", "Information Loss", "Notes"):
        assert heading in text
    for mapping_type in ("direct", "partial", "extension"):
        assert re.search(rf"\b{mapping_type}\b", text, re.I)
    palantir = (
        "Object Type", "Property", "Link Type", "Action", "Query", "Object Set",
        "Transaction", "Branch", "OntologyScenario", "ObjectType edits history", "permissions",
    )
    microsoft = (
        "Entity Type", "Property", "Relationship", "Data Binding", "composite key",
        "time series", "RDF import", "RDF export", "graph visualization",
    )
    standards = ("RDF", "OWL", "SHACL", "JSON Schema", "OpenAPI")
    for term in (*palantir, *microsoft, *standards):
        assert term.lower() in text.lower(), f"missing interoperability concept: {term}"
    assert re.search(r"Information Loss[^\n]*", text)


def test_interoperability_states_evidence_boundaries_and_non_goals():
    text = _read(INTEROPERABILITY)
    boundaries = (
        "official SDK", "direct implementation signal", "secondary analysis", "二级材料",
        "website", "not directly verified", "Playground code", "不复制私有实现",
    )
    for phrase in boundaries:
        assert phrase.lower() in text.lower(), f"missing source boundary: {phrase}"
    assert re.search(r"RDF/OWL.{0,100}(?:不能|无法).{0,80}(?:Kinetics|runtime)", text, re.I | re.S)
    assert "EBO extension" in text
    assert re.search(r"Microsoft.{0,80}(?:visualization|可视化).{0,60}deferred", text, re.I | re.S)
    assert re.search(r"Palantir.{0,100}(?:非|不构成|不是).{0,40}(?:兼容|compatibility)", text, re.I | re.S)
    assert "https://github.com/palantir/foundry-platform-python" in text
    assert text.count("https://github.com/microsoft/Ontology-Playground") == 1


def test_interoperability_uses_verified_palantir_source_boundaries():
    text = _read(INTEROPERABILITY)
    api_url = "https://www.palantir.com/docs/foundry/api/v2/general/overview/introduction/"
    essay_url = (
        "https://github.com/Leading-AI-IO/palantir-ontology-strategy/"
        "blob/main/docs/the-palantir-impact_en.md"
    )
    api_row = next(line for line in text.splitlines() if api_url in line)
    essay_row = next(line for line in text.splitlines() if essay_url in line)
    assert "official website" in api_row.lower()
    assert "官网未直接核验" in api_row
    assert "secondary analysis" in essay_row.lower()
    assert "二级材料" in essay_row
    assert "https://www.palantir.com/impact/ontology/" not in text


def test_palantir_mapping_rows_preserve_scenario_and_instance_history_levels():
    section = _section_named(_heading_sections(_read(INTEROPERABILITY), 2), "Palantir Ontology API 概念")
    rows = _markdown_table(
        section,
        ("Source Concept", "EBO Concept", "Mapping Type", "Information Loss", "Notes"),
    )
    scenario = rows["OntologyScenario"]
    assert scenario["Mapping Type"] in {"partial", "extension"}
    assert re.search(r"candidate|proposal|sandbox", scenario["EBO Concept"], re.I)
    assert "edit-conflict" in scenario["Notes"]
    assert re.search(r"不是.{0,30}capability acceptance scenario", scenario["Notes"], re.I)
    history = rows["ObjectType edits history"]
    assert history["Mapping Type"] in {"partial", "extension"}
    assert re.search(r"instance.{0,30}(?:audit|edit evidence|history)", history["EBO Concept"], re.I)
    assert re.search(r"不是.{0,30}ontology schema.{0,20}Change.{0,10}Lineage", history["Notes"], re.I)


def test_interoperability_sources_pin_revisions_and_standard_versions():
    section = _section_named(_heading_sections(_read(INTEROPERABILITY), 2), "来源与访问边界")
    headers = ("Source", "URL", "Version / Revision", "Access type", "How used")
    rows = _markdown_table(section, headers)
    for row in rows.values():
        if re.search(r"direct (?:implementation signal|code evidence)|secondary analysis", row["Access type"], re.I):
            assert re.fullmatch(r"`?[0-9a-f]{40}`?", row["Version / Revision"])
    expected = {
        "W3C RDF 1.1 Concepts": ("RDF 1.1", "https://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/"),
        "W3C OWL 2 Overview": ("OWL 2", "https://www.w3.org/TR/2012/REC-owl2-overview-20121211/"),
        "W3C SHACL": ("SHACL 1.0", "https://www.w3.org/TR/2017/REC-shacl-20170720/"),
        "JSON Schema": ("2020-12", "https://json-schema.org/draft/2020-12/json-schema-core.html"),
        "OpenAPI Specification": ("3.1.1", "https://spec.openapis.org/oas/v3.1.1.html"),
    }
    for source, (version, url) in expected.items():
        assert rows[source]["Version / Revision"] == version
        assert rows[source]["URL"] == url
    assert rows["Palantir API v2 Introduction"]["Version / Revision"] == "unversioned"
    assert "/latest" not in section


def test_both_documents_define_normative_terms():
    for path in TASK8_DOCS:
        section = _section_named(_heading_sections(_read(path), 2), "规范性术语")
        for english, chinese in (("MUST", "必须"), ("SHOULD", "应该"), ("MAY", "可以")):
            assert re.search(rf"{english}[^\n]*{chinese}", section), (
                f"{path.name} must define {english} as {chinese}"
            )


def test_architecture_normative_terms_are_defined_in_their_own_section():
    section = _section_named(_h3_sections(_read(DOCS[0])), "规范性术语")
    for english, chinese in (("MUST", "必须"), ("SHOULD", "应该"), ("MAY", "可以")):
        assert re.search(rf"{english}[^\n]*{chinese}", section)


def test_metamodel_normative_terms_are_defined_in_their_own_section():
    section = _section_named(_h3_sections(_read(DOCS[1])), "规范性术语")
    for english, chinese in (("MUST", "必须"), ("SHOULD", "应该"), ("MAY", "可以")):
        assert re.search(rf"{english}[^\n]*{chinese}", section)


def test_architecture_covers_required_concepts():
    raw = _read(DOCS[0])
    text = raw.lower()
    required = (
        "semantics",
        "kinetics",
        "binding & runtime",
        "governance & evolution",
        "ontology package",
        "single source of truth",
        "单一事实源",
        "multi-projection",
        "多投影",
        "contentdigest",
        "extension point",
        "traceability",
        "可追溯",
        "错误边界",
        "发布生命周期",
        "conceptual ontology",
        "operational ontology",
    )
    missing = [term for term in required if term not in text]
    assert not missing, f"architecture.md missing concepts: {missing}"

    for filename in (
        "manifest.yaml", "semantics.yaml", "kinetics.yaml", "bindings.yaml",
        "policies.yaml", "evidence.yaml", "migrations.yaml",
    ):
        assert filename in raw
    for metadata in ("ontologyId", "ontologyVersion", "specVersion", "contentDigest"):
        assert metadata in raw
    assert re.search(r"生成物.{0,20}(?:禁止|不得)直接修改", _plain(raw))
    assert "Extension Point" in raw


def test_architecture_projection_extension_and_traceability_sections_are_scoped():
    sections = _h3_sections(_read(DOCS[0]))
    identity = _section_named(sections, "投影身份与摘要")
    for field in ("ontologyId", "ontologyVersion", "specVersion", "contentDigest"):
        assert field in identity

    extension = _section_named(sections, "Extension Point")
    for phrase in ("extensionPoint", "v1", "运行投影契约"):
        assert phrase in extension
    assert re.search(r"(?:尚无|没有|未定义)", extension)

    traceability = _section_named(sections, "可追溯性矩阵")
    for link in ("Package 稳定 ID", "文档", "运行组件", "证据", "验证"):
        assert link in traceability
    for field in ("documentationRef", "runtimeRef", "verificationRefs"):
        assert field in traceability
    for phrase in ("第八个文档", "traceability.yaml", "evidenceRefs", "机器校验"):
        assert phrase in traceability
    assert not re.search(r"\bTask\s*5\b", _read(DOCS[0]), re.IGNORECASE)
    assert re.search(r"MUST.{0,80}目标一致性契约", traceability)
    assert not re.search(r"(?:未来|后续).{0,40}(?:companion|traceability\.yaml|Schema 扩展)", traceability)


def test_architecture_has_complete_layers_traceability_lifecycle_and_results():
    text = _read(DOCS[0])
    sections = _h3_sections(text)
    major_sections = _heading_sections(text, 2)
    for layer in (
        "2.1 Semantics（语义层）",
        "2.2 Kinetics（行为层）",
        "2.3 Binding & Runtime（绑定与运行层）",
        "2.4 Governance & Evolution（治理与演进层）",
    ):
        body = _section_named(sections, layer)
        for field in ("输入", "输出", "依赖", "错误边界"):
            assert field in body, f"{layer} missing {field}"

    traceability = _section_named(sections, "可追溯性矩阵")
    for link in ("Package 稳定 ID", "文档", "运行组件", "证据", "验证"):
        assert link in traceability

    lifecycle = _section_named(major_sections, "6. 发布生命周期").lower()
    ordered = re.compile(
        r"author\s*→\s*validate l0[–-]l3\s*→\s*proposal/review\s*→\s*release\s*→\s*observe"
    )
    assert ordered.search(lifecycle)

    kinetics = _section_named(sections, "2.2 Kinetics（行为层）").lower()
    for result in ("验证失败", "权限拒绝", "业务冲突", "副作用", "成功"):
        assert result in kinetics
    scope = _section_named(major_sections, "1. 目标、适用范围与非目标").lower()
    assert "runtime" in scope and re.search(r"(?:不是|不承诺|未实现|尚未实现)", scope)


def test_metamodel_covers_schema_categories_and_value_type_kinds():
    text = _read(DOCS[1])
    categories = (
        "manifest",
        "semantics",
        "kinetics",
        "bindings",
        "policies",
        "evidence",
        "migrations",
        "traceability",
    )
    lower = text.lower()
    missing = [term for term in categories if term.lower() not in lower]
    assert not missing, f"metamodel.md missing schema concepts: {missing}"
    for kind in ("primitive", "enum", "struct", "reference", "temporal", "spatial", "measured"):
        assert kind in lower, f"metamodel.md missing ValueType kind: {kind}"


def test_every_core_metamodel_definition_has_an_independent_complete_section():
    sections = _h3_sections(_read(DOCS[1]))
    definitions = (
        "Manifest", "Semantics Document", "Kinetics Document", "Bindings Document",
        "Policies Document", "Evidence Document", "Migrations Document",
        "Traceability Document", "TraceabilityRecord",
        "ValueType", "ObjectType", "PropertyType", "LinkType", "InterfaceType",
        "Invariant", "BusinessTerm", "Parameter", "Effect", "ActionType", "QueryType",
        "StateMachine", "State", "Transition", "DomainEventType", "DataBinding", "ApiBinding",
        "CodeBinding", "EventBinding", "Mapping", "OperationalPolicy", "Policy",
        "IdentityResolution", "SyncPolicy",
        "ConsistencyPolicy", "AuthorizationPolicy", "AuditPolicy", "QualityPolicy",
        "CompliancePolicy", "EvidenceRecord", "DiscoveryClaim", "Approval", "Change",
        "Lineage", "Migration",
    )
    for definition in definitions:
        body = _section_named(sections, definition)
        for label in ("Purpose", "Required Fields", "Invariants", "Depends On"):
            assert re.search(rf"\b{label}\b", body), f"### {definition} missing {label}"


def test_schema_core_definitions_have_documented_direct_required_fields():
    schema = load_structured(ROOT / "spec/v1/ontology-package.schema.json")
    sections = _h3_sections(_read(DOCS[1]))
    definition_headings = {
        "manifest": "Manifest", "semantics": "Semantics Document",
        "kinetics": "Kinetics Document", "bindings": "Bindings Document",
        "policies": "Policies Document", "evidence": "Evidence Document",
        "migrations": "Migrations Document",
        "traceability": "Traceability Document",
        "traceabilityRecord": "TraceabilityRecord",
        "valueType": "ValueType", "property": "PropertyType",
        "objectType": "ObjectType", "linkType": "LinkType", "interface": "InterfaceType",
        "rule": "Invariant", "businessTerm": "BusinessTerm", "parameter": "Parameter",
        "effect": "Effect", "action": "ActionType", "query": "QueryType",
        "state": "State", "transition": "Transition", "stateMachine": "StateMachine",
        "domainEvent": "DomainEventType", "mapping": "Mapping",
        "dataBinding": "DataBinding", "apiBinding": "ApiBinding",
        "codeBinding": "CodeBinding", "eventBinding": "EventBinding",
        "operationalPolicy": "OperationalPolicy", "policy": "Policy",
        "evidenceRecord": "EvidenceRecord", "discoveryClaim": "DiscoveryClaim",
        "approval": "Approval", "change": "Change", "lineageEntry": "Lineage",
    }
    for definition, heading in definition_headings.items():
        section = _section_named(sections, heading)
        required_line = _required_fields_line(section)
        for field in schema["$defs"][definition].get("required", []):
            assert f"`{field}`" in required_line, (
                f"### {heading} Required Fields missing schema field {field}"
            )


def test_schema_def_markers_exactly_cover_all_schema_definitions():
    schema = load_structured(ROOT / "spec/v1/ontology-package.schema.json")
    text = _read(DOCS[1])
    markers = re.findall(r"<!--\s*schema-def:\s*([A-Za-z][A-Za-z0-9]*)\s*-->", text)
    counts = Counter(markers)
    assert set(markers) == set(schema["$defs"]), (
        f"missing={sorted(set(schema['$defs']) - set(markers))}, "
        f"extra={sorted(set(markers) - set(schema['$defs']))}"
    )
    assert all(count == 1 for count in counts.values()), (
        f"duplicate schema-def markers: {sorted(k for k, v in counts.items() if v != 1)}"
    )


def test_schema_helper_definitions_table_documents_each_helper():
    helpers = (
        "stableId", "reference", "label", "descriptions", "lifecycle", "idRefs",
        "nonEmptyIdRefs", "stableIdList", "stringList", "semver",
    )
    section = _section_named(_h3_sections(_read(DOCS[1])), "Schema Helper Definitions")
    for column in ("Definition", "Purpose", "Constraint"):
        assert column in section
    for helper in helpers:
        assert f"`{helper}`" in section
        assert f"<!-- schema-def: {helper} -->" in section


def test_metamodel_external_reference_fields_match_schema_and_internal_refs_stay_internal():
    schema = load_structured(ROOT / "spec/v1/ontology-package.schema.json")
    derived_external = _schema_reference_fields(schema)
    section = _section_named(_h3_sections(_read(DOCS[1])), "内部与外部引用")
    external_part = section.split("仅内部稳定 ID", maxsplit=1)[0]
    documented_external = set(re.findall(
        r"`([A-Za-z][A-Za-z0-9]+\.[A-Za-z][A-Za-z0-9]+)`", external_part
    ))
    assert documented_external == derived_external

    for field in (
        "valueType.targetRef", "linkType.sourceRef", "linkType.targetRef",
        "effect.targetRef", "query.resultRef", "transition.fromRef", "transition.toRef",
        "transition.actionRef", "stateMachine.targetRef", "stateMachine.subjectRef",
        "stateMachine.initialStateRef",
        "domainEvent.subjectRef", "dataBinding.targetRef", "apiBinding.targetRef",
        "codeBinding.targetRef", "eventBinding.targetRef", "lineageEntry.predecessorRefs",
        "lineageEntry.successorRefs",
    ):
        assert f"`{field}`" in section
    assert "必须是内部稳定 ID" in section


def test_h3_titles_are_unique_and_domain_event_type_is_consistent():
    for path in DOCS[:2]:
        text = _read(path)
        sections = _h3_sections(text)
        duplicates = [title for title, bodies in sections.items() if len(bodies) > 1]
        assert not duplicates, f"duplicate H3 titles in {path.name}: {duplicates}"
        assert not re.search(r"\bDomainEvent\b(?!Type)", text)


def test_state_machine_documents_schema_array_cardinality_exactly():
    schema = load_structured(ROOT / "spec/v1/ontology-package.schema.json")
    properties = schema["$defs"]["stateMachine"]["properties"]
    assert properties["states"]["minItems"] == 1
    assert "minItems" not in properties["transitions"]

    section = _section_named(_h3_sections(_read(DOCS[1])), "StateMachine")
    plain = _plain(section)
    assert re.search(r"`?states`?\s*(?:必须|MUST)?\s*非空", plain, re.IGNORECASE)
    assert re.search(r"`?transitions`?\s*必填但可为空", plain, re.IGNORECASE)


def test_metamodel_draws_explicit_type_boundaries():
    text = _read(DOCS[1])
    plain = _plain(text)
    boundaries = (
        r"ObjectType[^。\n]{0,100}(?:不是|不等同于)\s*instance",
        r"LinkType[^。\n]{0,100}(?:不是|不等同于)\s*foreign key",
        r"ActionType[^。\n]{0,100}(?:不是|不等同于)\s*endpoint",
        r"DomainEvent(?:Type)?[^。\n]{0,100}(?:不是|不等同于)\s*command",
        r"Policy[^。\n]{0,100}(?:不是|不等同于)\s*validation",
        r"Evidence[^。\n]{0,100}(?:不是|不等同于)\s*inference",
    )
    for pattern in boundaries:
        assert re.search(pattern, plain, re.IGNORECASE), f"missing explicit boundary: {pattern}"


def test_metamodel_yaml_action_is_parseable_and_equal_to_source_example():
    text = _read(DOCS[1])
    fenced = re.findall(r"```yaml\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    parsed = [yaml.load(snippet, Loader=CoreLoader) for snippet in fenced]
    snippets_with_actions = [item for item in parsed if isinstance(item, dict) and "actions" in item]
    assert snippets_with_actions, "metamodel.md needs a parseable fenced actions YAML excerpt"

    excerpt = snippets_with_actions[0]
    assert len(excerpt["actions"]) >= 1
    source = load_structured(ROOT / "examples/service-operations/kinetics.yaml")
    source_actions = {action["id"]: action for action in source["actions"]}
    for action in excerpt["actions"]:
        assert action["id"] in source_actions
        assert action == source_actions[action["id"]], (
            f"documented action {action['id']} differs from kinetics.yaml"
        )

    assert "../spec/v1/ontology-package.schema.json" in text
    assert "../examples/service-operations/kinetics.yaml" in text


def test_all_relative_markdown_links_resolve():
    link_pattern = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
    for path in (*DOCS, *TASK8_DOCS):
        text = _read(path)
        for raw_target in link_pattern.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = target.split("#", maxsplit=1)[0]
            assert target_path, f"empty relative link in {path.name}: {raw_target}"
            resolved = (path.parent / target_path).resolve()
            assert resolved.exists(), f"broken link in {path.name}: {raw_target}"


def test_forward_engineering_has_six_complete_phases():
    text = _read(DOCS[2])
    sections = _heading_sections(text, 2)
    phases = (
        "1. 目标与能力问题（Goals & Competency Questions）",
        "2. 语义建模（Semantic Modeling）",
        "3. 行为建模（Behavior Modeling）",
        "4. 物理绑定（Physical Binding）",
        "5. 系统投影（System Projection）",
        "6. 场景验收（Scenario Acceptance）",
    )
    for phase in phases:
        body = _section_named(sections, phase)
        for column in (
            "Inputs / 输入", "Activities / 活动", "Outputs / 输出",
            "Quality Gate / 质量门", "Rejection Conditions / 拒绝条件",
        ):
            assert column in body, f"{phase} missing {column}"


def test_forward_engineering_defines_norms_scenarios_and_implementation_claim():
    text = _read(DOCS[2])
    for english, chinese in (("MUST", "必须"), ("SHOULD", "应该"), ("MAY", "可以")):
        assert re.search(rf"{english}[^\n]*{chinese}", text)
    for scenario in ("normal", "denied", "compensated"):
        assert scenario in text
    for condition in (
        "stable ID", "运行约束不弱", "权限与审计一致", "binding 定位",
        "digest 一致", "能力问题通过",
    ):
        assert condition in text
    for projection in ("API projection", "storage projection", "policy projection"):
        assert projection in text
    for field in (
        "elementRef", "documentationRef", "runtimeRef", "extensionPointRef",
        "evidenceRefs", "verificationRefs",
    ):
        assert field in text


def test_documents_define_traceability_profile_and_symlink_policy():
    for path in DOCS:
        text = _read(path)
        assert "x-traceability-profile" in text
        assert "唯一事实源" in text
    architecture = _read(DOCS[0])
    assert re.search(r"Package.{0,80}(?:symlink|符号链接).{0,80}(?:禁止|拒绝)", architecture, re.I | re.S)


def test_evolution_governance_covers_versions_workflow_corrections_and_boundaries():
    text = (ROOT / "docs/evolution-governance.md").read_text(encoding="utf-8")
    for term in ("specVersion", "ontologyVersion", "elementRevision"):
        assert term in text
    for state in ("hypothesis", "proposed", "accepted", "deprecated", "retracted"):
        assert state in text
    for stage in (
        "Branch", "Proposal", "Impact Analysis", "Review", "L0", "L1", "L2", "L3", "Release", "Observation"
    ):
        assert stage in text
    for operation in ("rename", "retype", "split", "merge", "relink", "supersede", "retract"):
        assert operation in text
    for strategy in ("coexist", "alias", "dual-read", "temporary dual-write", "backfill", "feature flag", "rollback"):
        assert strategy in text
    assert "机器可验证" in text and "人工决策" in text
    assert "不可变" in text and "不得删除历史" in text


def test_evolution_governance_defines_optimization_metrics_and_walkthrough():
    text = (ROOT / "docs/evolution-governance.md").read_text(encoding="utf-8")
    for metric in (
        "coverage", "conflicts", "orphans", "constraint violations", "action failures",
        "capability pass", "human correction", "breaking impact",
    ):
        assert metric in text
    assert '<a id="v1-v2-walkthrough"></a>' in text
    assert "Actor" in text and "Person" in text and "Organization" in text
    architecture = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    assert "evolution-governance.md" in architecture
