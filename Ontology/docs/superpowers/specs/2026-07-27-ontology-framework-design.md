# 可执行业务 Ontology 框架设计规格

状态：MVP A 已实现并完成静态发布准备
日期：2026-07-27
语言：中文正文，关键术语保留中英双语
范围：跨行业通用 MVP；文档、机器可读标准与示例，不包含运行引擎和 Web UI

## 1. 目标

本项目定义一套能够连接业务语义、系统实现与持续演进的 Ontology 方法和标准。它必须同时支持四种能力：

1. 用清晰、可审计的方式设计 Ontology。
2. 从 Ontology 正向构建系统边界、接口、数据映射、策略和测试契约。
3. 从数据库、OpenAPI、代码、配置和事件日志逆向发现候选 Ontology。
4. 通过证据、版本、提案、迁移和运行反馈持续纠错与优化 Ontology。

本框架采用“可执行业务 Ontology（Executable Business Ontology）优先”的路线：内部权威模型表达对象、关系和行为，并将 RDF/OWL/SHACL 作为标准交换与验证投影，而不是把语义网格式直接当作唯一运行模型。

## 2. 设计原则

### 2.1 语义与行为不可分离

Ontology 不只是名词目录。它同时描述：

- Semantics：世界中有哪些对象、属性、关系和约束。
- Kinetics：允许查询什么、执行什么动作、发生什么状态转换以及产生什么副作用。

只有语义而没有动作的模型难以驱动业务系统；只有领域代码而没有显式语义的系统又无法被一致地理解、治理和演进。

### 2.2 单一事实源，多种投影

`Ontology Package` 是唯一权威源。文档、运行契约、RDF/OWL、SHACL、JSON Schema 和 OpenAPI 都是从 Package 生成的投影，不能互相作为事实源。

每个投影必须携带：

- `ontologyId`
- `ontologyVersion`
- `specVersion`
- `contentDigest`

这些字段用于证明文档模型和运行模型来自同一版本。生成物不得直接编辑；手工实现只能通过显式 Extension Point 扩展，不能覆盖 Ontology 的标准语义。

### 2.3 业务能力优先于物理结构

对象类型来自业务概念和能力问题，而不是逐表映射数据库。表、端点、类和消息只是来源证据与绑定目标。物理系统可帮助发现候选概念，但不能单独决定业务含义。

### 2.4 所有结论可解释、可证伪

自动发现结果必须说明原因、证据、反证、备选解释和置信度。LLM 输出可以辅助推理和语义匹配，但不能自身充当证据。

### 2.5 发布版本不可变，错误可以被修正

已发布版本不可原地修改。错误定义通过带 lineage 的重命名、重分类、拆分、合并、重连、替代或撤销操作修正，历史含义和审计记录必须始终可解释。

## 3. 总体架构

### 3.1 语义层 Semantics

语义层定义业务世界的稳定结构：

- `ObjectType`：单一业务概念及其实例身份。
- `PropertyType`：对象属性、值类型、可空性、单位和约束。
- `LinkType`：带方向、语义、角色和基数的对象关系。
- `InterfaceType`：多个对象类型共享的能力或结构契约。
- `ValueType`：基础、枚举、结构、引用、时间、空间和度量类型。
- `Invariant`：跨属性或跨对象必须持续成立的业务不变量。
- `BusinessTerm`：业务词汇、别名、定义和上下文。

所有正式元素具有稳定 ID。名称可以修改或成为别名，稳定 ID 不随显示名称变化。

### 3.2 行为层 Kinetics

行为层定义系统如何读取和改变业务世界：

- `ActionType`：参数、目标、前置条件、效果、权限、副作用和补偿。
- `QueryType`：参数、对象范围、过滤、投影、聚合和返回类型。
- `StateMachine`：状态、转换、触发器、守卫条件和终态。
- `DomainEventType`：已发生的业务事实、载荷和关联对象。
- `Policy`：主体在何种上下文下可以读取或执行何种行为。
- `TransactionBoundary`：原子编辑集合、一致性与幂等要求。

动作执行必须产生可审计结果。接收请求不等于动作成功；结果必须区分验证失败、权限拒绝、业务冲突、部分副作用失败和成功提交。

### 3.3 绑定与运行层 Binding & Runtime

绑定层把抽象 Ontology 与物理系统连接：

- `DataBinding`：表、视图、流、字段、键和对象属性之间的映射。
- `ApiBinding`：OpenAPI operation、参数、响应和 Action/Query 之间的映射。
- `CodeBinding`：模块、类型、函数、配置和 Ontology 元素之间的映射。
- `EventBinding`：topic、消息 schema、事件类型和对象身份之间的映射。
- `IdentityResolution`：业务键、复合键、外部 ID 和去重策略。
- `SyncPolicy`：批处理、流处理、延迟、冲突解决和数据新鲜度。
- `ConsistencyPolicy`：读写一致性、事务边界、重试与幂等策略。

绑定必须保留来源证据和方向，明确是 source-to-ontology、ontology-to-system 还是双向映射。

### 3.4 治理与演进层 Governance & Evolution

治理层定义：

- Owner、Steward、Reviewer 和 Consumer 的职责。
- 元素级与行为级权限。
- 变更 Branch、Proposal、Review、Validation 和 Release 流程。
- 审计、数据质量、证据质量和合规要求。
- 兼容性分类、迁移、回滚、弃用和撤销。
- 运行反馈如何触发 Evolution Proposal。

## 4. Ontology Package

一个完整 Package 至少包含：

```text
ontology-package/
├── manifest.yaml
├── semantics.yaml
├── kinetics.yaml
├── bindings.yaml
├── policies.yaml
├── evidence.yaml
└── migrations.yaml
```

### 4.1 文件职责

- `manifest.yaml`：身份、版本、命名空间、依赖、负责人、发布状态与摘要。
- `semantics.yaml`：对象、属性、关系、接口、值类型和不变量。
- `kinetics.yaml`：动作、查询、状态机、事件、副作用和补偿。
- `bindings.yaml`：数据库、API、代码、配置与事件流映射。
- `policies.yaml`：权限、审计、数据质量和合规规则。
- `evidence.yaml`：原始证据引用、DiscoveryClaim 与批准记录。
- `migrations.yaml`：版本差异、兼容性、元素 lineage 和迁移步骤。

JSON 是 YAML 的规范等价表示。JSON Schema 是结构验证的权威约束；SHACL 验证图语义；RDF/OWL 是互操作投影。若投影结果发生冲突，以 Package 和其对应 `specVersion` 的规范转换规则为准。

## 5. 文档模型与运行模型的关联

### 5.1 文档投影

文档投影至少生成：

- 概念词典与元模型参考。
- 对象—属性—关系目录。
- 动作、查询、状态机和事件目录。
- 数据与 API 绑定表。
- 权限与审计矩阵。
- 来源证据、可信度和批准状态。
- 版本差异、迁移和弃用说明。

### 5.2 运行投影

未来运行实现可以从同一 Package 生成：

- 语言类型和 SDK。
- API 合约与客户端接口。
- 输入、状态和不变量校验器。
- 状态机与动作执行契约。
- 权限策略和审计事件格式。
- 数据、API 与事件映射配置。
- Contract Test 和验收场景骨架。

### 5.3 可追溯性矩阵

每个 Ontology 元素必须能追踪到：

1. Package 中的稳定 ID 和定义位置。
2. 解释该元素的文档章节。
3. 实现该元素的运行组件或扩展点。
4. 支持该定义的来源证据。
5. 验证该元素的规则与测试契约。

运行系统产生的失败、漂移和新证据不能直接修改 Ontology，而是进入 Proposal 流程：

```text
Ontology Package
  → 文档投影 / 运行投影
  → 运行证据与纠正反馈
  → Evolution Proposal
  → 审核与验证
  → 新版 Ontology Package
```

## 6. 从 Ontology 正向构建系统

正向方法采用以下阶段：

1. **目标与能力问题**：定义业务目标，以及 Ontology 必须能够回答或执行的问题。
2. **语义建模**：识别对象、身份、属性、关系、术语和不变量。
3. **行为建模**：定义动作、查询、状态转换、事件、权限和审计结果。
4. **物理绑定**：连接数据库、API、代码、配置和事件流。
5. **系统投影**：生成边界、接口、存储映射、策略和 Contract Test。
6. **场景验收**：用能力问题、正常流程、拒绝路径和补偿路径验证实现。

一个系统只有同时通过以下检查，才能声明“由该 Ontology 构建”：

- 所有被实现的对象与动作均能追踪到稳定 ID。
- 运行约束不弱于 Ontology 约束。
- 权限与审计语义一致。
- 绑定可定位到实际接口或数据源。
- 文档与运行投影的摘要一致。
- 能力问题和关键动作场景通过验收。

## 7. 从系统逆向发现 Ontology

### 7.1 证据采集

首版覆盖四类系统证据：

- 数据库：表、列、键、约束、视图、注释和变更历史。
- OpenAPI：schema、operation、路径、参数、响应和安全定义。
- 代码与配置：类型、服务、函数、状态枚举、授权规则和映射配置。
- 事件日志：事件类型、载荷、时序、关联 ID、动作结果和错误。

每项证据记录来源 URI、内容位置、采集时间、内容哈希、提取器版本和可见范围。

### 7.2 Evidence Graph

所有证据先归一化为 Evidence Graph，再进行概念推断。Evidence Graph 区分“观察事实”和“推断结论”，防止候选语义被误当成来源事实。

典型推断包括：

- 主键、唯一约束与跨源 ID 支持对象身份候选。
- 外键、连接表、API 嵌套和运行关联支持关系候选。
- 写操作、命令函数和事件序列支持动作与状态转换候选。
- 授权配置和拒绝日志支持策略候选。
- 字段共现、命名和调用上下文支持概念聚类，但不能单独证明业务语义。

### 7.3 冲突处理

发现过程必须保留冲突。例如数据库存在外键，但代码与日志从未使用该关系，系统应输出低置信候选和冲突说明，而不是直接确认关系。

自动发现只产生候选 Ontology。正式元素必须具有负责人、审核状态和批准记录。

## 8. 自动发现的自证与可信度

### 8.1 DiscoveryClaim

每个候选元素必须对应一个 `DiscoveryClaim`，至少包含：

- `claim`：候选结论和目标元素。
- `reasoningRules`：使用的显式推理规则。
- `supportingEvidence`：可复核的证据引用。
- `counterEvidence`：不支持或冲突的证据。
- `alternatives`：其他合理解释及其差异。
- `confidence`：总分、等级、维度分数和扣分原因。
- `falsifiers`：会推翻或改变结论的新证据条件。
- `validationQuestions`：领域负责人需要回答的问题。
- `capabilityQuestions`：该候选能回答或支持的问题。
- `provenance`：提取器、规则集、模型、时间和版本。

### 8.2 置信度模型

置信度由透明维度计算，不允许语言模型直接给出无依据分数：

| 维度 | 权重 |
|---|---:|
| 跨来源一致性 | 25% |
| 证据覆盖与可追溯性 | 20% |
| 运行时行为支持 | 20% |
| 语义明确程度 | 15% |
| 约束与命名一致性 | 10% |
| 反证与冲突惩罚 | 10% |

反证维度以“无冲突得满分，存在冲突按规则扣分”的方式计算。总分映射为：

- A，85–100：强证据候选，可进入快速审核。
- B，70–84：可信候选，需要人工确认语义。
- C，50–69：探索性假设，不得进入正式 Ontology。
- D，0–49：仅保留为线索。

任何等级都不能跳过治理流程自动发布。

### 8.3 机器自我理解标准

一个自动发现器只有能够对候选结论回答以下问题，才满足本规范：

1. 我认为它是什么？
2. 我为什么这样认为？
3. 我的证据来自哪里？
4. 哪些事实与判断冲突？
5. 还有哪些合理解释？
6. 什么新证据会改变结论？
7. 它能回答哪些能力问题，支持哪些系统行为？

## 9. 一致性级别与质量门禁

### 9.1 Conformance Levels

- **L0 Syntactic**：所有文件满足 JSON Schema，标识与格式合法。
- **L1 Semantic**：引用、类型、键、基数和 SHACL 图约束一致。
- **L2 Behavioral**：动作前置条件、效果、状态转换、补偿与权限无冲突。
- **L3 Operational**：绑定可解析，证据可追溯，迁移完整，文档和运行投影摘要一致。

MVP 示例必须通过 L0–L3 的静态规范验证。MVP 不实现真实运行引擎，因此 L3 中涉及外部连接的部分以可验证绑定描述和验收清单为准。

### 9.2 质量门禁

发布检查至少包括：

- 命名清晰，业务概念使用单数名词，关系使用具体动词语义。
- 每个对象只表达一个主要业务概念。
- 对象身份稳定且键策略明确。
- 关系方向、角色和基数明确。
- 动作具有前置条件、权限、效果和审计定义。
- 数据与接口绑定不存在悬空引用。
- 正式元素满足最低证据和批准要求。
- 不存在未解释的孤立对象或循环依赖。
- 破坏性变更具有迁移和回滚策略。
- 能力问题与关键场景具有对应验证项。

## 10. 版本、纠错与持续优化

### 10.1 三层版本

- `specVersion`：Package 格式和验证语义的版本。
- `ontologyVersion`：特定业务 Ontology 的语义版本。
- `elementRevision`：单个元素的修订历史。

`ontologyVersion` 采用语义化版本：

- Patch：描述、证据或不改变语义的元数据修正。
- Minor：向后兼容地增加元素、属性或动作。
- Major：删除、重命名、拆分、合并、改变基数或行为语义。

若一次 Proposal 同时包含多类变更，使用影响最大的版本等级。

### 10.2 认识状态

元素在发现和治理过程中的状态为：

```text
hypothesis → proposed → accepted → deprecated
                                ↘ retracted
```

- `hypothesis`：尚未达到正式候选要求。
- `proposed`：具备 DiscoveryClaim，等待审核。
- `accepted`：已批准并进入发布版本。
- `deprecated`：仍可解释但不应在新实现中使用。
- `retracted`：结论被判定为错误；保留历史与撤销原因。

### 10.3 修正操作

错误不能通过删除历史掩盖。规范支持：

- `rename`：保持稳定 ID，旧名称成为别名。
- `retype`：改变类型并提供值转换规则。
- `split`：一个概念拆分为多个概念，并提供分类与回填规则。
- `merge`：多个重复概念合并，并提供身份去重规则。
- `relink`：修正关系方向、角色、基数或语义。
- `supersede`：新元素明确替代旧元素。
- `retract`：撤销错误结论并记录原因、证据与影响。

每次修正必须记录原定义、新定义、错误成因、新证据、影响范围、迁移、回填、回滚、兼容期和验收结果。

### 10.4 变更流程

所有变更遵循：

```text
Branch → Proposal → Impact Analysis → Review
       → L0–L3 Validation → Release → Observation
```

Proposal 必须包含语义差异，而不仅是文本差异。Impact Analysis 覆盖对象数据、API、动作、查询、权限、绑定、文档、历史审计和下游消费者。

### 10.5 兼容与迁移

迁移期可使用：

- 旧新版本并存。
- 稳定 ID 与别名解析。
- 双读比较。
- 仅在确有一致性需求时使用的临时双写。
- 数据回填与重放。
- Feature Flag 和分阶段切换。
- 回滚到上一个不可变版本。

所有映射保存在 lineage 中，使旧数据、旧审计日志和旧文档在未来仍可解释。

### 10.6 演进触发器与效果指标

运行反馈包括数据漂移、约束失败、未映射 API、动作失败、用户纠正、术语变化和新业务能力。系统可以定期生成 Evolution Proposal，但不得自动发布。

版本优化效果通过以下指标比较：

- 证据覆盖率与跨源一致性。
- 未知项、冲突项和孤立元素数量。
- 约束违规率和动作失败率。
- 系统覆盖率与能力问题通过率。
- 人工纠正率和自动发现准确率。
- 破坏性变更影响范围。

## 11. 错误处理

规范区分以下失败类型：

- 结构错误：Package 不满足 JSON Schema，阻止进入 L1。
- 语义错误：引用、类型、基数或 SHACL 约束冲突，阻止进入 L2。
- 行为错误：状态转换、权限、前置条件或补偿矛盾，阻止进入 L3。
- 绑定错误：来源不存在、键不匹配或映射不完整，阻止发布。
- 证据错误：引用不可复核、哈希变化或来源范围不足，候选降级或退回。
- 演进错误：缺少迁移、回滚或影响分析，Proposal 不得合并。

验证报告必须定位到元素 ID、文件位置、规则 ID，并提供可操作的修复说明。

## 12. 验证策略

MVP 采用静态、往返与场景验证：

1. 所有示例 Package 必须通过 JSON Schema。
2. Package 转为 RDF 后必须通过 SHACL。
3. YAML → JSON → YAML 的规范字段不得丢失。
4. RDF/OWL 往返允许保留映射声明中列出的表示差异，但不得改变稳定 ID、类型和关系语义。
5. 正向示例必须能从能力问题追踪到模型、绑定和验收项。
6. 逆向示例必须包含支持证据、反证、置信度和人工裁决。
7. 版本示例必须覆盖 rename、split、merge 和 retract，并验证 lineage。
8. 文档与运行投影示例必须具有相同 `contentDigest`。

## 13. MVP 交付结构

后续实施将形成：

1. 架构与设计原则。
2. Ontology Package 标准与元模型参考。
3. 从 Ontology 正向构建系统的方法指南。
4. 从系统逆向发现 Ontology 的方法指南。
5. 自动发现、自证与可信度规范。
6. 版本、治理、纠错与持续演进指南。
7. JSON Schema、SHACL 和完整 YAML 示例。
8. Palantir、Microsoft、RDF/OWL/SHACL 概念映射表。
9. L0–L3 一致性级别、质量门禁与验收清单。

## 14. 参考来源与采用边界

### 14.1 Palantir Foundry Platform Python SDK

采用的设计信号包括：Object Type、Link、Action、Query、Object Set、Transaction、Branch、Scenario、Edit History、权限与审计相关 API 形态。该 SDK 用于验证一个可执行 Ontology 需要明确的读写、事务、版本上下文和动作结果语义。本项目不复制 Palantir 私有实现。

来源：<https://github.com/palantir/foundry-platform-python/tree/develop>

### 14.2 Palantir API v2 Introduction

该页面被列为正式参考源；当前研究环境的浏览器安全策略禁止访问 `palantir.com`，因此本设计没有声称逐项核验该页面内容。实施文档只引用能够从官方 SDK 或公开可访问材料独立验证的 API 概念。

来源：<https://www.palantir.com/docs/foundry/api/v2/general/overview/introduction/>

### 14.3 The Palantir Impact

采用其“Operational Layer”“Semantics + Kinetics”“Objects/Links/Actions”“Indexing”“Branch/Proposal/Review”和 Action Log 等架构解释，作为方法论参考。该文档是二级分析材料，不替代官方规范。

来源：<https://github.com/Leading-AI-IO/palantir-ontology-strategy/blob/main/docs/the-palantir-impact_en.md>

### 14.4 Microsoft Ontology Playground

采用其实体、属性、关系、数据绑定、RDF/OWL 导入导出、图查询和可视化设计思路。其当前实现主要面向语义建模和交互学习，本项目额外补充 Action、事务、治理、证据、可信度和版本演进。

来源：<https://github.com/microsoft/Ontology-Playground>

### 14.5 开放语义标准

- RDF/OWL：交换、语义关系和推理投影。
- SHACL：图数据与图结构约束。
- JSON Schema：Ontology Package 的结构验证。
- OpenAPI：API 证据采集与运行契约投影。

## 15. 明确不在 MVP 范围内

- 可部署的 Ontology Runtime。
- 自动代码生成器或 CLI。
- 数据库、代码和日志采集器。
- 自动推理服务或 LLM Agent。
- Web 设计器与 Microsoft 风格图形界面。
- 与 Palantir Foundry 或 Microsoft Fabric 的在线连接器。

这些能力由本规范定义接口和约束，但留给后续可运行版本实现。

## 16. MVP 验收标准

MVP 完成时必须满足：

- 所有第 13 节文档与机器可读产物齐全。
- 至少一个跨行业中立示例完整覆盖四层模型。
- 至少一个逆向发现示例包含 A–D 置信度、自证、反证与审核结果。
- 至少一个错误 Ontology 的演进示例覆盖拆分或合并、撤销、迁移和 lineage。
- JSON Schema、SHACL 与示例之间无未解释冲突。
- 文档术语、Package 字段和映射表保持一致。
- 不包含未决内容标记；所有规范性要求可由检查表或机器规则验证。
