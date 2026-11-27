# {{PROJECT}} — README

> 一句话：______（与 CONSTITUTION.md §1 同源）。

状态：（立项 / 进行中波次 / 归档）。入口阅读顺序：CONSTITUTION → PLAN → HANDOFF → SPEC-INDEX。

## 布局

- `CONSTITUTION.md` 宪章 · `PLAN.md` 计划与预注册判决 · `HANDOFF.md` 会话交接
- `SPEC-INDEX.md` 规格路由 · `notes/` 三账本（lessons/playbook/map）
- `tools/` run 脚本谱系 + 评测/判分脚本 · `data/` 数据与 PROVENANCE · `reports/` 只增不改证据
- `tests/` 判分器对照测试 · `research/` 调研 · `.agents/skills/{{PROJECT}}/` 操作路由

## 快速命令

（labkit 的安装见其仓 README；本项目脚本经 `labkit` 命令或 `python -m labkit` 调用。）

```bash
labkit doctor                 # 环境自检（在项目根跑）
labkit wave W1 baseline       # 开波（预注册模板入 PLAN；英文模板加 --lang en）
labkit close W1               # 收尾门（证据/判决/lessons/晋升/git）
```
