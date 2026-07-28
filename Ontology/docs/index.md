# EBO 文档索引

本页按规范依赖组织内容：先理解架构与元模型，再进入正向/逆向方法、发现可信度、演进、符合性和互操作，最后查看机器规范、示例、设计依据与内部实施记录。

## 依赖顺序

1. [总体架构](architecture.md)：目标、四层、单源多投影、MVP 边界与生命周期。
2. [元模型参考](metamodel.md)：Package 各定义、字段、引用与生命周期语义。
3. [正向工程指南](forward-engineering.md)：从能力问题到语义、行为、绑定、投影与场景验收。
4. [逆向工程指南](reverse-engineering.md)：证据采集、归一化、推断、冲突保留与人工裁决。
5. [发现置信度](discovery-confidence.md)：DiscoveryClaim、自证、反证、评分和治理提升。
6. [演进治理](evolution-governance.md)：版本、纠错、迁移、回滚与 v1→v2 walkthrough。
7. [符合性规范](conformance.md)：L0–L3-static 静态发布门禁、错误分层与命令。
8. [互操作映射](interoperability.md)：Palantir、Microsoft 与开放标准的映射及信息损失。
9. [Service operations example](../examples/service-operations/manifest.yaml)：完整四层 Package；另见 [Discovery claims](../examples/discovery/claims.yaml)、[Human adjudication](../examples/discovery/adjudication.yaml) 与 [Evolution example](../examples/evolution/migration.yaml)。
10. [Package JSON Schema](../spec/v1/ontology-package.schema.json) 与 [SHACL shapes](../spec/v1/ontology.shacl.ttl)：结构和 RDF 图机器规则。
11. [设计规格](superpowers/specs/2026-07-27-ontology-framework-design.md)：需求、设计原则、交付边界与验收标准。
12. [内部实施计划](superpowers/plans/2026-07-27-ontology-framework-mvp.md)：历史任务分解；它不是规范权威。

## 三条阅读路径

### 决策者

依次阅读总体架构、符合性规范、互操作映射和设计规格，重点判断业务价值、治理责任、发布风险与 MVP A/未来 runtime UI 的边界。

### Ontology Designer

依次阅读总体架构、元模型、正向工程、演进治理和 service-operations 示例；编辑 Package 后先运行 component validator，再运行统一静态发布验证器。

### System / Reverse Engineer

依次阅读元模型、逆向工程、发现置信度、互操作映射与 discovery/evolution 示例，保持 Observation、Inference、Binding 和运行事实的边界。

## Design coverage

| 用户能力 | 文档 | Schema | Example | Test |
|---|---|---|---|---|
| 设计 Ontology | architecture / metamodel / forward-engineering 文档 | Schema：Semantics、Kinetics、Bindings、Policies | Example：service-operations | Test：schema / SHACL / traceability |
| 正向构建 | forward-engineering / conformance 文档 | Schema：binding 与 traceability profile | Example：service-operations bindings | Test：release / traceability |
| 逆向发现 | reverse-engineering / discovery-confidence 文档 | Schema：EvidenceGraph 与 DiscoveryClaim | Example：discovery | Test：discovery |
| 持续纠错与优化 | evolution-governance 文档 | Schema：Change、Migration、Lineage | Example：evolution v1→v2 | Test：evolution |

## 发布命令与范围

```bash
python -m scripts.validate_package examples/service-operations
python -m scripts.validate_release examples/service-operations
python -m pytest
```

`validate_package` 保持 component-level；`validate_release` 汇总 L0–L3-static 机器规则并输出分层错误。静态通过不等于部署或 live operational certification，不连接外部系统，也不执行 Action runtime。MVP A 到此为止；connector、执行引擎、contract-test runtime 和 Web UI 是未来工作。
