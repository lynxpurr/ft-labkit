---
name: {{PROJECT}}
description: {{PROJECT}} 仓的标准操作路由——开工检查、训练/评测标准动作、波次闭环。
---

# {{PROJECT}} — 操作路由（仓内 skill）

> 只路由不双写：本件告诉 agent 在这个仓里标准动作走哪；细节事实源见指针。
> 其他 agent 宿主可把本目录 symlink 到各自的 skills 目录。

## §1 开工序

HANDOFF.md §1 五步开工检查 → labkit doctor 全绿 → 读当前波次预注册。

## §2 资产坐标

评测/判分脚本 tools/ · run 脚本与 spec tools/ · 证据 reports/<波>/
账本 notes/{lessons,playbook,map}.md · 数据指纹 data/{PROVENANCE.md,SHA256SUMS}。

## §3 训练标准动作

run 脚本由 spec 生成并自带门：未知档大声失败 / 幂等跳过 / GPU 预检拒跑不静默 OOM /
后台采样器 / 跑完核对参数快照与末步 ckpt。

## §4 评测标准动作

评测器自检门先行（不过禁跑模型）→ 推理 → 判分 → 汇总表。
证据只增不改；口径修订走 rejudge。

## §5 波次闭环

wave（预注册写死）→ 实验 → close（证据/判决落表/lessons 批次/晋升记录/git 提交）。

## §6 红线

AGENTS.md 红线节。

## §7 维护约定

判分/数据/超参改动与本文件同 commit。
新增或修改检查/门时，先过 notes/playbook.md §4 的检查器规则（能变红、防自匹配、只看
git 索引、常驻读数当场定性、检查接到门上）；逐条形状见 labkit 仓 docs/lessons.md 的 A 节。
