# 可执行业务 Ontology / Executable Business Ontology

本仓库定义一个跨行业的可执行业务 Ontology（Executable Business Ontology, EBO）MVP：以可审计、可版本化的 Ontology Package 连接业务语义、行为契约、物理绑定、证据与持续演进。Package 是单一事实源（Single Source of Truth），文档、RDF/OWL、SHACL 与其他契约是多投影（Multi-projection），不能反向成为隐式权威。

## 四种能力与四层模型

框架支持四种能力：设计 Ontology；从 Ontology 正向构建系统契约；从数据库、OpenAPI、代码与事件证据逆向发现候选 Ontology；通过证据、版本、迁移与反馈持续纠错和优化。

- **Semantics**：对象、属性、关系、接口、不变量与业务术语。
- **Kinetics**：动作、查询、状态机与领域事件。
- **Binding & Runtime**：数据、API、代码与事件绑定，以及身份、同步和一致性契约。
- **Governance & Evolution**：策略、证据、审批、版本、迁移和 lineage。

当前 MVP A 的边界是文档、JSON Schema、SHACL、静态验证器和可复核示例；它**不包含运行引擎**、live connector、代码生成服务或 Web UI，也不声称已部署 runtime。运行执行与 UI 属于未来实现。

## Repository map

- [`docs/index.md`](docs/index.md)：三条阅读路径、规范依赖顺序与 design coverage。
- [`spec/v1/ontology-package.schema.json`](spec/v1/ontology-package.schema.json)：Package 结构权威。
- [`spec/v1/ontology.shacl.ttl`](spec/v1/ontology.shacl.ttl)：RDF 图约束。
- [`examples/service-operations/manifest.yaml`](examples/service-operations/manifest.yaml)：四层完整服务示例。
- [`examples/discovery/claims.yaml`](examples/discovery/claims.yaml)：逆向发现与置信度示例。
- [`examples/evolution/migration.yaml`](examples/evolution/migration.yaml)：v1→v2 纠错和迁移示例。
- [`scripts/validate_package.py`](scripts/validate_package.py)：component-level Package validator。
- [`scripts/validate_release.py`](scripts/validate_release.py)：统一静态发布验证入口。
- [`tests/test_release.py`](tests/test_release.py)：发布层级与 mutation 验收。

## Installation

需要 **Python 3.11** 或更高版本。推荐使用独立虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
```

## Quick commands

Package component check（不颁发 L 级结论）：

```bash
python -m scripts.validate_package examples/service-operations
```

统一静态发布验证（L0–L3-static；不执行 runtime，也不连接 live system）：

```bash
python -m scripts.validate_release examples/service-operations
```

完整测试：

```bash
python -m pytest
```

## Walkthroughs

### Service operations

从 [`manifest.yaml`](examples/service-operations/manifest.yaml) 确认身份与摘要，依次查看 [`semantics.yaml`](examples/service-operations/semantics.yaml)、[`kinetics.yaml`](examples/service-operations/kinetics.yaml)、[`bindings.yaml`](examples/service-operations/bindings.yaml)、[`policies.yaml`](examples/service-operations/policies.yaml) 与 [`traceability.yaml`](examples/service-operations/traceability.yaml)，最后运行静态发布验证。该流程验证结构、引用、SHACL、状态可达性、binding/evidence、traceability 与投影摘要；它不探测示例 URI。

### Discovery

阅读 [`evidence-graph.yaml`](examples/discovery/evidence-graph.yaml)、[`claims.yaml`](examples/discovery/claims.yaml) 与 [`adjudication.yaml`](examples/discovery/adjudication.yaml)，观察事实、proposed claim snapshot 与 human decision 如何分离，以及 accepted decision 如何进入 baseline promotion proposal。

### Evolution

比较 [`v1 manifest`](examples/evolution/v1/manifest.yaml) 和 [`v2 manifest`](examples/evolution/v2/manifest.yaml)，再阅读 [`migration.yaml`](examples/evolution/migration.yaml)。这两个历史 Package 继续使用 component validator；跨版本 breaking-change、lineage、backfill 与 rollback 由 evolution 测试验收，不要求 RDF 投影。

## 来源致谢 / Source acknowledgements

设计吸收并明确限定了 Palantir Foundry Platform Python SDK、Palantir API v2 概念资料、Microsoft Ontology Playground，以及 W3C RDF 1.1、OWL 2、SHACL、JSON Schema 2020-12 和 OpenAPI 3.1.1。它们提供实现信号、比较对象或开放标准边界，不构成产品兼容性声明。完整来源、固定 revision 与采用边界见 [`docs/interoperability.md`](docs/interoperability.md)。
