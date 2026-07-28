# EBO Conformance Profile

本文定义 Executable Business Ontology（EBO）Package 的分级符合性、发布阻断条件与可操作报告。适用对象是本仓库规范的 YAML/JSON Package、RDF 投影及其证据；不把产品映射或运行平台认证纳入符合性。结构权威见 [JSON Schema](../spec/v1/ontology-package.schema.json)，图约束见 [SHACL shapes](../spec/v1/ontology.shacl.ttl)，概念边界见 [Metamodel](metamodel.md)。

## 规范性术语

- **MUST（必须）**表示符合性或发布不可缺少的要求。
- **SHOULD（应该）**表示默认要求；偏离必须记录理由、风险与批准人。
- **MAY（可以）**表示受控可选项。

符合性是递进的：通过 L*n* 必须先通过所有较低级别。`validate_package` 继续只执行 **component-level** checks，不颁发 L 级结论。统一入口 `python -m scripts.validate_release` 汇总当前可机器执行的 **L0-L3-static** 发布规则；成功只证明静态规则通过，仍不执行 runtime、不连接 live 外部系统，也不替代人工证据质量、风险接受与最终发布决定。

## L0 Syntactic

### Inputs

Package 目录、八个规范文件、[JSON Schema](../spec/v1/ontology-package.schema.json) 与 manifest 声明。

### Checks

检查文件集合且拒绝 symlink；解析 YAML/JSON；按 Schema 校验类型、必填字段、枚举、稳定 ID 与 SemVer 格式；重算规范化 Package `contentDigest` 并与 `manifest.yaml`、`traceability.yaml` 比对。YAML 结构必须可确定地解释，不允许重复键或未识别的结构逃逸。

### Failure Report

报告 structural 类 Finding，给出 `level`、`class`、`rule`、`path`、`element`（无法识别时为 `package`）、`message` 与 `fix`；文件位置编码在 `path` 中。

### Pass Criteria

所有输入可加载、结构满足 Schema、文件边界合法且 digest 一致；任何 structural error 都阻断 L1 与发布。

## L1 Semantic

### Inputs

已通过 L0 的 Package、[SHACL shapes](../spec/v1/ontology.shacl.ttl) 与 RDF 投影。

### Checks

解析内部/外部引用；核对值类型、键、relationship 端点与 cardinality；执行 SHACL。版本化 `x-rdf-projection-profile` 是 semantic/kinetic RDF 投影集合的单一事实源：验证器双向比较 Package 与 RDF 的 stable ID、RDF class 和 label exact parity，拒绝缺失、多余、错类型或错标签节点。显示名称变化不得制造新身份，物理 foreign key 不得替代业务 LinkType。

### Failure Report

报告 semantic 类 Finding，使用原生 `class`、`rule`、`path`、`element`、`message` 与 `fix` 字段；若 RDF 投影与 Package 冲突，`path` 和 `message` 同时标记权威 Package 与投影位置。

### Pass Criteria

L0 保持通过，所有引用可解析、类型/键/基数一致且 SHACL 无 violation；semantic error 阻断 L2 与发布。

## L2 Behavioral

### Inputs

已通过 L1 的 Semantics、Kinetics、Policies、能力问题与场景。

### Checks

检查每个 ActionType 都有非空 effects、`permissionRefs` 与 `auditRefs`，且声明 `sideEffectRefs` 时也声明 `compensationRefs`；三类引用分别只能指 AuthorizationPolicy、AuditPolicy 与 ActionType。每个 StateMachine 用 `subjectRef` 标明 ObjectType 主体；每个 Transition 必须在对应 Action 的 `stateTransitions` 中存在 exact tuple `(subjectRef, fromStateRef, toStateRef)`，不使用 expression substring 推测状态闭合。另检查状态可达性、QueryType、DomainEventType、DiscoveryClaim confidence 与 evolution semantics。

### Failure Report

报告 behavioral 类 Finding，必须以 `element` 标出动作或状态机，以 `path` 定位文件和字段，并提供 `rule`、`message` 与可执行 `fix`；策略缺失与置信度不合规分别注明关联引用。

### Pass Criteria

L1 保持通过；每个 accepted 行为具有闭合前置条件、效果、状态、权限、审计及必要补偿，相关 capability questions 有可复核验收场景。behavioral error 阻断 L3 与发布。

## L3 Operational

### Inputs

已通过 L2 的 Bindings、Evidence、Migrations、Traceability、投影摘要及静态运行契约。

### Checks

检查 binding source/target 与 mapping 可解析、方向明确、运行约束不弱于 Ontology。Target 类型由 RDF projection profile 派生：`dataBindings → ObjectType`，`apiBindings → ActionType / QueryType`，`eventBindings → DomainEventType`；`codeBindings` 只允许 profile 中明确的 semantic/kinetic classes，所有 mapping `ontologyPath` 也只能指向 Semantics/Kinetics ID，禁止 Evidence、Approval、Policy、Change 等治理 ID。

检查 evidence 哈希、类型、批准、traceability 精确覆盖与 digest。非空 **Package migrations** 复用 evolution 语义：`split` 至少两个 successors、`merge` 至少两个 predecessors、`retract` 的 successors 为空；change 与 lineage 必须双向 one-to-one，无 duplicate 或 cycle，并具备 cause、evidence、impact、migration、rollback 与 acceptance 内容。Package 内校验不臆造 from/to version，因此不执行不适用的 version bump。另核对 runtimeRef 或 extensionPointRef 与验证引用。

**L3-static 是静态发布验收范围**：统一入口组合 Package、SHACL、文档、behavior、binding、evidence、traceability 与投影 digest 检查。Service release 若没有版本间变更，不强制存在 evolution migration；v1→v2 的 breaking-change、lineage、backfill 与 rollback 由独立 evolution validator/test 验收。该范围**不含 live connector，不连接或探测外部系统**，也不执行 Action runtime，不证明凭据、网络、数据新鲜度或真实事务成功。真正 Operational L3 仍需要未来 connector/contract-test profile，不能从静态通过推断。

### Failure Report

报告 binding、evidence 或 evolution 类 Finding，必须给出 `class`、`element`、绑定/证据/迁移 `path`、`rule`、`message` 与最小 `fix`；外部连通性“未测试”是范围声明，不可伪报为通过。

### Pass Criteria

L2 保持通过；静态绑定可解析、证据和追溯闭合、摘要一致，适用的破坏性迁移具备安全路径。任何 binding/evidence/evolution error 阻断发布。`PASS … L0-L3-static` 可以记录机器静态门禁结果，但不得写作 live operational certification；人工发布审阅仍需独立完成。

## 错误分类与阻断规则

| Error class | 典型错误 | Block condition |
|---|---|---|
| `structural` | 文件、Schema、格式、digest 错误 | 阻断 L1–L3 与 release |
| `semantic` | 悬空引用、类型/键/基数冲突、SHACL violation | 阻断 L2–L3 与 release |
| `behavioral` | 前置/效果矛盾、非法状态、权限/审计/补偿缺失 | 阻断 L3 与 release |
| `binding` | target/source 不可解析、映射或方向缺失 | 阻断 release |
| `evidence` | 证据不可复核、hash/approval/traceability 缺失 | 阻断 accepted 声明与 release |
| `evolution` | 破坏性变化无 lineage、迁移、回填或回滚 | 阻断 proposal merge 与 release |

`MUST` 失败、未豁免的 `SHOULD` 失败或任一 error 使 release decision 为 `BLOCK`。豁免只适用于 SHOULD，必须有 owner、理由、到期日与风险；不能豁免 Schema、引用完整性、stable identity、权限或证据真实性。

## 完整质量门禁清单

- [ ] **命名**：术语清晰、无保留字/歧义冲突。
- [ ] **单概念**：每个类型只表达一个业务概念。
- [ ] **stable identity**：稳定 ID、业务键与版本历史一致。
- [ ] **relationship**：两端、方向、语义和 cardinality 闭合。
- [ ] **action audit**：preconditions/effects/state/authorization/audit/compensation 可追溯。
- [ ] **binding**：目标、来源、字段映射、方向及约束可解析。
- [ ] **evidence**：来源、hash、范围、confidence 与 approval 可复核。
- [ ] **orphan**：无未解释的孤立 accepted 元素或证据。
- [ ] **cycle**：无禁止的 lineage、自引用依赖或迁移 cycle。
- [ ] **breaking migration**：impact、lineage、backfill、compatibility window、rollback 完整。
- [ ] **capability questions**：正常、拒绝、补偿与演进场景有验收证据。

只有全部 MUST 项、四级依赖和适用的人工审阅通过，release decision 才为 `PASS`；否则为 `BLOCK`，并保留完整错误列表，禁止只报告首个错误。

## Validator 命令与报告

`python -m scripts.validate_package` 只是 **component-level** Package 检查，覆盖 L0 与部分 L1/L2/L3 evidence 相关规则；它没有按级别选择参数，不颁发 L 级认证。`validate_release` 是当前 service Package 的统一静态发布入口；evolution v1→v2 仍由独立测试验证：

```bash
python -m scripts.validate_package examples/service-operations \
  --schema spec/v1/ontology-package.schema.json
python -m scripts.validate_release examples/service-operations
python -m pytest -q tests/test_shacl.py
python -m pytest -q tests/test_evolution.py
python -m pytest -q
```

component validator 成功输出 Package 路径。统一入口成功输出 `PASS <ontologyId>@<ontologyVersion> L0-L3-static`。验证按依赖渐进执行：L0 fail 时 L1–L3 `blocked`；L1 fail 时 L2–L3 `blocked`；L2 fail 时 L3 `blocked`。失败层输出 `Finding`，blocked 层只输出稳定 status。每条 Finding 原生包含 `class`、`rule`、`path`、`element`、`message` 与 `fix`：

```text
level=L2 class=behavioral rule=EBO-L2-ACTION-AUDIT path="kinetics.yaml:actions/0/auditRefs" element="submitServiceRequest" message="action 'submitServiceRequest' requires at least one auditRefs entry" fix="complete the action and state-machine behavioral contract"
```

## 正常、反例与演进证据

- Normal：完整 [service-operations Package](../examples/service-operations/) 及其 [ontology.ttl](../examples/service-operations/ontology.ttl)。
- Negative：[ontology-invalid.ttl](../examples/service-operations/ontology-invalid.ttl) 演示 SHACL 图约束失败；它不是可发布 Package。
- Discovery：[claims.yaml](../examples/discovery/claims.yaml) 与 [evidence graph](../examples/discovery/evidence-graph.yaml) 演示 evidence/confidence 输入。
- Evolution：[v1→v2 migration](../examples/evolution/migration.yaml)、[v1](../examples/evolution/v1/) 和 [v2](../examples/evolution/v2/) 演示 breaking migration、lineage 与 rollback 门禁。

发布解释、生命周期与运行边界见 [Architecture](architecture.md)，纠错规则见 [Evolution Governance](evolution-governance.md)，产品/标准映射见 [Interoperability](interoperability.md)。
