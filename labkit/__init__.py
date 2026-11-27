# labkit — 微调项目脚手架：预注册判决 + 证据纪律 + 机器可查的门
#
# v0 范围：项目生命周期 CLI（new/doctor/wave/close）与通用护栏件
# （config/gates/evidence/ckpt/gpu/augment）。训练与评测件见 ROADMAP.md。
# 本包 stdlib-only（python>=3.11）；一切跨仓路径经 config.load()
# （labkit.toml + LABKIT_* 环境变量），代码零绝对路径；
# 文件读写显式 utf-8，控制台输出不因区域设置抛编码错（_io）。
__version__ = "0.1.0a1"
