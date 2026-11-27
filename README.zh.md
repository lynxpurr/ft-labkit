# ft-labkit

**预注册判决、证据只增不改的微调实验脚手架，由 coding agent 驱动。**

[English](README.md)

`labkit` 是一个很小的脚手架，供 coding agent 替你跑 LLM 微调项目。训练本身交给训练框架
（ms-swift、LLaMA-Factory、Axolotl、TRL 等）；labkit 管的是训练之外、决定你能否信任结果的那一层：

| 常见事故 | labkit 的做法 | 由谁强制 |
|---|---|---|
| 看到数字之后再调通过标准 | **预注册**。每个波次先写下判决规则，并把两种结局都枚举出来（过 → …／不过 → …）。 | `labkit wave` 插入条目；判决行还是占位符时，`labkit close` 拒绝收尾。 |
| 结果被覆盖、反复重读直到好看 | **证据只增不改**。报告写一次；重判是在旧文件旁边落一个新文件。 | 文件已存在时 `labkit.evidence.write_new` 拒写并报错。 |
| 检查通过，只是因为真实路径从没跑过 | **两侧对照测试**。每道门都配阴性对照：占位或损坏形态必须红，真实形态必须绿。 | 测试套件，每次推送都跑。 |
| 判分器恒真，没人发现 | **自检门 + 篡改样本**。判分器必须给金标打满分、必须把篡改过的答案判错。 | `labkit.gates.gold_gate` 与 `negative_controls`，由你的评测脚本在跑模型列之前调用。 |
| 同一个错犯三次 | **有晋升管道的教训账本**。同型教训第二次出现必须晋升：教训 → playbook 规则 → skill → 护栏代码。 | `labkit close` 要求当日 lessons 批次带晋升记录行；管道见 `docs/lessons-distillation.md`。 |
| "跑完了"（目录存在） | **以末步 checkpoint 为准的幂等判据**，按数据量计算，选中即校验。 | `labkit.ckpt`。 |

## 状态：v0，治理核心

| v0 已有 | v0 暂无 |
|---|---|
| `labkit new / doctor / wave / close` | 任何发起训练或推理的部件 |
| 项目模板：宪章、计划、交接、agent 协议 | 评测流水线、run 脚本生成器、泄漏检查、模板对拍 |
| `gates`、`evidence`、`ckpt`、`gpu`、`augment`、`config` | 证据浏览器、在线双臂对比 |

缺的部件在 [ROADMAP.md](ROADMAP.md) 里写明了行为；它们会在本仓里按行为规格实现。
**如果你自带训练与评测脚本**，只想要外面这一层治理，v0 现在就能用。

## 快速开始

要求 Linux、Python 3.11 及以上、`git`。零第三方依赖。

```bash
git clone https://github.com/lynxpurr/ft-labkit.git
cd ft-labkit && pip install .            # 或 pip install -e .
labkit --version                         # ft-labkit 0.1.0（后面括号里是实际运行的那份包的路径）

labkit new demo-lab                      # 用内置模板在当前目录生成 ./demo-lab
cd demo-lab
$EDITOR CONSTITUTION.md labkit.toml      # 一句话任务、停止条件、本机路径
labkit doctor                            # 每道门一条 JSON verdict；全绿才开工

labkit wave W1 baseline                  # 往 PLAN.md 插入预注册条目
# 先把判决规则填死（两种结局都写），然后才许跑任何东西。
# ……用你自己的脚本跑实验……
labkit close W1                          # 证据、判决、lessons、干净工作区缺一项即红
```

项目名只许小写字母、数字与单个连字符（1–64 个字符）——它同时是项目 skill 的目录名与 `name`。

`labkit doctor` 报五项检查，任一项红即非零退出：配置文件、引擎可执行文件与解释器、模型目录、
GPU（free 显存 + 进程表）、训练解释器能否 import `labkit`。它还会校验 `data/SHA256SUMS`
里登记的每个数据文件的 SHA-256。没有 NVIDIA GPU 时 GPU 门为红，其余读数照常给出。

如果机器上还有另一份叫 `labkit` 的包（已安装，或在 `PYTHONPATH` 上），它可能遮蔽这一份：
`labkit --version` 打印实际运行的那份包的路径；配置的解释器导入的是另一份时，`labkit doctor` 会告警。

## 一个项目怎么跑

```text
doctor 全绿
   │
   ▼
labkit wave W1 ──► PLAN.md：预注册判决规则（过 → …／不过 → …）
   │
   ▼
实验 + 评测            证据写一次，落在 reports/W1/
   │
   ▼
labkit close W1 ──► 判决已填 · 证据在 · lessons 批次 · 晋升记录行 · 工作区干净
   │
   └──► 下一个波次 ……
```

## 包里有什么

| 模块 | 职责 |
|---|---|
| `labkit.proj` | `labkit` 命令行：`new`、`doctor`、`wave`、`close` |
| `labkit.gates` | `gold_gate`、`negative_controls`、`checks_gate`：JSON verdict + 退出码，agent 可链式调用 |
| `labkit.evidence` | `write_new` 拒绝覆盖；`latest_by_key`；可再聚合 schema 门 |
| `labkit.ckpt` | 末步动态计算、按数字选 ckpt、末步硬门 |
| `labkit.gpu` | 预检门（free ≥ NEED + 进程表）、等待-重试、后台采样器 |
| `labkit.augment` | 确定性造数骨架：配额断言、跨模式去重、对账钩子、零 RNG |
| `labkit.config` | `labkit.toml` + `LABKIT_*` 环境变量覆盖；代码零绝对路径 |

这些件背后的方法见 [docs/methodology.md](docs/methodology.md)，每条规则由哪次事故而来见
[docs/lessons.md](docs/lessons.md)。

## 设计约束

- **只用标准库。** 零运行时依赖，任何训练 venv 里都能直接跑。
- **函数注入，不做 DSL。** 判分器、增强规则、实验臂留在你的项目里。
- **不硬编码本机路径。** 一切本机相关的东西走 `labkit.toml` 或 `LABKIT_*`。
- **一律 UTF-8。** 文件读写不随区域设置变，控制台输出不因编码失败。
- **纪律迁移，结论不迁移。** labkit 携带方法；超参、配比、阈值留在各项目。

## 语言

治理模板与方法论文档用中文书写（作者的工作语言）。`labkit close` 的关键词中英文都认，
`labkit wave --lang en` 会插入英文预注册条目。欢迎翻译。

## 参与

ft-labkit 由作者与 coding agent 协作开发；[AGENTS.md](AGENTS.md) 记录了 agent 遵循的约定。

比错别字大的改动，请先开 issue；见 [CONTRIBUTING.md](CONTRIBUTING.md)。在仓根运行
`python -m unittest discover -s tests -t .`，必须保持全绿。

## 许可证

[Apache-2.0](LICENSE)。第三方声明见 [NOTICE](NOTICE)。变更记录见 [CHANGELOG.md](CHANGELOG.md)。
