# 可执行业务 Ontology 总体架构

本文规定可执行业务 Ontology 的架构边界。规范性要求以 [Ontology Package JSON Schema](../spec/v1/ontology-package.schema.json) 为机器权威；本文解释其架构意图，不替代 Schema。

分级验证、阻断条件与报告格式见 [Conformance Profile](conformance.md)；产品概念和开放标准的有损映射见 [Interoperability Mapping](interoperability.md)。

L0–L3 是组合验收模型。`validate_package` 保持 **component-level** checks；`python -m scripts.validate_release examples/service-operations` 是统一 **L0-L3-static** 发布入口，组合 Package、SHACL、文档、behavior、binding、evidence、traceability 与投影摘要规则。它不执行 runtime、不连接 live 外部系统，也不替代人工发布审阅或版本间 evolution 验收。

## 1. 目标、适用范围与非目标

目标是用一个可审计、可版本化的 **Ontology Package** 连接业务概念、行为契约、物理系统绑定和持续治理，使设计、正向投影、逆向发现及纠错共享同一语义基础。它适用于跨行业的静态规范、YAML/JSON Package、RDF/OWL 与 SHACL 投影、文档投影和运行投影契约。

当前 MVP 的交付物是文档、机器规范、验证规则和示例；它**不是**可部署的 Ontology Runtime，不承诺已实现执行引擎、代码生成器、连接器、自动推理服务或 Web UI。本文提到的运行组件均是未来实现必须遵守的契约边界，而非已交付能力。

### 规范性术语

- **MUST（必须）**：满足规范或发布门禁不可缺少的要求。
- **SHOULD（应该）**：通常必须遵循；偏离时必须记录理由与影响。
- **MAY（可以）**：可选能力，不影响基础符合性。

## 2. 四层架构

### 2.1 Semantics（语义层）

**职责。** 定义业务世界中稳定的类型结构：`ObjectType`、`PropertyType`、`LinkType`、`InterfaceType`、`ValueType`、`Invariant` 与 `BusinessTerm`。对象类型描述概念及其身份规则，不是对象实例；关系描述业务语义，不等同于数据库外键。

**输入。** 能力问题、领域定义、经审阅的证据与稳定 ID。**输出。** 对象、属性、关系、接口、词汇与不变量的权威定义。**依赖。** 只依赖 Package 的身份与治理上下文，不得依赖某个数据库表来决定业务含义。

**错误边界。** 键引用不存在、关系端点悬空、值类型不合法或不变量自相矛盾属于语义失败；这些错误 MUST 在进入行为验证前阻断。名称 MAY 改变，但稳定 `id` MUST 保持可追踪。

### 2.2 Kinetics（行为层）

**职责。** 用 `ActionType`、`QueryType`、`StateMachine` 和 `DomainEventType` 描述读取、改变、转换与已发生的业务事实。动作包含 `parameters`、`preconditions`、`effects`、权限、审计、副作用和可选补偿引用；事件是事实而非命令。

**输入。** Semantics 的稳定 ID、能力场景和策略引用。**输出。** 行为契约、状态转换、查询和事件定义。**依赖。** 行为目标、结果及状态机目标 MUST 可解析到 Semantics；权限和审计引用依赖策略层。

**错误边界。** 前置条件冲突、非法状态转换、遗漏权限/审计契约、效果目标悬空或补偿不闭合属于行为失败。**接收动作 ≠ 成功**：接收请求只表示进入处理边界；结果至少应区分结构/验证失败、权限拒绝、业务冲突、部分副作用失败与成功提交。未来运行实现 MUST 产生可审计的最终结果，不得把 HTTP 接收或队列入站当作业务成功。

### 2.3 Binding & Runtime（绑定与运行层）

**职责。** 用 `DataBinding`、`ApiBinding`、`CodeBinding`、`EventBinding` 将抽象元素连接到表/流、OpenAPI operation、代码 symbol 与消息 channel；用 `IdentityResolution`、`SyncPolicy`、`ConsistencyPolicy` 说明身份、同步与一致性。

**输入。** Ontology 稳定引用、物理资源定位、字段映射及来源证据。**输出。** 有方向的 `inbound`、`outbound` 或 `bidirectional` 映射和未来运行投影契约。**依赖。** 每个绑定 MUST 依赖可复核的 `evidenceRefs`；目标引用 MUST 指向已定义元素。

**错误边界。** 来源不可达、身份键不匹配、映射不完整、方向不明、陈旧证据或一致性规则冲突属于绑定失败。MVP 只静态验证绑定描述，不声称已经连接外部系统；外部连通性留给未来 Operational 验收。

### 2.4 Governance & Evolution（治理与演进层）

**职责。** 管理 Owner、Steward、Reviewer、Consumer 的责任，授权/审计/质量/合规策略，证据与推断的审批，以及变更、兼容性、迁移、回滚和 lineage。

**输入。** 四层验证结果、证据、运行观察和变更提案。**输出。** 审批决定、不可变发布、迁移说明和可追溯演进记录。**依赖。** 正式结论依赖 Evidence 与 Approval；发布目标依赖组合的 L0–L3 门禁，不能由单个 CLI 成功替代。

**错误边界。** 证据不可复核、哈希漂移、缺少批准、破坏性变更无迁移/回滚或影响分析不完整，均 MUST 阻止发布。运行反馈只 MAY 创建 Proposal，不得直接改写已发布 Package。

版本边界、认识状态、纠正操作、迁移安全与可验证 v1→v2 示例见 [Evolution Governance](evolution-governance.md)。

四层依赖方向是 Semantics → Kinetics → Binding & Runtime，并由 Governance & Evolution 横切约束。治理可以否决发布，但不能绕过下层事实制造语义。

### Evidence discovery process

逆向发现沿 `采集 → Evidence Graph → deterministic inference → semantic-assisted matching → conflict retention → human adjudication → Baseline Ontology proposal` 运行。EvidenceObservation 与 DiscoveryClaim 的边界、每阶段输入/输出/门禁及失败策略见 [Reverse Engineering Discovery](reverse-engineering.md)，六维确定性评分与治理提升规则见 [DiscoveryClaim Confidence](discovery-confidence.md)。所有发现结果只是 candidate；高分不得绕过 Governance & Evolution。

## 3. Ontology Package 与开放标准

一个 Package MUST 由以下八个文件构成（manifest 加七个权威内容文档）：

| 文件 | 权威职责 |
|---|---|
| `manifest.yaml` | `ontologyId`、版本、命名空间、所有者、状态、文档清单和摘要 |
| `semantics.yaml` | 对象、属性、关系、接口、不变量与业务术语 |
| `kinetics.yaml` | 动作、查询、状态机与领域事件 |
| `bindings.yaml` | 数据、API、代码、事件绑定及身份/同步/一致性策略 |
| `policies.yaml` | 授权、审计、数据质量与合规策略 |
| `evidence.yaml` | 原始证据、发现声明与批准记录 |
| `migrations.yaml` | 版本变更、兼容性、迁移、回滚与 lineage |
| `traceability.yaml` | 元素到文档、运行实现或扩展点、证据与验证的机器可读追溯 |

八个 Package 文档构成不可变、自包含的发布单元；Package 内的 **symlink（符号链接）一律禁止并由 validator 拒绝**，避免验证时读取包目录之外的可变内容。

YAML 与其规范 JSON 表示语义等价。**JSON Schema** 是文件结构、字段形状和基本格式的权威验证器；**SHACL** 验证 RDF 图中的引用与图约束；**RDF/OWL** 是语义交换、关系与推理的互操作投影。三者职责互补：投影冲突时，以 Package、其 `specVersion` 及规范转换规则为准。

## 4. Single Source of Truth（单一事实源）与 Multi-projection（多投影）

Ontology Package 是 **Single Source of Truth / 单一事实源**。文档、RDF/OWL、SHACL 输入、JSON、OpenAPI、SDK 或运行配置都是 **Multi-projection / 多投影** 的产物，任何投影都不得反过来成为隐式权威源。

### 投影身份与摘要

每个文档投影和运行投影 MUST 携带同一组四元 metadata：

- `ontologyId`：业务 Ontology 身份；
- `ontologyVersion`：业务语义发布版本，仅允许严格 `X.Y.Z` core SemVer；
- `specVersion`：Package 格式与验证语义版本，可以使用完整 SemVer prerelease/build；
- `contentDigest`：该版本规范内容摘要。

**文档投影** SHOULD 包含概念词典、元素目录、行为目录、绑定表、权限/审计矩阵、证据状态和迁移说明。**运行投影** MAY 生成类型、SDK、API 合约、验证器、状态机契约、映射配置与 Contract Test 骨架；当前仓库只交付机器可校验的投影契约，不宣称这些运行产物已经实现。

### Extension Point

生成物 MUST 可重建且**禁止直接修改**。若需要定制，只能使用显式 **Extension Point（扩展点）**。Extension Point 是运行投影契约：当前 v1 用 `traceability.yaml` 的 `extensionPointRef` 机器编码并验证 `extension://` 定位符；尚无运行实现时 MUST 使用扩展点，而不得伪造 `runtimeRef`。

扩展点 MUST 有稳定定位符、声明宿主元素与版本、限定输入/输出及权限边界，并保留实现位置与测试的可追溯链接；它 MUST NOT 覆盖标准字段语义、放宽 Ontology 不变量或伪造 `contentDigest`。当前无法表达的定制 SHOULD 进入 Proposal，而不是藏在生成物补丁中。

## 5. Traceability（可追溯）矩阵

### 可追溯性矩阵

每个正式元素 MUST 建立以下五类链接；缺一项时不得声称端到端符合：

| 链接 | 从 → 到 | 最低证据 |
|---|---|---|
| 定义链接 | 元素 → Package 稳定 ID/文件位置 | `id` 与定位 |
| 文档链接 | 元素 → 解释章节 | 文档锚点或目录条目 |
| 实现链接 | 元素 → 运行组件或 Extension Point | 无 runtime 实现时不得填 `runtimeRef`，必须用 `extensionPointRef` 表达预留扩展点 |
| 证据链接 | 元素 → `EvidenceRecord` | `evidenceRefs`、来源 URI、哈希 |
| 验证链接 | 元素 → 规则与测试契约 | `verificationRefs`、场景结果 |

矩阵 MUST 保持双向可查询：既能从元素找到证据和验证，也能从失败规则定位元素、文件位置与修复动作。LLM 输出 MAY 辅助匹配，但不能自身充当 Evidence。

`traceability.yaml` 现为 Package 的**第八个文档**。每个 accepted 语义/行为元素 MUST 有且仅有一条 `TraceabilityRecord`：`elementRef` 与 `evidenceRefs` 解析为内部稳定 ID，`documentationRef` 定位项目 Markdown 与显式锚点，`runtimeRef` 或 `extensionPointRef` 至少一个，`verificationRefs` 使用 `test://` 或 `scenario://`。Schema 与 Package validator 对这些字段、引用和精确覆盖执行**机器校验**。

Schema 根部的版本化 `x-traceability-profile` 是哪些 collection 进入精确追溯覆盖的**唯一事实源**。测试与 validator MUST 从该 profile 派生元素集合，并验证每个 collection 的 item `$ref` 指向带稳定 `id` 的定义；不得在代码或测试中维护第二份路径清单。

这里的 MUST 是**目标一致性契约**，也是当前发布门禁：文档、实现/扩展点、证据或验证任一链接缺失，均不得声称端到端符合。Parameter 属于动作/事件载荷细节，Effect 在 v1 无稳定 ID，二者不在 v1 精确覆盖集；该边界不得用来跳过所属 ActionType 或 DomainEventType 的追溯。

## 6. 发布生命周期

发布生命周期为：

`author → validate L0–L3 → proposal/review → release → observe`

1. **author**：在分支中编辑 Package，分配稳定 ID 并附证据。
2. **validate L0–L3**：这是组合验收阶段；L0 Syntactic 检查 JSON Schema 与 Package digest；L1 Semantic 组合引用、键、基数与 SHACL；L2 Behavioral 组合动作、转换、权限与静态可达性检查；L3-static 组合绑定、证据、traceability、投影摘要和文档检查。统一命令 `python -m scripts.validate_release examples/service-operations` 汇总这些静态机器规则；它不连接 live system、不证明 runtime 执行，适用的版本间 evolution 仍独立验收。
3. **proposal/review**：Proposal MUST 含语义差异和影响分析；Reviewer 对证据、兼容性与迁移作决定。
4. **release**：通过门禁后产生不可变版本及 `contentDigest`；已发布内容不得原地修改。
5. **observe**：收集漂移、约束失败、动作结果和新证据。观察 MAY 触发新 Proposal，不能自动发布。

元素认识状态是 `hypothesis → proposed → accepted → deprecated`，`accepted` 也可在证伪后转为 `retracted`。`ontologyVersion` 遵循 core SemVer：不改变语义的元数据修正为 Patch，向后兼容扩展为 Minor，删除、拆分、合并、基数或行为语义变化为 Major；同版本不得声明 evolution。

## 7. Conceptual ontology 与 operational ontology

| 维度 | Conceptual ontology（概念 Ontology） | Operational ontology（操作 Ontology） |
|---|---|---|
| 核心问题 | “业务世界是什么、概念如何关联？” | “系统允许读写什么、如何执行与审计？” |
| 主要内容 | 术语、对象、属性、关系、不变量 | 动作、查询、状态、策略、绑定、结果语义 |
| 物理依赖 | 应独立于单一系统实现 | 明确映射到 API、数据、代码、事件 |
| 验证重点 | 一致含义、身份、基数、图约束 | 权限、前置条件、效果、事务/补偿和绑定 |
| 变更风险 | 概念误解与语义漂移 | 副作用、兼容性、数据迁移与运行失败 |

二者不是两份事实源。Semantics 提供 conceptual ontology 的稳定核心；Kinetics、Binding 与 Policy 把它提升为 operational ontology。操作层 MUST 引用概念层稳定 ID，不得以 endpoint、表或 foreign key 偷换业务概念。

## 8. 错误分类、不变量与结果语义

| 类别 | 例子 | 处理边界 |
|---|---|---|
| 结构错误 | Schema 不满足、ID/摘要格式错误 | 阻止 L1 |
| 语义错误 | 悬空引用、键/类型/基数或 SHACL 冲突 | 阻止 L2 |
| 行为错误 | 前置条件、状态转换、权限或补偿矛盾 | 阻止 L3 |
| 绑定错误 | 来源不存在、键不匹配、映射缺失 | 阻止发布 |
| 证据错误 | 来源不可复核、哈希改变、范围不足 | 候选降级或退回 |
| 演进错误 | 缺少迁移、回滚或影响分析 | Proposal 不得合并 |

跨层不变量如下：所有正式元素 MUST 有合法稳定 ID；所有内部引用 MUST 可解析；外部引用 MUST 显式标识；运行约束不得弱于 Ontology 约束；正式发现结论 MUST 有证据与批准；发布版本及其摘要 MUST 不可变；破坏性变更 MUST 保留 migration、rollback 和 lineage；验证报告 MUST 指向元素 ID、文件位置、规则 ID 与可操作修复。

动作结果 MUST 区分“已接收”“验证失败”“权限拒绝”“业务冲突”“副作用部分失败”“已成功提交”。只有满足前置条件、权限、预期效果与事务/补偿契约后，才可报告业务成功。
