# ckpt — ckpt 选择器 / 末步动态计算 / 幂等判据
# 三条教训物化：
#  - `sort -t-` 被路径连字符污染 → checkpoint-73 静默当选末步 → 只按数字比较
#  - 幂等条件必须是"末步 ckpt 存在"而非"目录存在"（失败残留目录会被误判完成、
#    静默吞掉整条实验臂）
#  - 末步不写死：按数据行数与批大小动态计算；checkpoint 路径别写死步数
from __future__ import annotations

import json
import math
from pathlib import Path


def last_step(n_rows: int, batch: int, accum: int, epochs: int) -> int:
    """末步动态计算：⌈N/(bs×accum)⌉×epochs。

    例：1000 行 bs1×accum16 3ep → 189；1010 行 → 192；250 行 bs2×accum8 → 48。
    """
    return math.ceil(n_rows / (batch * accum)) * epochs


def list_ckpts(out_dir: str | Path) -> list[int]:
    """列出 checkpoint-N 的 N（数字升序；只认 checkpoint-<纯数字> 形态）。"""
    d = Path(out_dir)
    if not d.is_dir():
        return []
    steps = []
    for p in d.glob("checkpoint-*"):
        suffix = p.name.split("-", 1)[1] if "-" in p.name else ""
        if suffix.isdigit():
            steps.append(int(suffix))
    return sorted(steps)


def pick_last(out_dir: str | Path) -> Path:
    """选末步 ckpt。无 ckpt 大声失败（不猜、不退而求其次）。"""
    steps = list_ckpts(out_dir)
    if not steps:
        raise FileNotFoundError(f"[ckpt] {out_dir} 下无 checkpoint-<N>（未完成或残留目录）")
    return Path(out_dir) / f"checkpoint-{steps[-1]}"


def verify_last(out_dir: str | Path, expect: int) -> Path:
    """末步硬门：选中即校验，非 expect 即拒（选择器坏了大声失败）。"""
    got = list_ckpts(out_dir)
    if not got:
        raise FileNotFoundError(f"[ckpt] {out_dir} 下无 checkpoint（期望末步 {expect}）")
    if got[-1] != expect:
        raise AssertionError(
            f"[ckpt] 末步 {got[-1]} ≠ 期望 {expect}（训练中断或步数算错，拒跑）")
    return Path(out_dir) / f"checkpoint-{expect}"


def is_done(out_dir: str | Path, steps: int | None = None) -> bool:
    """幂等判据：指定 steps 时看 checkpoint-<steps> 是否在；
    未指定时看是否存在任意 ckpt（目录存在但零 ckpt 视为未完成——
    "残留目录误判完成"教训的物化）。"""
    got = list_ckpts(out_dir)
    if steps is not None:
        return steps in got
    return bool(got)


def load_train_args(ckpt: str | Path) -> dict:
    """读 ckpt 同级的训练参数快照 args.json（训练配置事实源：推理时从它恢复
    模板/思考开关/量化等配置；此处只做读取 + 存在性大声失败）。"""
    args_file = Path(ckpt).parent / "args.json"
    if not args_file.exists():
        raise FileNotFoundError(f"[ckpt] {args_file} 缺失（训练产物应自带）")
    return json.loads(args_file.read_text(encoding="utf-8"))
