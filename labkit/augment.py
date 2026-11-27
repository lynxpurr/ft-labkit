# augment — 确定性造数骨架
# 纪律：增强只源自 train 内部、评测集一字不入；零 RNG（可复现）；
# 稳定排序 + 配额断言 + 生成后对账（判分器/校验器复检）。域变换规则不入本仓。
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ModeSpec:
    """一个增强模式的规格。

    pool: 源行筛选谓词（如"输出含某字段且输入未提及"）
    make: 源行 -> 新行（变换本体；确定性无 RNG；新行 id 建议带模式后缀防 arm 内重复）
    quota: 目标条数（必须凑满，凑不满=池不足，大声失败）
    audit: 新行批量对账（如过 validate / 判分器复检；违规 raise）
    """
    name: str
    quota: int
    pool: Callable[[dict], bool]
    make: Callable[[dict], dict]
    audit: Callable[[list[dict]], None] = field(default=lambda rows: None)


def pick_pool(rows: list[dict], pool: Callable[[dict], bool],
              used: set, n: int) -> list[dict]:
    """稳定选样：id 序（零随机），跳过已被其他模式用过的源行（used 跨组去重——
    同一条源行不给两个模式重复用）。"""
    cand = sorted((r for r in rows if pool(r) and r["id"] not in used),
                  key=lambda r: str(r["id"]))
    if len(cand) < n:
        raise AssertionError(
            f"[augment] 池不足：需 {n} 只有 {len(cand)}"
            f"（放宽 pool 或减小 quota；凑不满不许静默缩水）")
    return cand[:n]


def gen_mode(base_rows: list[dict], spec: ModeSpec, used: set) -> list[dict]:
    """执行一个模式：选样 → 逐行变换 → 唯一性断言 → 对账。"""
    src = pick_pool(base_rows, spec.pool, used, spec.quota)
    out = [spec.make(r) for r in src]
    ids = [r["id"] for r in out]
    assert all(ids), "[augment] 新行缺 id"
    assert len(ids) == len(set(ids)), f"[augment] {spec.name} 产出 id 重复"
    spec.audit(out)  # 对账钩子（违规即 raise——增强产物未过对账不许入训练集）
    used.update(r["id"] for r in src)
    return out


def gen_arm(base_rows: list[dict], modes: list[ModeSpec]) -> list[dict]:
    """arm 合并：base + 各模式产物确定性拼接 + 条数与 id 唯一断言。

    arm = 训练臂数据集（"base + 模式 A 的产物 + 模式 B 的产物 + …" 的形状）。
    产物顺序：base 原序 + 模式注册序（可复现，同输入逐字节稳定）。
    """
    used: set = set()
    parts = [list(base_rows)]
    for spec in modes:
        parts.append(gen_mode(base_rows, spec, used))
    arm = [r for part in parts for r in part]
    ids = [r["id"] for r in arm]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    assert not dup, (f"[augment] arm 内 id 重复：{dup[:8]}"
                     "（同源多变体须改 id 规约，如 <id>#<mode>）")
    expect = len(base_rows) + sum(s.quota for s in modes)
    assert len(arm) == expect, f"[augment] arm 条数 {len(arm)} ≠ 预期 {expect}"
    return arm


def arm_stats(arm: list[dict], modes: list[ModeSpec]) -> dict:
    """arm 统计证据（供 PROVENANCE/reports 落档）。"""
    return {"total": len(arm), "base": len(arm) - sum(s.quota for s in modes),
            "modes": {s.name: s.quota for s in modes}}
