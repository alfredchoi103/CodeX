# Reverse Engineering Discovery

逆向发现把既有系统中的可复核 observation 转换为待治理的 ontology candidate。它不会把推断伪装成事实，也不会因高置信度而自动发布。本流程的机器契约见 [Evidence Graph 示例](../examples/discovery/evidence-graph.yaml)、[DiscoveryClaim 示例](../examples/discovery/claims.yaml)、[人工裁决示例](../examples/discovery/adjudication.yaml) 与 [置信度规范](discovery-confidence.md)。

仓库中的 discovery 文件是 **fully synthetic / 完全合成**演示；其 URI、内容与 hash 仅用于说明数据形状，**not admissible / 不可采信**为真实系统证据或治理依据。

程序化验证必须显式传入版本化 schema 路径，例如 `validate_discovery_bundle(evidence_graph, claims_document, schema_path)`；API 不推测当前目录、环境变量或隐式默认路径。

DiscoveryClaim 是不可变的 proposed snapshot。人工 reviewer 在独立 Adjudication Document 中逐 claim 记录 accepted、needsRevision、rejected 或 deferred；决定不会回写历史 claim。只有 accepted decision 才可创建 baseline promotion proposal，仍须经过正常治理与发布门禁。

## 证据源与边界

必须至少考虑四类来源：database 目录与约束、OpenAPI 操作契约、code 与 config 静态结构、event log 运行记录。数据库表名不自动等于业务对象，endpoint 不自动等于 ActionType，类名不自动等于概念，事件出现也不证明事务原子性。

**Observation（观察）**是带 `sourceUri`、精确 `location`、采集时间、内容哈希、提取器版本与 `observedFacts` 的可复核记录。**Inference（推断）**是由规则解释 observation 后形成的 DiscoveryClaim。推断只能引用证据，不能回写或冒充 observation。

## 七阶段流水线

### 1. 采集

- **输入：** 获准访问的 database、OpenAPI、code、config 与 event log 快照。
- **输出：** 不可变内容、来源定位、时间、SHA-256 与提取器版本。
- **门禁：** 来源不可定位、授权不明、哈希缺失或采集不完整时拒绝进入下一阶段。

### 2. 归一化 Evidence Graph

- **输入：** 已采集快照与提取器输出。
- **输出：** 闭合 `evidenceGraph`，每个 observation 只陈述源中可直接复核的事实。
- **门禁：** observation 不得包含“因此是业务对象”等 inference；重复 ID、空事实或不可复核位置均失败。

### 3. deterministic inference

- **输入：** Evidence Graph 与版本化确定性规则集。
- **输出：** 带 rule ID 的候选 identity、cardinality、state、action、policy 与 constraint claims。
- **门禁：** 同样输入、规则版本与提取器版本必须产生同样结果；无法说明规则链的 claim 被拒绝。

典型推断包括：唯一且非空的跨源标识符形成对象身份候选；数据库枚举约束与代码 guard 共同形成状态集候选；OpenAPI operation、代码 precondition 和运行事件共同形成 action 候选；事件字段反复共现形成关联候选。这些仍是候选，不是事实。

### 4. semantic-assisted matching

- **输入：** 确定性 candidates、术语表与可选语义模型。
- **输出：** 同义词、可能重复概念、命名建议与替代解释。
- **门禁：** 语义模型输出必须作为推断记录 provenance，不得成为 EvidenceObservation，也不得覆盖规则或原始文本。

### 5. conflict retention

- **输入：** 全部 candidates、支持证据与反证。
- **输出：** 保留 `counterEvidenceRefs`、反证评估与 alternatives 的 DiscoveryClaim。
- **门禁：** 删除不一致来源、只保留多数意见或把“未找到”写成“没有”均失败。

例如，OpenAPI 与代码可能声称提交后立即可读，而 event log 显示事件早于 read-model 更新。系统必须同时保留“同步 postcondition”与“最终一致投影”两种解释，并降低 runtime support，而不是选择更方便的一方。

### 6. human adjudication

- **输入：** 完整 claim、置信度、证据、反证、falsifiers、验证问题与能力问题。
- **输出：** 有责任人的批准、拒绝、要求修改或补证决定。
- **门禁：** Grade A 仍只能是 candidate；没有人工治理记录不得变为 `accepted`。

### 7. Baseline Ontology

- **输入：** 经裁决的 claims、稳定 ID 规则与治理约束。
- **输出：** Baseline Ontology proposal、来源追溯与验证场景。
- **门禁：** 只有批准且验证问题已闭合的内容可提升；未解决冲突、隐私风险或证据失效必须阻止发布。

## 安全、隐私与失败处理

采集必须最小权限、最小数据和目的限定。event log 应先脱敏，不得把密钥、个人数据或业务载荷复制进 observed facts；source URI 可以指向受控存储，但不得泄露凭据。提取器超时、格式漂移、部分读取、哈希变化或权限撤销时，必须标记运行失败并保留上次快照的失效状态，禁止静默复用。来源无法访问不是“无反证”。任何阶段失败都应产生可审计报告，且不会自动接受或覆盖现有 Baseline Ontology。
