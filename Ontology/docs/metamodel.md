# Ontology Package 元模型参考

本文是四层元模型的字段级参考。机器结构以 [Ontology Package JSON Schema](../spec/v1/ontology-package.schema.json) 为准；可运行字段示例取自 [service-operations kinetics](../examples/service-operations/kinetics.yaml)，其他完整示例见 [service-operations 目录](../examples/service-operations/)。JSON Schema 负责结构验证，SHACL 负责 RDF 图约束，RDF/OWL 是交换与推理投影；投影不得改写 Package 语义。

## 1. 规范约定与通用语义

### 规范性术语

- **MUST（必须）**：符合 Schema 或发布门禁不可缺少。
- **SHOULD（应该）**：默认遵循；偏离必须有审计理由。
- **MAY（可以）**：可选表达。

顶级 `oneOf` 类别共八种：`manifest`、`semantics`、`kinetics`、`bindings`、`policies`、`evidence`、`migrations`、`traceability`，分别对应八个 Package 文件。

Schema 根部版本化扩展键 `x-traceability-profile` 是追溯覆盖 collection、对应 definition 与嵌套路径的**唯一事实源**。validator 与覆盖测试从它派生 accepted 元素；profile 缺失、路径不存在、item `$ref` 不匹配或目标定义没有稳定 `id` 都是配置错误。

稳定 `id` MUST 匹配 `^[A-Za-z][A-Za-z0-9._:-]*$`，在其命名空间内唯一，并在重命名时保持不变。`reference` 可以是内部稳定 ID，也可以是带协议 URI 或 `external:` 前缀的外部引用；内部引用 MUST 在 Package 中解析，外部引用 MUST 保留来源与解析责任，不能假装已受本 Package 完整验证。

通用生命周期 `status` 为 `hypothesis`、`proposed`、`accepted`、`deprecated`、`retracted`。未写 `status` 不代表自动接受；治理流程必须另行判断。开放字段只存在于 Schema 明确允许的位置，例如 `PropertyType.default` 可容纳任意 JSON 值；绝大多数对象 `additionalProperties: false`，不得借未知字段扩展。需要扩展时 SHOULD 使用架构定义的 Extension Point 和 Proposal。

以下条目统一给出 **Purpose（用途）**、**Required Fields（必填字段）**、**Invariants（不变量）**、**Depends On（依赖）**。

### Schema Helper Definitions

这些 helper definition 由其他定义复用，不各自代表 Package 文档。表中 marker 用于让文档覆盖检查与 Schema `$defs` 精确同步。

| Definition | Purpose | Constraint |
|---|---|---|
| `stableId` <!-- schema-def: stableId --> | 元素与内部引用的稳定标识 | 字母开头，只允许字母、数字、点、下划线、冒号、连字符 |
| `internalStableId` <!-- schema-def: internalStableId --> | 非 URI 的内部稳定标识 | v1 allowlist：允许无冒号 stable token，或唯一注册的 `domain:<local-token>`；其他冒号前缀一律拒绝 |
| `reference` <!-- schema-def: reference --> | 内部 ID 或明确外部引用 | 必须满足 `stableId`，或是带协议 URI/`external:` 值 |
| `label` <!-- schema-def: label --> | 人类可读名称 | 非空字符串 |
| `descriptions` <!-- schema-def: descriptions --> | 按语言标签保存描述 | 至少一项；语言键合法且值非空 |
| `lifecycle` <!-- schema-def: lifecycle --> | 元素认识状态 | 仅 `hypothesis|proposed|accepted|deprecated|retracted` |
| `idRefs` <!-- schema-def: idRefs --> | 可为空的引用数组 | 元素唯一且每项满足 `reference` |
| `nonEmptyIdRefs` <!-- schema-def: nonEmptyIdRefs --> | 非空引用数组 | 至少一项、元素唯一且每项满足 `reference` |
| `stableIdList` <!-- schema-def: stableIdList --> | 非空内部 ID 数组 | 至少一项、元素唯一且每项满足 `stableId` |
| `stringList` <!-- schema-def: stringList --> | 字符串数组 | 每项为非空字符串 |
| `semver` <!-- schema-def: semver --> | Package 与规范版本 | 满足语义化版本格式 |
| `coreSemver` <!-- schema-def: coreSemver --> | Ontology 发布版本 | 仅严格 `X.Y.Z`，禁止 prerelease 与 build metadata |

### 内部与外部引用

Schema 中只有直接使用 `reference`、`idRefs` 或 `nonEmptyIdRefs` 的属性允许外部 URI/`external:` 引用。允许外部 URI 的实际字段类别完整如下：

`property.evidenceRefs`、`objectType.evidenceRefs`、`linkType.evidenceRefs`、`interface.evidenceRefs`、`interface.propertyRefs`、`interface.actionRefs`、`rule.evidenceRefs`、`businessTerm.evidenceRefs`、`action.evidenceRefs`、`action.permissionRefs`、`action.auditRefs`、`action.sideEffectRefs`、`action.compensationRefs`、`query.evidenceRefs`、`stateMachine.evidenceRefs`、`domainEvent.evidenceRefs`、`dataBinding.evidenceRefs`、`apiBinding.evidenceRefs`、`codeBinding.evidenceRefs`、`eventBinding.evidenceRefs`、`operationalPolicy.targetRefs`、`operationalPolicy.evidenceRefs`、`policy.evidenceRefs`、`policy.targetRefs`、`approval.scopeRefs`、`approval.evidenceRefs`。

**仅内部稳定 ID** 字段如下。它们只使用 `stableId`、`stableIdList` 或等价的 stable-ID 数组，**必须是内部稳定 ID**，不得填写外部 URI：`valueType.targetRef`、`linkType.sourceRef`、`linkType.targetRef`、`effect.targetRef`、`query.resultRef`、`transition.fromRef`、`transition.toRef`、`transition.actionRef`、`stateTransitionContract.subjectRef`、`stateTransitionContract.fromStateRef`、`stateTransitionContract.toStateRef`、`stateMachine.targetRef`、`stateMachine.subjectRef`、`stateMachine.initialStateRef`、`domainEvent.subjectRef`、`dataBinding.targetRef`、`apiBinding.targetRef`、`codeBinding.targetRef`、`eventBinding.targetRef`、`discoveryClaim.evidenceRefs`、`discoveryClaim.counterEvidenceRefs`、`confidenceRationaleItem.evidenceRefs`、`approval.approvedElementRefs`、`change.predecessorRefs`、`change.successorRefs`、`change.evidenceRefs`、`lineageEntry.predecessorRefs`、`lineageEntry.successorRefs`、`traceabilityRecord.elementRef`、`traceabilityRecord.evidenceRefs`。字段名带 `Ref` 或 `Refs` 本身不代表允许外部引用，必须以其 Schema 类型为准。

## 2. Manifest 与 Package 身份

### Manifest

<!-- schema-def: manifest -->

- **Purpose：** 标识整个 Package 及其文档集合。
- **Required Fields：** `ontologyId`、`ontologyVersion`、`specVersion`、`namespace`、`status`、`owners`、`documents`、`contentDigest`。
- **Invariants：** `ontologyId` 是反向域风格小写标识；`ontologyVersion` 使用 coreSemver，`specVersion` 可使用完整 SemVer；`documents` 精确列出七个非 manifest YAML 文件；`contentDigest` 为 `sha256:` 加 64 位小写十六进制。
- **Depends On：** 八文件发布单元及对应 `specVersion`；示例见 [manifest.yaml](../examples/service-operations/manifest.yaml)。

## 3. Semantics

`semantics` 必须包含 `objectTypes`、`links`、`interfaces`、`invariants`、`businessTerms`，即使某个数组为空。

### Semantics Document

<!-- schema-def: semantics -->

- **Purpose：** 定义 `semantics.yaml` 顶级文档及其五类语义集合。
- **Required Fields：** `objectTypes`、`links`、`interfaces`、`invariants`、`businessTerms`。
- **Invariants：** `additionalProperties` 为 false；五个数组都必须出现，但可按 Schema 为空。
- **Depends On：** ObjectType、LinkType、InterfaceType、Invariant 与 BusinessTerm。

### ValueType

<!-- schema-def: valueType -->

- **Purpose：** 为 PropertyType、Parameter 与 DomainEventType payload 定义值域。
- **Required Fields：** 按 `kind` 分支：`primitive` 需 `primitive`；`enum` 需唯一非空 `values`；`struct` 需非空 `fields`（每项 `id`、`valueType`）；`reference` 需 `targetRef`；`temporal` 需 `base`；`spatial` 需 `geometry`；`measured` 需 `numericType` 与 `unit`。
- **Invariants：** 七种 kind 为 `primitive`、`enum`、`struct`、`reference`、`temporal`、`spatial`、`measured`，各分支不得混用字段。primitive 值域是 `string|integer|number|boolean|date|dateTime|uri`；temporal 的 `base` 是 `date|dateTime`；measured 数值仅 `integer|number`。
- **Depends On：** reference 的 `targetRef` 依赖稳定目标 ID；struct 可递归依赖 ValueType。

### ObjectType

<!-- schema-def: objectType -->

- **Purpose：** 定义业务概念、身份键和 PropertyType 集合。
- **Required Fields：** `id`、`label`、非空 `key`、非空 `properties`；可选字段为 `descriptions`、`status`、`evidenceRefs`。
- **Invariants：** `key` 是唯一、非空的稳定 ID 列表，其中每个 ID MUST 指向该对象的属性。ObjectType 是实例集合的类型定义，**不是 instance（实例）**，Package 也不存业务实例。
- **Depends On：** PropertyType；可选 `evidenceRefs` 依赖 EvidenceRecord。

### PropertyType

<!-- schema-def: property -->

- **Purpose：** 定义对象属性的标签、值域、必需性与默认值；Schema 定义名为 `property`。
- **Required Fields：** `id`、`label`、`valueType`；可选 `descriptions`、`status`、`evidenceRefs`、布尔 `required` 与开放值 `default`。
- **Invariants：** 属性 ID SHOULD 使用 `Object.property` 稳定形式；`required` 缺省不等于 `true`，`default` 必须符合所声明 ValueType 的业务含义。
- **Depends On：** ValueType、所属 ObjectType 及可选 EvidenceRecord。

### LinkType

<!-- schema-def: linkType -->

- **Purpose：** 定义两个 ObjectType 之间有方向、有业务含义和基数的关系。
- **Required Fields：** `id`、`label`、`sourceRef`、`targetRef`、`cardinality`。
- **Invariants：** 两端 MUST 解析到 ObjectType；基数仅 `one-to-one|one-to-many|many-to-one|many-to-many`。LinkType **不是 foreign key（外键）**：外键只能作为 DataBinding/Evidence 支持该关系，不能单独证明业务语义。
- **Depends On：** 源/目标 ObjectType 及可选 EvidenceRecord。

### InterfaceType

<!-- schema-def: interface -->

- **Purpose：** 以 `propertyRefs` 和 `actionRefs` 汇集跨对象共享的结构或能力契约。
- **Required Fields：** `id`、`label`。
- **Invariants：** 所有引用 MUST 可解析；接口不创建实例，也不复制被引用元素。
- **Depends On：** PropertyType、ActionType 与 EvidenceRecord。

### Invariant

<!-- schema-def: rule -->

- **Purpose：** 表达必须持续成立的跨属性或跨对象业务规则；Schema 定义名为 `rule`，在 `invariants` 数组中使用。
- **Required Fields：** `id`、`label`、非空 `expression`。
- **Invariants：** 表达式必须可审阅并引用稳定语义；未来执行器不得弱化它。
- **Depends On：** expression 涉及的对象、属性与关系；图约束可投影到 SHACL。

### BusinessTerm

<!-- schema-def: businessTerm -->

- **Purpose：** 保存业务词汇、正式定义及同义词。
- **Required Fields：** `id`、`label`、`definition`。
- **Invariants：** 同义词不创建新稳定身份；术语冲突 SHOULD 经治理解决。
- **Depends On：** 可选 `evidenceRefs`；通常链接到相关语义元素。

## 4. Kinetics

`kinetics` 必须包含 `actions`、`queries`、`stateMachines`、`domainEvents`。

### Kinetics Document

<!-- schema-def: kinetics -->

- **Purpose：** 定义 `kinetics.yaml` 顶级行为文档。
- **Required Fields：** `actions`、`queries`、`stateMachines`、`domainEvents`。
- **Invariants：** `additionalProperties` 为 false；四个数组必须出现，每项符合对应定义。
- **Depends On：** ActionType、QueryType、StateMachine 与 DomainEventType。

### Parameter

<!-- schema-def: parameter -->

- **Purpose：** 描述 ActionType/QueryType 输入及 DomainEventType payload 字段。
- **Required Fields：** `id`、`label`、`valueType`；可选布尔 `required`。
- **Invariants：** `required` 缺省不等于 `true`；`id` 为稳定 ID，值必须符合 ValueType。
- **Depends On：** ValueType，以及所属 ActionType、QueryType 或 DomainEventType。

### Effect

<!-- schema-def: effect -->

- **Purpose：** 描述 ActionType 要产生的对象变化、状态转换或事件发射。
- **Required Fields：** `targetRef`、`operation`、`expression`。
- **Invariants：** `operation` 仅为 `create|update|delete|emit|transition`；`targetRef` MUST 是可解析的内部稳定 ID，`expression` 非空。
- **Depends On：** ObjectType、PropertyType 或 DomainEventType 目标及所属 ActionType。

### ActionType

<!-- schema-def: action -->

- **Purpose：** 定义可请求的业务改变及其条件、效果、权限、审计、副作用和补偿引用；Schema 定义名为 `action`。
- **Required Fields：** `id`、`label`、`parameters`、`preconditions`、至少一个 `effects` 与闭合数组 `stateTransitions`；L2 发布规则还要求非空 `permissionRefs` 与 `auditRefs`。
- **Invariants：** 每个效果目标可解析；`permissionRefs` 只能指 AuthorizationPolicy，`auditRefs` 只能指 AuditPolicy，`compensationRefs` 只能指 ActionType。`sideEffectRefs` 非空时 `compensationRefs` 也必须非空。状态闭合只由结构化 `stateTransitions` 判断，不解析或搜索自然语言 expression。ActionType **不是 endpoint（端点）**：一个 endpoint 只是 ApiBinding，传输成功也不等于业务动作成功。
- **Depends On：** Parameter、Effect、Policy、DomainEventType；补偿动作通过 `compensationRefs` 引用其他稳定 ID。

### State Transition Contract

<!-- schema-def: stateTransitionContract -->

- **Purpose：** 以确定性 tuple 声明 Action 对某个 StateMachine subject 的状态迁移承诺。
- **Required Fields：** `subjectRef`、`fromStateRef`、`toStateRef`；对象闭合，不允许额外字段。
- **Invariants：** `subjectRef` MUST 指向 ObjectType 及其 StateMachine；两个状态引用 MUST 属于该 subject 的状态集合。每个 StateMachine Transition 必须在其 Action 中存在完全相等的 tuple；Action 可以声明额外 tuple，但引用仍须合法。
- **Depends On：** ObjectType、StateMachine 与 State。

### QueryType

<!-- schema-def: query -->

- **Purpose：** 定义只读选择或计算契约；Schema 定义名为 `query`。
- **Required Fields：** `id`、`label`、`parameters`、`resultRef`、`expression`。
- **Invariants：** `resultRef` MUST 指向稳定结果类型；Query 不应产生 Effect。
- **Depends On：** Parameter、ObjectType/ValueType 语义和可选 EvidenceRecord。

### StateMachine

<!-- schema-def: stateMachine -->

- **Purpose：** 定义 ObjectType 的状态集合和由动作触发的转换。
- **Required Fields：** `id`、`label`、`targetRef`、`subjectRef`、`initialStateRef`、`states`、`transitions`；其中 `states` 非空，`transitions` 必填但可为空；可选 `evidenceRefs`。
- **Invariants：** `targetRef`、`subjectRef` 和 `initialStateRef` MUST 可解析；`subjectRef` 指向 ObjectType，状态 ID 在该状态机内唯一。每个 Transition 必须与其 Action 的 `stateTransitions` 中一个 exact tuple 完全一致。
- **Depends On：** ObjectType、ActionType、State 与 EvidenceRecord。

### State

<!-- schema-def: state -->

- **Purpose：** 表示 StateMachine 中一个可引用的状态节点。
- **Required Fields：** `id`、`label`；可选 `terminal`，其值必须是 boolean。
- **Invariants：** `id` 必须是稳定 ID，并在所属 StateMachine 内唯一；`terminal: true` 表示终态，终态 SHOULD 不再作为 Transition 的 `fromRef`。
- **Depends On：** 所属 StateMachine；Transition 通过 `fromRef`、`toRef` 引用它。

### Transition

<!-- schema-def: transition -->

- **Purpose：** 描述由 ActionType 触发、从一个 State 到另一个 State 的转换。
- **Required Fields：** `id`、`fromRef`、`toRef`、`actionRef`；可选 `guard` 字符串。
- **Invariants：** `id` 为稳定 ID；`fromRef` 和 `toRef` MUST 解析到所属 StateMachine 的 State，`actionRef` MUST 解析到 ActionType；Action 必须用结构化 State Transition Contract 静态闭合 `subjectRef/fromRef/toRef` exact tuple，可选 `guard` 不得弱于 Action preconditions。
- **Depends On：** StateMachine、源/目标 State 和 ActionType。

### DomainEventType

<!-- schema-def: domainEvent -->

- **Purpose：** 表达已经发生、可审计的业务事实及其 subject 和 payload；Schema 定义名为 `domainEvent`。
- **Required Fields：** `id`、`label`、`subjectRef`、`payload`。
- **Invariants：** DomainEventType **不是 command（命令）**；它不得以将来式要求执行。`payload` 是 Parameter 数组，Schema 允许为空并只允许 Parameter 字段；若业务需要开放 payload，必须通过显式 ValueType（如 struct）建模，不能塞入未声明键。
- **Depends On：** subject ObjectType、Parameter、ValueType 和 EvidenceRecord。

### Compensation 与 Transaction

- **Purpose：** Compensation 通过 ActionType 的 `compensationRefs` 指出副作用失败后的恢复动作；Transaction（事务边界）规定哪些 Effects 必须原子提交以及幂等/一致性预期。
- **Required Fields：** 当前 v1 Schema 仅机器表达 `compensationRefs`；**没有独立 `transactions` 顶级字段**。事务意图当前必须由 Action effects、ConsistencyPolicy 和可审计文档共同约束，不能发明 YAML 字段。
- **Invariants：** 接收动作不等于成功；成功必须在权限、前置条件、效果与一致性边界完成后报告。部分副作用失败 MUST 可区分并关联补偿结果。
- **Depends On：** ActionType、Effect、ConsistencyPolicy 与 AuditPolicy。独立 TransactionBoundary 是未来 Schema 演进候选，当前不得宣称已实现。

### 来自当前示例的 YAML

以下片段逐字段摘自 [kinetics.yaml](../examples/service-operations/kinetics.yaml)，没有添加 Schema 外字段：

```yaml
actions:
  - id: submitServiceRequest
    label: Submit service request
    status: accepted
    evidenceRefs: [evidence.process]
    parameters:
      - id: submit.requestId
        label: Request identifier
        valueType: {kind: primitive, primitive: string}
        required: true
    preconditions: [ServiceRequest.status == 'draft']
    effects:
      - {targetRef: ServiceRequest, operation: transition, expression: "status = 'submitted'"}
      - {targetRef: event.serviceRequestSubmitted, operation: emit, expression: emit request snapshot}
    stateTransitions:
      - {subjectRef: ServiceRequest, fromStateRef: request.draft, toStateRef: request.submitted}
    permissionRefs: [policy.submitRequest]
    auditRefs: [policy.auditActions]
    sideEffectRefs: [event.serviceRequestSubmitted]
    compensationRefs: [withdrawServiceRequest]
```

## 5. Binding & Runtime

`bindings` 必须包含四种绑定以及 `identityResolution`、`syncPolicies`、`consistencyPolicies`。绑定只描述契约；MVP 不声称外部连接已经运行。

### Bindings Document

<!-- schema-def: bindings -->

- **Purpose：** 定义 `bindings.yaml` 顶级物理绑定与运行策略文档。
- **Required Fields：** `dataBindings`、`apiBindings`、`codeBindings`、`eventBindings`、`identityResolution`、`syncPolicies`、`consistencyPolicies`。
- **Invariants：** `additionalProperties` 为 false；七个数组必须出现，每项符合其 Binding 或 OperationalPolicy 定义。
- **Depends On：** 四种 Binding、OperationalPolicy 与 EvidenceRecord。

### DataBinding

<!-- schema-def: dataBinding -->

- **Purpose：** 映射表、视图或流到 Ontology 目标。
- **Required Fields：** `id`、`targetRef`、`direction`、非空 `evidenceRefs`、`source`、非空 `mappings`；`source` 内部必填 `system` 与 `resource`。
- **Invariants：** direction 仅 `inbound|outbound|bidirectional`；每条映射必须明确两端路径。
- **Depends On：** 目标语义元素、EvidenceRecord 与物理数据资源。

### ApiBinding

<!-- schema-def: apiBinding -->

- **Purpose：** 把 OpenAPI operation 映射到 ActionType 或 QueryType。
- **Required Fields：** `id`、`targetRef`、`direction`、非空 `evidenceRefs`、`operation`、非空 `mappings`；`operation` 内部必填 `specUri` 与 `operationId`。
- **Invariants：** `specUri` 是 URI；operationId 非空；endpoint 响应不替代 Action 结果语义。
- **Depends On：** ActionType/QueryType、API EvidenceRecord。

### CodeBinding

<!-- schema-def: codeBinding -->

- **Purpose：** 连接 Ontology 元素与模块、类型或函数 symbol。
- **Required Fields：** `id`、`targetRef`、`direction`、非空 `evidenceRefs`、`symbol`、非空 `mappings`；`symbol` 内部必填 `language` 与 `qualifiedName`。
- **Invariants：** qualifiedName 必须可定位；代码名称改变不得偷偷改变稳定 Ontology ID。
- **Depends On：** 目标元素、代码 EvidenceRecord。

### EventBinding

<!-- schema-def: eventBinding -->

- **Purpose：** 连接 DomainEventType 与消息 channel/schema 路径。
- **Required Fields：** `id`、`targetRef`、`direction`、非空 `evidenceRefs`、`channel`、非空 `mappings`；`channel` 内部必填 `protocol` 与 `name`。
- **Invariants：** channel 方向与 DomainEventType 事实方向一致；消息 payload 映射不得越过声明的证据边界。
- **Depends On：** DomainEventType、Event EvidenceRecord。

### Mapping

<!-- schema-def: mapping -->

- **Purpose：** 描述物理来源路径与 Ontology 路径之间的字段级对应及可选转换。
- **Required Fields：** 非空字符串 `ontologyPath`、非空字符串 `sourcePath`；可选 `transform` 字符串。
- **Invariants：** `additionalProperties` 为 false，不允许其他字段；两个必填路径不得为空，`transform` 若存在必须是字符串。Mapping 自身没有 `id`。
- **Depends On：** 所属 DataBinding、ApiBinding、CodeBinding 或 EventBinding，以及两端可解析的字段语义。

### OperationalPolicy

<!-- schema-def: operationalPolicy -->

- **Purpose：** 定义 Binding 层 `identityResolution`、`syncPolicies` 与 `consistencyPolicies` 共用的机器结构。
- **Required Fields：** `id`、`label`、非空 `targetRefs`、非空 `rule`；可选 `evidenceRefs`。
- **Invariants：** `additionalProperties` 为 false；公共字段由每个具体 OperationalPolicy 条目直接继承使用，不产生额外 YAML 包装层。
- **Depends On：** `targetRefs` 指向的 Ontology 元素或 Binding，以及可选 EvidenceRecord。

### IdentityResolution

- **Purpose：** 使用 Schema 的 `operationalPolicy` 形状规定业务键、外部 ID 与跨源实例的匹配规则。
- **Required Fields：** `id`、`label`、非空 `targetRefs`、非空 `rule`；可选 `evidenceRefs`。
- **Invariants：** `targetRefs` 必须可解析；规则不得仅凭名称相似合并实例。
- **Depends On：** ObjectType 的 `key`、DataBinding 与 EvidenceRecord。

### SyncPolicy

- **Purpose：** 使用 `operationalPolicy` 形状规定更新顺序、新鲜度、批流同步和冲突处理。
- **Required Fields：** `id`、`label`、非空 `targetRefs`、非空 `rule`；可选 `evidenceRefs`。
- **Invariants：** `targetRefs` 必须可解析；规则 MUST 说明顺序或数据新鲜度，不能静默覆盖冲突。
- **Depends On：** 一个或多个 Binding、IdentityResolution 与 EvidenceRecord。

### ConsistencyPolicy

- **Purpose：** 使用 `operationalPolicy` 形状规定读写一致性、幂等与状态更新边界。
- **Required Fields：** `id`、`label`、非空 `targetRefs`、非空 `rule`；可选 `evidenceRefs`。
- **Invariants：** `targetRefs` 必须可解析；规则不得弱化 Invariant 或 StateMachine 转换。
- **Depends On：** ActionType、StateMachine、Binding 与 EvidenceRecord。

## 6. Policies

`policies` 必须包含四类数组。四类共用 `policy` 形状，但治理含义不同。Policy **不是 validation（验证）本身**：Policy 声明业务/治理决定；JSON Schema、SHACL 或运行检查器才执行相应验证。

### Policies Document

<!-- schema-def: policies -->

- **Purpose：** 定义 `policies.yaml` 顶级治理策略文档。
- **Required Fields：** `authorizationPolicies`、`auditPolicies`、`qualityPolicies`、`compliancePolicies`。
- **Invariants：** `additionalProperties` 为 false；四个数组必须出现，每项符合 Policy。
- **Depends On：** Policy 及其目标 Ontology 元素。

### Policy

<!-- schema-def: policy -->

- **Purpose：** 定义 AuthorizationPolicy、AuditPolicy、QualityPolicy 与 CompliancePolicy 共用的机器结构。
- **Required Fields：** `id`、`label`、非空 `targetRefs`、非空 `rule`；可选 `descriptions`、`status`、`evidenceRefs`、`severity`。
- **Invariants：** `targetRefs` 至少一项；`severity` 若存在仅为 `info|warning|error`。公共字段由四类具体 Policy 条目直接继承使用，不产生额外 YAML 包装层。
- **Depends On：** 受管目标元素与可选 EvidenceRecord。

### AuthorizationPolicy

- **Purpose：** 规定什么主体在何种语境可读取或执行目标。
- **Required Fields：** `id`、`label`、非空 `targetRefs`、`rule`。
- **Invariants：** 目标可解析；拒绝必须可审计。
- **Depends On：** ActionType/QueryType 或受保护语义元素、EvidenceRecord。

### AuditPolicy

- **Purpose：** 规定记录 actor、时间、输入、决定和 outcome 的审计要求。
- **Required Fields：** 同 Policy 通用字段。
- **Invariants：** 规则应区分接收、拒绝、失败与成功；severity 可为 `info|warning|error`。
- **Depends On：** ActionType、DomainEventType 与审计证据。

### QualityPolicy

- **Purpose：** 规定标识、完整性、唯一性及数据质量要求。
- **Required Fields：** 同 Policy 通用字段。
- **Invariants：** 不得与 ObjectType key 或 Invariant 冲突。
- **Depends On：** ObjectType、PropertyType、DataBinding 和 EvidenceRecord。

### CompliancePolicy

- **Purpose：** 规定数据最小化、留存或行业合规边界。
- **Required Fields：** 同 Policy 通用字段。
- **Invariants：** 范围和严重度必须明确；合规规则不得被运行投影静默删除。
- **Depends On：** 受管元素、审批与来源证据。

## 7. Evidence 与治理边界

`evidence` 必须包含 `evidenceRecords`、`discoveryClaims`、`approvals`。**Evidence（证据）不是 inference（推断）**：EvidenceRecord 是可复核观察；DiscoveryClaim 是基于证据、可被证伪的判断。LLM 输出不能自身成为 EvidenceRecord。

### EvidenceObservation

<!-- schema-def: evidenceObservation -->

- **Purpose：** 在独立 Evidence Graph 中记录 database、OpenAPI、code、config 或 event log 的可复核 observation。
- **Required Fields：** `id`、`kind`、`sourceUri`、`location`、`capturedAt`、`contentHash`、`extractorVersion`、非空 `observedFacts`。
- **Invariants：** 对象闭合；哈希为 SHA-256；`observedFacts` 只能陈述直接观察，不能包含 inference。
- **Depends On：** 获准采集且可复核的外部来源。

### Evidence Graph

<!-- schema-def: evidenceGraph -->

- **Purpose：** 作为逆向发现的规范化 observation 图文档。
- **Required Fields：** `ontologyId`、`generatedAt`、非空 `observations`。
- **Invariants：** 对象闭合；每个 observation 使用稳定 ID，推断不得写入此文档。
- **Depends On：** EvidenceObservation；示例见 [Evidence Graph](../examples/discovery/evidence-graph.yaml)。

### Discovery Claims Document

<!-- schema-def: discoveryClaimsDocument -->

- **Purpose：** 独立交换一组由 Evidence Graph 支持的 DiscoveryClaim candidates。
- **Required Fields：** `ontologyId`、`generatedAt`、非空 `claims`。
- **Invariants：** 对象闭合；证据引用必须解析，score 与 grade 必须确定性重算一致。
- **Depends On：** DiscoveryClaim 与对应 Evidence Graph；示例见 [claims](../examples/discovery/claims.yaml)。

### Evidence Document

<!-- schema-def: evidence -->

- **Purpose：** 定义 `evidence.yaml` 顶级证据、推断与审批文档。
- **Required Fields：** `evidenceRecords`、`discoveryClaims`、`approvals`。
- **Invariants：** `additionalProperties` 为 false；三个数组必须出现，观察、推断和决定不得混为一类。
- **Depends On：** EvidenceRecord、DiscoveryClaim 与 Approval。

### EvidenceRecord

<!-- schema-def: evidenceRecord -->

- **Purpose：** 固定来源 URI、位置、采集时间、内容哈希、提取器版本及证据类型。
- **Required Fields：** `id`、`sourceUri`、`location`、`capturedAt`、`contentHash`、`extractorVersion`、`kind`。
- **Invariants：** hash 必须是 SHA-256；kind 仅 `document|database|api|code|event|interview|observation`；开放 payload 不得越过采集时声明的可见范围与证据边界。
- **Depends On：** 可复核的外部来源；示例见 [evidence.yaml](../examples/service-operations/evidence.yaml)。

### DiscoveryClaim

<!-- schema-def: discoveryClaim -->

- **Purpose：** 记录候选结论、推理规则、支持/反证、替代解释、六维置信度、证伪条件、问题与 provenance。
- **Required Fields：** `id`、`label`、`statement`、`status`、非空 `reasoningRules`、非空 `evidenceRefs`、`counterEvidenceRefs`、`counterEvidenceLevel`、`counterEvidenceAssessment`、非空 `alternatives`、`confidenceDimensions`、`confidenceRationale`、`confidence`、`grade`、非空 `falsifiers`、非空 `validationQuestions`、非空 `capabilityQuestions`、`provenance`。
- **Invariants：** 六维与 confidence 均为 0–100 严格整数，grade 为 A–D；`counterEvidenceLevel` 与反证维度严格映射为 none/100、minor/75、material/50、strong/25、coreContradiction/0；score 使用十进制 ROUND_HALF_UP；任何等级都不能跳过人工治理；反证不得被删除。
- **Depends On：** EvidenceRecord；被接受前依赖 Approval。

### ConfidenceRationale

<!-- schema-def: confidenceRationale -->

- **Purpose：** 为六个置信度维度提供 exact-key、机器可比的评分依据。
- **Required Fields：** `crossSourceAgreement`、`evidenceCoverage`、`runtimeSupport`、`semanticSpecificity`、`constraintConsistency`、`counterEvidenceAssessment`。
- **Invariants：** 对象闭合；六项的 score 必须与 `confidenceDimensions` 同名值一致。
- **Depends On：** 六个 ConfidenceRationaleItem。

### ConfidenceRationaleItem

<!-- schema-def: confidenceRationaleItem -->

- **Purpose：** 记录单一置信度维度的 score、解释、证据与扣分原因。
- **Required Fields：** `score`、`rationale`、`evidenceRefs`、`deductions`。
- **Invariants：** 对象闭合；score 是 0–100 整数；score 小于 100 时 deductions 必须非空；证据只能是内部稳定 ID。
- **Depends On：** Package 中的 EvidenceRecord 或 discovery bundle 中的 EvidenceObservation。

### Approval

<!-- schema-def: approval -->

- **Purpose：** 对一组 `scopeRefs` 记录批准、拒绝或要求修改的人工决定，并显式列出获批发布元素。
- **Required Fields：** `id`、非空 `scopeRefs`、非空 `approvedElementRefs`、`decision`、`approver`、`decidedAt`。
- **Invariants：** decision 仅 `approved|rejected|changes-requested`；`approvedElementRefs` 只能是内部稳定 ID。L3-static 要求所有 accepted trace-profile 元素被 decision=approved 的记录并集覆盖；proposed claim 不进入该集合。
- **Depends On：** 被审范围、Approver 身份及可选 EvidenceRecord。

### Adjudication Decision

<!-- schema-def: adjudicationDecision -->

- **Purpose：** 对一个不可变 DiscoveryClaim snapshot 记录人工治理决定。
- **Required Fields：** `claimRef`、`outcome`、`rationale`、`evidenceRefs`、`conditions`、`actions`；可选 `resultingElementRefs`。
- **Invariants：** outcome 仅 `accepted|needsRevision|rejected|deferred`；claimRef 必须精确覆盖 claims 文档中的一个 claim，evidenceRefs 只能引用 EvidenceObservation。决定不回写历史 claim。
- **Depends On：** DiscoveryClaim、EvidenceObservation 与 human reviewer。

### Adjudication Document

<!-- schema-def: adjudicationDocument -->

- **Purpose：** 保存指定 Ontology discovery run 的 reviewer 身份、时间与逐 claim 决定。
- **Required Fields：** `ontologyId`、`decidedAt`、闭合 reviewer（`name`、`role`）和非空 `decisions`。
- **Invariants：** ontologyId 必须与 claims 文档一致；每个 claim 恰有一个 decision，不允许 unknown 或 duplicate claimRef。accepted decision 只创建 baseline promotion proposal。
- **Depends On：** Discovery Claims Document 与 Adjudication Decision。

## 8. Governance & Evolution

`migrations` 必须包含 `version`、`changes`、`lineage`；空数组表示该版本无已声明变更，而非允许丢弃历史。

### Migrations Document

<!-- schema-def: migrations -->

- **Purpose：** 定义 `migrations.yaml` 顶级版本、变更与 lineage 文档。
- **Required Fields：** `version`、`changes`、`lineage`。
- **Invariants：** `additionalProperties` 为 false；`version` 符合三段 SemVer，两个数组必须出现。
- **Depends On：** Change、Lineage 与 Manifest 的 `ontologyVersion`。

### Change

<!-- schema-def: change -->

- **Purpose：** 描述 add/metadata 或带证据的纠错，并携带完整迁移安全记录。
- **Required Fields：** `id`、`operation`、`compatibility`、`predecessorRefs`、`successorRefs`、`originalDefinition`、`newDefinition`、`errorCause`、`evidenceRefs`、`impactAnalysis`、`migrationStrategy`、`backfill`、`rollback`、`compatibilityWindow`、`dualRead`、`dualWrite`、`acceptanceEvidence`。
- **Invariants：** operation 仅 `add|metadata|rename|retype|split|merge|relink|supersede|retract`；compatibility 仅 `patch|minor|major`；内部 evidence 引用、影响、回填、回滚和验收均显式。Change 是声明，不能替代独立且边一致的 Lineage，也不代表迁移工具已经实现。
- **Depends On：** 前后版本元素、EvidenceRecord 和发布审批。

### Alias Proof

<!-- schema-def: aliasProof -->

- **Purpose：** 证明纯 rename 未改变稳定身份和消费者标识，从而允许 minor 例外。
- **Required Fields：** `stableIdPreserved: true`、`consumerIdentifiersUnchanged: true`、非空内部 `evidenceRefs`。
- **Invariants：** 对象闭合；仅 rename 可使用兼容性降级。Validator 从 `x-traceability-profile` 路径抽取真实前后元素，要求 originalDefinition/newDefinition 与实际定义一致，并对真实递归 diff 仅允许 `label|name|descriptions|aliases` 及其子路径；开放 payload 内偶然出现的 `id` 不参与索引。retype/relink/split/merge/supersede/retract 仍为 major。
- **Depends On：** Change 与跨版本 EvidenceRecord。

### Impact Analysis

<!-- schema-def: impactAnalysis -->

- **Purpose：** 闭合记录 data、api、action、query、policy、document、audit、consumers 八类影响。
- **Required Fields：** 八个影响数组全部必须出现，允许空数组表示已分析但无影响。
- **Invariants：** 禁止未知影响类别；不得以缺字段表示“无影响”。
- **Depends On：** Change 与消费者清单。

### Read/Write Mode

<!-- schema-def: readWriteMode -->

- **Purpose：** 记录 dual-read 是否启用及理由。
- **Required Fields：** `enabled`、`description`。
- **Invariants：** description 非空。
- **Depends On：** migrationStrategy 与兼容窗口。

### Dual Write Mode

<!-- schema-def: dualWriteMode -->

- **Purpose：** 记录临时双写开关及其数据一致性安全契约。
- **Required Fields：** 始终要求 `enabled`、`description`；启用时还要求 `idempotencyKey`、`ordering`、`conflictAuthority`、非空 `stopConditions`。
- **Invariants：** 对象闭合；`enabled: true` 时 migrationStrategy 必须包含 `temporary-dual-write`。
- **Depends On：** Change、兼容窗口与回滚计划。

### Rollback Plan

<!-- schema-def: rollbackPlan -->

- **Purpose：** 把回滚从一句说明升级为可执行、可触发、可验收的安全计划。
- **Required Fields：** 非空 `procedure`、`triggerConditions`、`verificationSteps` 字符串数组。
- **Invariants：** 对象闭合；不得以空数组或自由文本替代运行步骤。
- **Depends On：** Change、Observation 与 Acceptance Evidence。

### Lineage

<!-- schema-def: lineageEntry -->

- **Purpose：** `lineageEntry` 连接 predecessor 与 successor，使旧数据、审计和文档持续可解释。
- **Required Fields：** `operation`、非空 `predecessorRefs`、`successorRefs`。
- **Invariants：** 两端为稳定内部 ID；retract 的 `successorRefs` 必须为空，其余 operation 必须非空；split 明示一对多，merge 明示多对一。每个纠正 Change 与 Lineage 必须双向一一匹配，额外 lineage 也拒绝；重复边、共享覆盖、自环或跨边有向环均拒绝。retract predecessor 必须继续存在于目标 Package 且 lifecycle 为 retracted，lineage-only retract 不能绕过 Change 的 cause/evidence/impact。
- **Depends On：** Change 和新旧 Package 版本。

### Migration

- **Purpose：** 表示 `migrations.yaml` 的顶级迁移文档，聚合目标版本、Change 数组与 Lineage 数组；Schema 定义名为 `migrations`。
- **Required Fields：** `version`、`changes`、`lineage`。
- **Invariants：** `version` MUST 是三段 SemVer 核心版本；`changes` 每项符合 Change，`lineage` 每项符合 `lineageEntry`；两个数组可以为空，但不得借空数组删除已有历史。
- **Depends On：** Manifest 的 `ontologyVersion`、Change、Lineage 与发布流程。

### Evolution Migration

<!-- schema-def: evolutionMigration -->

- **Purpose：** 以机器字段连接两个不可变 Package 发布。
- **Required Fields：** `fromVersion`、`toVersion`、非空 `changes`、非空 `lineage`。
- **Invariants：** from/to 为三段 SemVer 核心，版本升级必须与最大 change impact 精确一致。
- **Depends On：** 前后 Manifest、Change、Lineage 与 [演进治理](evolution-governance.md)。

### Traceability Document

<!-- schema-def: traceability -->

- **Purpose：** 定义 `traceability.yaml`，把 accepted 语义/行为元素连接到文档、运行实现或扩展点、证据和验证。
- **Required Fields：** `ontologyId`、`ontologyVersion`、`sourceDigest`、`records`。
- **Invariants：** 对象闭合；`ontologyId` 与 `ontologyVersion` MUST 分别匹配 Manifest；每个 `x-traceability-profile` 声明的 accepted 元素有且仅有一条记录，该 profile 是覆盖声明唯一事实源。`sourceDigest` 的计算排除自身字段但包含全部 records，且 MUST 等于 Manifest `contentDigest`。Parameter 是载荷细节，Effect 在 v1 无稳定 ID，二者不进入 v1 覆盖集。
- **Depends On：** Manifest、Semantics Document、Kinetics Document、Evidence Document 与项目文档锚点。

### TraceabilityRecord

<!-- schema-def: traceabilityRecord -->

- **Purpose：** 为一个稳定元素保存端到端追溯边。
- **Required Fields：** `elementRef`、`documentationRef`、非空 `evidenceRefs`、非空 `verificationRefs`；并且 `runtimeRef` 或 `extensionPointRef` 至少一个。
- **Invariants：** 对象闭合；`elementRef` 与 `evidenceRefs` 是内部稳定 ID；`documentationRef` 是项目根内 `.md#explicit-anchor` 且不得含路径逃逸；`runtimeRef` 使用 `runtime://`，`extensionPointRef` 使用 `extension://`，验证仅使用 `test://` 或 `scenario://`。没有已验证运行实现时 MUST 使用扩展点，不得虚报 runtime。
- **Depends On：** 被追溯的语义/行为元素、EvidenceRecord、文档章节及契约测试或验收场景。

### 发布与引用语义

- **Purpose：** 将认识生命周期与不可变发布结合。
- **Required Fields：** 元素状态使用通用 lifecycle；发布身份来自 Manifest 四元组。
- **Invariants：** `hypothesis → proposed → accepted → deprecated`，accepted 可转 `retracted`；已发布版本不得原地修改。内部引用在 L1 必须闭合；外部引用只能作为明确 URI/`external:` 引用，并在 L3 记录解析和证据责任。
- **Depends On：** L0 JSON Schema、L1 SHACL/引用检查、L2 行为检查、L3 绑定/证据/迁移检查及 Approval。

## 9. 投影边界总结

Package YAML/JSON 是权威模型。JSON Schema MUST 拒绝未知结构与错误字段；RDF/OWL MAY 表达类型、关系与互操作语义；SHACL MUST 用于图形状、引用与跨节点约束。RDF 推理结论仍属于 inference，除非有 EvidenceRecord 和 Approval，不得自动写回正式 Ontology。任何往返投影必须保留稳定 ID、类型、关系语义以及 `ontologyId`、`ontologyVersion`、`specVersion`、`contentDigest`。
