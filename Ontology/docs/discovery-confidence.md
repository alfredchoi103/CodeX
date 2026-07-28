# DiscoveryClaim Confidence

DiscoveryClaim 是 observation 之上的可解释、可证伪候选结论。结构示例见 [Evidence Graph](../examples/discovery/evidence-graph.yaml)、[A–D Claims](../examples/discovery/claims.yaml) 与 [Human Adjudication](../examples/discovery/adjudication.yaml)，机器结构以 [Ontology Package Schema](../spec/v1/ontology-package.schema.json) 为准。proposed claim snapshot 保持不可变；human decision 独立记录，accepted 只触发 baseline promotion proposal，不直接改写 claim 或发布 Ontology。

## 字段契约

- `id`、`label`、`statement` 与 `status` 标识并陈述候选；发现输出必须从 `proposed` 或 `hypothesis` 开始。
- `reasoningRules` 非空，记录确定性 rule ID 或附解释的规则对象。
- `evidenceRefs` 非空且只引用 supporting observations；`counterEvidenceRefs` 必须出现，允许为空。两者及 rationale 引用只能使用 `internalStableId`。v1 采用 allowlist：允许无冒号 stable token，且 `domain:` 是唯一注册的 colon namespace（如 `domain:Known`）；`did:`、`foo:`、URI 等任何其他冒号前缀均无效。未来新增内部命名空间必须升级 schema 并显式注册，不能扩展为任意 scheme。
- `counterEvidenceLevel` 是结构化等级 `none|minor|material|strong|coreContradiction`；`counterEvidenceAssessment` 仅作为 summary 文本，不参与解析，并说明已查范围、真实冲突与未知项。
- `alternatives` 至少一个，记录其他合理解释；没有已知替代时也必须明确说明搜索范围与“未识别到替代”。
- `confidenceDimensions` 精确包含六维；`confidence` 与 `grade` 必须由确定性算法重算一致。
- `falsifiers`、`validationQuestions`、`capabilityQuestions` 均非空，分别说明如何推翻、如何验证及本体应回答什么。
- `provenance` 闭合，要求 `extractorVersion`、`ruleSetVersion`、`generatedAt`，可选 `model`。

## 七个自我理解问题

1. 我声称了什么，边界在哪里？
2. 哪些可复核 observation 直接支持它？
3. 使用了哪些确定性规则，能否复现？
4. 找到了什么反证，哪些范围尚未检查？
5. 还有哪些合理替代解释？
6. 什么观察会证伪它，下一步应问什么验证问题？
7. 它回答了什么 capability question，谁有权决定提升？

## 证据可采信性

证据必须可定位、可复核、有采集时间、有完整性哈希且提取器版本明确。运行记录能证明样本中发生过什么，却不能单独证明所有允许行为；静态 code 能证明路径存在，却不能单独证明路径被执行；config 能证明采集时的值，却不能证明外部 override；文档或 OpenAPI 能证明声明契约，却不能单独证明实现一致。

**LLM 不是证据。** LLM 可以辅助 semantic matching、生成 alternatives 或提出问题，但输出只能进入 inference 与 provenance；没有独立 observation 支持时不得提高证据覆盖率或 runtime support。

## 六维权重与确定性舍入

| Dimension | Weight | 含义 |
| --- | ---: | --- |
| `crossSourceAgreement` | 25% | 独立来源是否一致 |
| `evidenceCoverage` | 20% | 声明关键部分是否都有证据 |
| `runtimeSupport` | 20% | 是否存在运行观察支持 |
| `semanticSpecificity` | 15% | 概念、关系与边界是否具体 |
| `constraintConsistency` | 10% | 约束之间是否自洽 |
| `counterEvidenceAssessment` | 10% | 反证的冲突强度及其置信度扣分；冲突越强，扣分越大 |

六维都必须是 0–100 的整数，布尔值无效。计算 `sum(dimension × weight)` 后以十进制 `ROUND_HALF_UP` 舍入为 0–100 整数；禁止依赖 Python bankers rounding。实现见 [`scripts/confidence.py`](../scripts/confidence.py)。

### Counter-evidence rubric

`counterEvidenceAssessment` 衡量的是冲突强度，而不是“是否诚实填写”。它只允许以下单调等级；记录检索范围是评分前提，但不能抵消冲突本身：

| Score | Conflict level | 判定 |
| ---: | --- | --- |
| 100 | `none` — no material conflict | 已记录的合理检索未发现 material conflict；未知范围不得影响 claim 核心。 |
| 75 | `minor` — minor unresolved | 存在 minor unresolved 冲突或非核心不确定性，claim 经收窄后仍成立。 |
| 50 | `material` — material bounded | 存在 material bounded 冲突，只有明确限定范围内的 statement 可保留。 |
| 25 | `strong` — strong unresolved | strong unresolved 反证显著削弱 statement，尚无足够裁决。 |
| 0 | `coreContradiction` — core contradiction | core contradiction 直接否定 claim 核心。 |

例如，事件早于 read model 更新只与“立即可读”发生 minor unresolved 冲突，可评 75；如果 claim 明确声称自动分配已在生产启用，而唯一生产配置将其关闭，则是 core contradiction，必须评 0。不得仅因评估过程完整就给 100。

Validator 不解析 assessment summary 来猜等级；它直接验证 `counterEvidenceLevel`、`confidenceDimensions.counterEvidenceAssessment` 与同名 `confidenceRationale.score` 三者一致。

## Grade 与治理

- A：85–100，强候选；仍需人工裁决。
- B：70–84，较强候选；需要关闭主要未知项。
- C：50–69，弱候选；通常需要补证或缩小 statement。
- D：0–49，探索性假设；不得进入 Baseline Ontology。

Grade 只表达发现置信度，不表达批准、正确性或风险接受。即使 A 也不得自动把 `status` 改为 `accepted`。

## Falsification、promotion 与 governance

验证者应优先执行 falsifiers 和 validation questions：一旦观察到证伪事实，保留原 claim 与证据，创建修订或撤回记录并重算置信度。Promotion 必须确认引用仍可解析、score/grade 一致、反证已裁决、能力问题有验收结果，并由有权人员完成 governance decision。模型版本变化、来源哈希变化或新增反证会触发重新评估，不得静默覆盖历史。
