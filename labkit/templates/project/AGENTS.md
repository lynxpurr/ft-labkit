# AGENTS.md — {{PROJECT}} 的 agent 操作协议

> 开工先读本件 → HANDOFF.md §1 开工检查 → 当前波次的 PLAN 预注册条目。
> 工具与方法纪律见 labkit 文档（AGENTS.md、docs/methodology.md），不重述。

## 生命周期

```
doctor 全绿 → labkit wave <id> <名> → 填预注册（判决写死才许跑实验）
  → 实验与评测（评测器自检门先行）
  → labkit close <id>（收尾门：证据/判决落表/lessons 批次/晋升记录/git 干净）
```

## 红线（违者停，交人裁决）

- 评测器自检门未过就跑模型评测列
- 实验跑完后修改该波预注册判决原文
- 修改 reports/ 下已落盘证据
- 评测集数据流入训练集（增强只许源自 train）

## 本项目特有约定

（建仓时填：评测/判分脚本入口、评测集清单、模型档位、GPU 需求线、外部只读借用路径。）
