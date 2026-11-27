# SPEC-INDEX — 规格事实源路由器

> 本件只路由不双写。每类规格的"事实源在哪、怎么机器验证、怎么改"一表化。
> 拆 specs/ 目录的触发条件：PLAN 膨胀到不可维护，或项目延长/换手
> （届时走 specs/README.md 的形态）。

| 规格类型 | 事实源在哪 | 怎么机器验证 | 怎么改 |
|---|---|---|---|
| 项目契约（charter/Gate） | CONSTITUTION.md | 人工 + PLAN §2 验收 | 变更记录追加 |
| 实验规格（预注册 R#） | PLAN.md §4 波次条目 | labkit close（判决落表检查） | 校准块只改设计层 |
| 评测规格 | tools/ 评测/判分脚本 | 评测器自检门（金标满分 + 阴性对照） | 判分改动必须重过自检门 |
| 数据规格 | data/PROVENANCE.md | sha256sum -c + 泄漏检查 | PROVENANCE 追加 |
| 训练配置规格 | 训练产物目录的参数快照（如 args.json） | run 脚本的跑完核对 | 改超参=新 run 新目录 |
| 操作流程 | .agents/skills/{{PROJECT}}/SKILL.md | — | 与代码同 commit |
| 域结论 | notes/map.md | — | 波次戳追加制 |
| 方法论 | notes/playbook.md | — | 晋升管道（labkit 仓 docs/lessons-distillation.md） |
| 过程教训 | notes/lessons.md | labkit close（批次检查） | 追加批制 |
| 波次证据 | reports/<波次>/ | 证据只增不改 | rejudge 落新文件 |
