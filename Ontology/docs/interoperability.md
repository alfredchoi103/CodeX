# EBO Interoperability Mapping

本文给出 EBO 与外部产品概念及开放标准之间的方向性语义映射。它用于设计与交换评估，不是代码适配器、认证、商标许可或兼容性保证；EBO [Metamodel](metamodel.md) 和 [Package Schema](../spec/v1/ontology-package.schema.json) 仍是本项目权威源。

## 规范性术语

- **MUST（必须）**：符合映射边界不可缺少的要求。
- **SHOULD（应该）**：默认要求；偏离时必须记录理由与信息损失。
- **MAY（可以）**：受控的可选映射，不表示兼容承诺。

## 方法、方向与映射类型

映射方向默认为 `Source Concept → EBO Concept`。反向投影只有在行内明确说明且满足 round-trip 规则时成立。

- `direct`：核心含义与基数可表示；仍需转换标识符和序列化形状。
- `partial`：只保留共同语义，`Information Loss` 列必须说明遗漏。
- `extension`：核心模型没有等价物，需 EBO extension point 或产品专用投影。

“无”仅表示本表评估未发现语义损失；不表示二进制、API 或运行兼容。所有映射都必须记录源版本、方向与未映射字段，禁止用相似命名推定等价。

## Palantir Ontology API 概念

下表的实现信号依据公开 `foundry-platform-python` **official SDK** 文档/类型，属于 **direct implementation signal**；它证明公开客户端表面存在相应资源，不证明服务内部实现。Palantir 官方 API v2 Introduction 仅列作官方定位入口，**official website / 官网未直接核验**，不据此作具体能力断言。`Leading-AI-IO` 的 Palantir impact essay 是第三方 **secondary analysis / 二级材料**，只作解释性背景，不是 Palantir 官方来源或实现证据。本文不复制私有实现，也没有访问非公开代码或实例。

| Source Concept | EBO Concept | Mapping Type | Information Loss | Notes |
|---|---|---|---|---|
| Object Type | `ObjectType` | direct | 产品 RID/API name 与 EBO stable ID 需转换 | Source → EBO；定义层，不是实例 |
| Property | `PropertyType` + `ValueType` | direct | 产品专用格式/索引 hints 可能丢失 | key、nullable、value type 需显式映射 |
| Link Type | `LinkType` | direct | 产品导航/检索细节不进入核心 | 保留 source、target、direction、cardinality |
| Action / Action Type | `ActionType` | partial | 提交协议、执行状态与平台 side effects 不可从定义完整恢复 | 映射 parameters/preconditions/effects；运行适配另行实现 |
| Query / Query Type | `QueryType` | partial | 产品函数语言、分页和执行计划丢失 | 只保留输入、结果与意图契约 |
| Object Set | `QueryType` + extension point | extension | 集合代数、订阅与惰性执行不能进核心 | 使用产品投影扩展，不伪装成 ObjectType |
| Transaction | `ActionType` transaction/compensation contract | partial | 隔离级别、提交 token 与平台原子性不可移植 | EBO 只表达要求，不宣称执行 |
| Branch | Proposal / release workflow | partial | 产品分支能力与 EBO immutable release 不同 | Branch 是编辑隔离，不是 ontologyVersion |
| OntologyScenario | candidate/proposal sandbox extension | partial | 平台 what-if 编辑、base 与冲突检测语义不可完整移植 | 对应 edit-conflict context；不是 capability acceptance scenario，也不是验收证据 |
| ObjectType edits history | instance audit/edit evidence/history extension | partial | 对象实例增删改历史、分页与作者字段可能不同 | 这是 instance 层记录，不是 ontology schema `Change` + `Lineage` |
| permissions | `AuthorizationPolicy` | partial | 平台 principal、scope 与 enforcement runtime 不可移植 | 所审 Ontologies SDK 表面不足以证明完整权限模型；只映射策略意图，实际授权需 adapter/contract test |

这些映射是建模对照，**Palantir mapping 非兼容承诺**，也不暗示 Palantir 对本项目的认可。尤其 Action、Transaction、permissions 的静态对应不能证明在 Palantir 或任何平台上具有同等运行效果。

## Microsoft Ontology Playground 概念

以下判断来自公开仓库的 **Playground code**、测试与 README：模型类型、designer store、RDF parser/serializer 及 Cytoscape graph 组件是直接代码证据。Playground 是设计/学习工具信号；本表不把它外推为 Microsoft 产品 runtime，也不声称其支持 EBO Action、权限、审计或治理。

| Source Concept | EBO Concept | Mapping Type | Information Loss | Notes |
|---|---|---|---|---|
| Entity Type | `ObjectType` | direct | UI icon、color、layout 丢失 | Source → EBO；名称需分配 stable ID |
| Property | `PropertyType` + `ValueType` | direct | UI metadata 与部分 datatype facet 可能丢失 | typed property 可直接进入语义层 |
| Relationship | `LinkType` | direct | UI edge style/layout 丢失 | from/to/cardinality 可映射 |
| Data Binding | `DataBinding` | partial | 示例 lakehouse source 不能证明连接可达或同步语义 | 必须补 evidence、identity/sync/consistency policy |
| composite key | `ObjectType.keys` | extension | 所审 Playground 代码未建立原生 composite key 支持 | 这是目标交换用例而非当前能力声明；需 EBO Schema/extension metadata 保护 |
| time series | temporal `ValueType` + `DataBinding` | extension | 所审 Playground 代码未建立原生 time series 语义 | 这是目标交换用例而非当前能力声明；需显式 temporal/binding 约束 |
| RDF import | RDF projection → EBO candidate | partial | Kinetics、policy、evidence、binding、evolution 不在 RDF 中 | 导入结果必须治理审阅，不能直接 accepted |
| RDF export | EBO Semantics → RDF/OWL projection | partial | 行为与运行契约不完整 | Package 保持单一事实源 |
| graph visualization | non-authoritative documentation projection | extension | 布局、折叠、交互状态不应回写规范语义 | **Microsoft visualization deferred**；本 MVP 不实现该 UI |

Playground 的 RDF round-trip 是其代码范围内的序列化能力；不能据此推断完整 EBO Package round-trip。EBO → Playground 只投影共同的实体、属性、关系与部分基数，反向导入必须产生 candidate 和损失清单。

## Semantic standards

| Source Concept | EBO Concept | Mapping Type | Information Loss | Notes |
|---|---|---|---|---|
| RDF graph | Semantics 的对象/属性/关系投影 | partial | 文件边界、治理、证据、行为与运行 contract 丢失 | 可交换事实与图结构；不是 Package 权威源 |
| OWL class/property/axiom | `ObjectType`/`PropertyType`/`LinkType`/部分 `Invariant` | partial | closed-world、业务键及可执行行为不等价 | 推理结果必须保留 provenance |
| SHACL shape | L1 graph constraint / `Invariant` projection | partial | 不表达完整动作、权限、迁移和 runtime | [本地 SHACL](../spec/v1/ontology.shacl.ttl) 用于图约束 |
| JSON Schema | Package structural contract | direct | 图推理与运行行为不由 Schema 提供 | [本地 Schema](../spec/v1/ontology-package.schema.json) 是结构权威 |
| OpenAPI operation/schema | `ApiBinding` + `ActionType`/`QueryType` projection | partial | endpoint 不等同业务行为；状态、补偿、审计语义可能丢失 | 必须引用稳定 EBO targetRef |

**RDF/OWL 不能原生完整表达 Kinetics 或 runtime contract**；Action 状态语义、补偿、策略、证据、绑定、迁移和 traceability 必须留在 Package，交换时使用显式 **EBO extension**（带命名空间、版本和损失声明）。SHACL 能验证部分图约束，但不把开放世界 RDF 变成行为执行引擎。

## Round-trip 规则

1. 导出前固定 `ontologyId`、`ontologyVersion`、`specVersion` 与 `contentDigest`，记录 projection profile。
2. 每个元素保存 EBO stable ID；源系统只支持本地 ID 时建立显式双向 id map。
3. 每次转换输出 mapped、extended、dropped、defaulted 字段清单；`partial` 或 `extension` 不得标为 lossless。
4. 重新导入先形成 candidate Package；重算 digest，比较 stable-ID 级 semantic diff，并重新运行 [L0–L3-static](conformance.md)。
5. round-trip success 仅在共同子集语义等价、无未声明 loss 且 capability questions 仍通过时成立；序列化字节相同既非必要也非充分条件。

## Compatibility 与非目标

- 不承诺与 Palantir Foundry、Microsoft Fabric 或 Ontology Playground 的 API、文件、运行或版本兼容。
- 不复制、反向工程或推断任何私有实现；只使用列出的公开材料与本地 EBO 规范。
- 不把产品名相似性当作 semantic equivalence，不把 SDK 表面当作服务运行保证。
- 不声称 Microsoft Playground 支持 Action、policy、permissions、audit、evidence 或 evolution；graph UI 集成 deferred。
- 不声称 RDF/OWL、SHACL、JSON Schema 或 OpenAPI 任一标准可单独完整承载 EBO。

## 来源与访问边界

访问日期均为 2026-07-28；URL 用于可复核定位，本文没有实时请求这些网站。

| Source | URL | Version / Revision | Access type | How used |
|---|---|---|---|---|
| Palantir `foundry-platform-python` Ontologies v2 docs | https://github.com/palantir/foundry-platform-python | `168d51910570b6966afa2320333ab36f6a3f7ccf` | official SDK；本地 checkout；direct implementation signal | ObjectType、Property、Link、ActionType、QueryType、ObjectSet、Transaction、Branch、OntologyScenario 等公开客户端表面 |
| Palantir API v2 Introduction | https://www.palantir.com/docs/foundry/api/v2/general/overview/introduction/ | unversioned | official website；官网未直接核验 / not directly verified | 只列作官方 API 定位入口，不从未访问页面提取具体能力声明 |
| `Leading-AI-IO` Palantir impact essay | https://github.com/Leading-AI-IO/palantir-ontology-strategy/blob/main/docs/the-palantir-impact_en.md | `43865edee483234967a583016c9e259e7b8ba241` | secondary analysis / 二级材料；本地 checkout | 只提供解释性背景，不作为 Palantir 官方来源或实现能力证据 |
| Microsoft Ontology Playground | https://github.com/microsoft/Ontology-Playground | `683adcc8d5a449b9ca9c82e92aaf51c066025c25` | 公开 Playground code 与 README；本地 checkout；direct code evidence | Entity/Property/Relationship、cardinality、Data Binding、RDF parser/serializer、graph visualization |
| W3C RDF 1.1 Concepts | https://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/ | RDF 1.1 | public standard；固定 Recommendation URL | RDF 图交换边界 |
| W3C OWL 2 Overview | https://www.w3.org/TR/2012/REC-owl2-overview-20121211/ | OWL 2 | public standard；固定 Recommendation URL | OWL 类、属性与推理边界 |
| W3C SHACL | https://www.w3.org/TR/2017/REC-shacl-20170720/ | SHACL 1.0 | public standard；固定 Recommendation URL | 图约束映射 |
| JSON Schema | https://json-schema.org/draft/2020-12/json-schema-core.html | 2020-12 | public standard；固定版本 URL | Package 结构映射 |
| OpenAPI Specification | https://spec.openapis.org/oas/v3.1.1.html | 3.1.1 | public standard；固定版本 URL | API binding 投影边界 |
