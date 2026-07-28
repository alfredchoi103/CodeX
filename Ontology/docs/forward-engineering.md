# 正向工程指南（Forward Engineering Guide）

本文定义如何从业务目标生成可验证的本体、物理绑定与系统投影。规范词 **MUST（必须）**、**SHOULD（应该）**、**MAY（可以）** 表示强制、建议与可选要求。发生错误时，产物 MUST 停在当前质量门，报告稳定 ID、源文件、规则、失败场景与修复建议；不得用降级约束掩盖错误。

系统边界 MUST 先声明包含的业务能力、参与者、数据所有权、外部系统、信任边界以及不在范围内的流程。边界外依赖只能通过 Binding 或 Extension Point 表达。

<a id="goals-competency-questions"></a>
## 1. 目标与能力问题（Goals & Competency Questions）

### Inputs / 输入

业务目标、法规、利益相关者、现状证据、系统边界与失败风险。

### Activities / 活动

把目标改写为可证伪的能力问题（Competency Questions），定义术语、成功指标、正常与失败边界，并识别权限及审计责任。

### Outputs / 输出

有负责人和证据来源的能力问题清单、范围声明、风险与验收口径。

### Quality Gate / 质量门

每个目标 MUST 至少映射一个能力问题；每个问题 MUST 可由查询、动作或场景验证。

### Rejection Conditions / 拒绝条件

目标不可衡量、边界含混、证据不可定位，或问题无法形成可重复判定时拒绝。

<a id="semantic-modeling"></a>
## 2. 语义建模（Semantic Modeling）

### Inputs / 输入

已通过质量门的能力问题、术语表和证据记录。

### Activities / 活动

定义 ObjectType、PropertyType、LinkType、InterfaceType、Invariant 与 BusinessTerm；分配 stable ID，明确值类型、键、基数与约束。Parameter 是动作/事件载荷细节，Effect 在 v1 没有稳定 ID，因此两者不进入 v1 TraceabilityRecord 覆盖集。

### Outputs / 输出

`semantics.yaml`、证据引用以及能力问题到语义元素的映射。

### Quality Gate / 质量门

accepted 元素 MUST 唯一、闭合、可引用；术语和约束 MUST 无矛盾，内部引用 MUST 可解析。

### Rejection Conditions / 拒绝条件

出现重复 ID、悬空引用、未定义值域、模糊术语或不可证伪约束时拒绝。

<a id="behavior-modeling"></a>
## 3. 行为建模（Behavior Modeling）

### Inputs / 输入

通过的语义模型、业务流程、权限责任、失败及补偿需求。

### Activities / 活动

定义 ActionType、QueryType、StateMachine、State、Transition 与 DomainEventType。动作 MUST 区分验证失败、权限拒绝、业务冲突、副作用失败与成功；补偿不能把失败伪装为成功。

### Outputs / 输出

`kinetics.yaml`，含前置条件、效果、权限、审计、副作用与补偿引用。

### Quality Gate / 质量门

状态迁移 MUST 可达且受 guard/action 约束；每个有副作用动作 MUST 有明确提交边界及错误结果。

### Rejection Conditions / 拒绝条件

状态不可达、权限缺失、错误语义混合、事件与命令混淆或补偿责任不明时拒绝。

<a id="physical-binding"></a>
## 4. 物理绑定（Physical Binding）

### Inputs / 输入

通过的语义/行为模型、数据目录、API 契约、代码符号与事件目录。

### Activities / 活动

建立 DataBinding、ApiBinding、CodeBinding、EventBinding 和 Mapping，声明身份解析、同步及一致性策略。每个 binding MUST 定位到可检查资源并携带证据，不得把外部名称当作本体 stable ID。

### Outputs / 输出

`bindings.yaml` 与可定位的源路径、操作、符号、通道和转换。

### Quality Gate / 质量门

映射方向、身份、单位、枚举与一致性语义 MUST 明确；读写路径 SHOULD 可自动验证。

### Rejection Conditions / 拒绝条件

资源不存在、映射有损却无声明、身份冲突或一致性窗口未定义时拒绝。

<a id="system-projection"></a>
## 5. 系统投影（System Projection）

### Inputs / 输入

通过的 Package、绑定、治理策略、部署边界和目标系统契约。

### Activities / 活动

生成 API projection、storage projection 与 policy projection。生成物不得直接修改；变化 MUST 回流权威 Package 后重生成。没有运行实现时 MUST 使用 `extensionPointRef: extension://...`；只有可定位且已验证的组件才可用 `runtimeRef: runtime://...`。Extension Point policy 要求扩展不得改变 stable ID、削弱不变量或绕过权限/审计，并在实现后替换为运行引用。

Schema 的版本化 `x-traceability-profile` 是追溯覆盖路径与 definition 映射的**唯一事实源**；生成器、validator 与测试 MUST 共同读取它，profile 配置错误必须阻断投影。八个 Package 文档 MUST 是普通文件，禁止 symlink，以保证发布单元自包含且验证不会读取包外内容。

### Outputs / 输出

系统投影、`traceability.yaml`、生成报告及摘要。TraceabilityRecord 用 `elementRef` 连接本体，用 `documentationRef` 连接本文锚点，用 `runtimeRef` 或 `extensionPointRef` 连接运行模型，用 `evidenceRefs` 连接证据，用 `verificationRefs` 连接测试/场景。

### Quality Gate / 质量门

投影 MUST 保持目标约束，并通过 schema、引用、摘要及追溯覆盖校验。

### Rejection Conditions / 拒绝条件

投影丢失约束、直接编辑生成物、伪报运行组件、摘要过期或追溯缺失/重复时拒绝。

<a id="scenario-acceptance"></a>
## 6. 场景验收（Scenario Acceptance）

### Inputs / 输入

能力问题、投影、运行约束、权限策略、审计策略与可复现测试夹具。

### Activities / 活动

至少执行 normal（正常成功）、denied（权限或前置条件拒绝）与 compensated（副作用失败后补偿）三类场景，并核对状态、事件、持久化、审计和错误码。

### Outputs / 输出

`test://` 契约结果、`scenario://` 验收结果、失败证据与发布建议。

### Quality Gate / 质量门

系统只有同时满足以下六项才可声明 “implements this ontology”：stable ID 全链路追溯；运行约束不弱于本体；权限与审计一致；binding 定位到真实资源；digest 一致；能力问题通过。

### Rejection Conditions / 拒绝条件

任一场景不可重复、拒绝路径发生副作用、补偿不完整、审计与决策不一致，或六项声明条件任一失败时拒绝。

## 摘要算法与错误处理

Package 有八个文档：manifest 加七个权威文档。`contentDigest` 按文件名排序，对七个非 manifest 文档的 JSON 规范形式计算 SHA-256；映射键排序、UTF-8、紧凑分隔符。为避免自引用，计算 `traceability.yaml` 时 MUST 仅移除顶层 `sourceDigest`，records 仍完整参与摘要；所得值同时写入 manifest `contentDigest` 与 traceability `sourceDigest`。任何 records 变更都会改变摘要，单独改写 sourceDigest 不改变计算值但会触发一致性错误。

相关定义见 [元模型](metamodel.md)，总体原则见 [架构](architecture.md)，机器约束见 [JSON Schema](../spec/v1/ontology-package.schema.json)。
