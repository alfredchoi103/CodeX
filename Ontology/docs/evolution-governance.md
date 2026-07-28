# Ontology 版本、纠错与演进治理

本规范配合 [Ontology Package JSON Schema](../spec/v1/ontology-package.schema.json)、[总体架构](architecture.md) 与可验证的 [v1→v2 migration](../examples/evolution/migration.yaml) 使用。MUST（必须）表示发布门禁，SHOULD（应该）表示通常要求且偏离需说明，MAY（可以）表示受控可选项。

## 三层版本语义与 SemVer

- `specVersion` 版本化 Package 格式、Schema 与验证语义；可使用完整 SemVer prerelease/build 标识。
- `ontologyVersion` 版本化某个 `ontologyId` 的业务语义；采用严格 `X.Y.Z` core SemVer，禁止 prerelease 与 build metadata。
- `elementRevision` 是单元素的审计修订序号，不替代发布版本，也不能让元素绕过 Package 发布。

影响等级满足 `patch < minor < major`，一次发布取所有变化的最大影响。仅描述、证据说明或 metadata 变化为 patch；增加兼容元素为 minor；rename、retype、split、merge、relink、supersede、retract 默认 major。唯一 alias 例外是纯 rename：只有闭合 `aliasProof` 同时证明 `stableIdPreserved: true`、`consumerIdentifiersUnchanged: true` 并引用非空内部证据时 MAY 判为 minor。Validator 必须沿 Schema `x-traceability-profile` 从真实前后 Package 抽取稳定 ID 对应定义，核对 migration 的 originalDefinition/newDefinition 与真实定义完全一致，并对真实递归 diff 判定只改变 display 路径；migration 自报的 label-only diff 不能掩盖 property/type/link/lifecycle 改动。retype、relink 等结构修正即使附 proof 仍为 major。版本必须精确升级：Patch `1.2.3→1.2.4`，Minor `1.2.3→1.3.0`，Major `1.2.3→2.0.0`；降级、跳级和以大版本掩盖小影响都不合规。

已发布的 `ontologyVersion + contentDigest` 是不可变快照。同版本不同摘要必须拒绝；即使摘要相同，只要声明 evolution 就必须产生更高的新版本，不能用同版本 change/lineage 冒充发布。

## 认识状态与纠错原则

元素按 `hypothesis → proposed → accepted → deprecated` 演进；证据证伪 accepted 定义时进入 `retracted`。accepted 只是当前证据下的治理决定，不代表永真。新观察只能创建 Proposal，不能直接改变认识状态。

错误定义不得删除历史。旧稳定 ID、原定义、错误原因、证据、影响与 lineage 必须保留，使旧数据、审计和文档持续可解释。Change 本身不能替代独立 lineage；每个纠正 change 的 predecessor/successor 集合与 operation 必须和唯一 lineage entry 双向一一匹配，额外 lineage 同样拒绝，不能用 lineage-only retract 绕过 cause、evidence 与 impact。重复边、两个 change 共享一条 lineage、自环或跨边有向环均拒绝。`predecessorRefs` 始终非空，只有纯 `retract` 的 `successorRefs` 必须为空，且 predecessor 必须保留在目标 Package 并标为 `retracted`；其余操作 successor 必须非空。七种纠正操作是：

- `rename`：只改 `label|name|descriptions|aliases` 展示路径，稳定 ID 必须保持且 diff 不得为空；
- `retype`：改变类型或值域并映射前后定义；
- `split`：一个 predecessor 映射到多个 successor；
- `merge`：多个 predecessor 映射到一个 successor；
- `relink`：用具体关系替代错误或模糊关系；
- `supersede`：由更准确定义接替但保留旧定义；
- `retract`：撤销错误结论，必须记录 cause、evidence 与 impact。

## 发布工作流与验证等级

标准流程为 `Branch → Proposal → Impact Analysis → Review → L0 → L1 → L2 → L3 → Release → Observation`。

Branch 隔离编辑；Proposal 陈述动机、证据和差异；Impact Analysis 覆盖 data、API、action、query、policy、document、audit 与 consumers；Review 由 Owner/Steward/Reviewer 审查。L0 验证结构和 Schema，L1 验证引用、lineage 与语义，L2 验证行为、权限、补偿与场景，L3 验证绑定、迁移、摘要和运行准备。Release 生成不可变版本；Observation 记录漂移和结果，必要时触发下一 Proposal。

## 迁移、回填与回滚

破坏性变化 MUST 提供 migrationStrategy、backfill、rollback、compatibilityWindow、dualRead/dualWrite 说明、acceptanceEvidence 与完整 impactAnalysis。可组合策略包括：

- `coexist` 在兼容窗口并存新旧读模型；
- `alias` 只用于不改变含义的定位兼容；
- `dual-read` 比较新旧结果并记录差异；
- `temporary dual-write` 风险高，只能在 `idempotencyKey`、ordering、conflictAuthority 和非空 stopConditions 明确时短期启用，且 migrationStrategy 必须显式包含该策略；
- `backfill` 必须可重跑、可审计并隔离歧义数据；
- `feature flag` 分批切换消费者；
- `rollback` 必须是闭合对象，包含非空 procedure、triggerConditions、verificationSteps；恢复旧读路径时不得删除新 ID、lineage 或审计历史。

兼容窗口必须有起止和退出准则。默认不启用 dual-write：双权威写入会产生顺序、部分失败和语义分叉。回滚是可执行安全路径，不是“恢复备份”一句话。

## 触发器、观察与优化指标

触发器包括新权威证据、跨源冲突、orphan 增长、constraint violations、action failures、能力问题失败、监管变化、消费者破坏性影响与人工纠错。每个版本 SHOULD 比较以下指标：

- evidence/traceability `coverage`；
- unresolved `conflicts` 与 `orphans`；
- `constraint violations` 与 `action failures`；
- competency `capability pass` rate；
- `human correction` rate；
- projected `breaking impact` 及受影响消费者数。

指标优化不能牺牲证据真实性：较高 coverage 不得通过删除冲突获得，较低 correction 也不得通过隐藏 retraction 获得。

<a id="v1-v2-walkthrough"></a>
## v1→v2 walkthrough

[v1](../examples/evolution/v1/manifest.yaml) 在当时证据下 accepted 了混合自然人与组织属性的 `Actor`，以及含义模糊的 `Actor.relatedTo.Actor`；它结构合法，错误是 epistemic，而不是 Schema 非法。[v2](../examples/evolution/v2/manifest.yaml) 保留并标记这两个元素为 retracted，将 Actor split 为 `Person` 与 `Organization`，再将模糊关系 relink 为 `Person.memberOf.Organization` 和 `Organization.representedBy.Person`。

[migration.yaml](../examples/evolution/migration.yaml) 记录原/新定义、冲突证据、split/relink/retract、逐领域影响、兼容窗口、dual-read、回填、feature flag、验收和 rollback。dual-write 明确为 false，因为把角色化关系反写到模糊关系会丢失语义。任何旧 accepted ID 的消失必须有 successor lineage 或 retract；历史 Actor ID 仍可通过 lineage 解析。

## 机器可验证与人工决策边界

机器可验证：SemVer 边界、操作枚举、最大影响、必填字段、闭合影响对象、稳定 ID 引用、split/merge 基数、rename 稳定 ID、摘要不可变、accepted 元素消失规则，以及 migration/schema/package 有效性。

人工决策：证据是否权威、歧义分类是否可接受、业务影响严重度、兼容窗口长度、临时 dual-write 风险是否值得、验收阈值与最终批准。自动化 MAY 提供建议，但不得伪造证据、静默删除历史或替代 Reviewer 决策。
