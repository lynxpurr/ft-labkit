# gates — gold 自校准门 + 阴性对照 mutant 框架 + 检查表门
# 全部输出 JSON verdict + 退出码：机器可查，agent 可链式执行。
# 最强共识：金标过判分器须得已知满分，不过则评测器有 bug，禁跑模型。
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from ._io import out


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: dict = field(default_factory=dict)

    def render(self) -> str:
        return json.dumps(
            {"gate": self.name, "pass": self.passed, **self.detail},
            ensure_ascii=False)

    def exit_code(self) -> int:
        return 0 if self.passed else 1


def gold_gate(
    samples: list,
    gold_target: Callable,      # sample -> 金标回答文本（或任何可判对象）
    judge: Callable,            # (sample, target) -> dict（布尔字段构成判分结果）
    required_true: list[str],   # 金标上必须为真的判分字段
    required_false: list[str] | None = None,
    name: str = "gold",
) -> GateResult:
    """金标自测：所有样本 × 所有 required 字段全中才 PASS。

    用法（评测器 main 里）：
        r = gold_gate(samples, gold_target, score_item, required_true=["fmt_ok", "f1_full"])
        print(r.render()); sys.exit(r.exit_code())   # 不过禁跑模型列
    """
    required_false = required_false or []
    failures: list[dict] = []
    for s in samples:
        rec = judge(s, gold_target(s))
        bad = [k for k in required_true if not rec.get(k)]
        bad += [k for k in required_false if rec.get(k)]
        if bad:
            failures.append({"id": s.get("id", "?"), "violated": bad})
    return GateResult(name, not failures, {
        "n": len(samples), "required_true": required_true,
        "required_false": required_false, "failures": failures,
        # 已知答案锚变体：gold_target 换成"返回已知答案的闭包"即覆盖
        # （判分器无法构造 gold_target 时，用一份已知答案当锚）。
    })


def negative_controls(
    samples: list,
    gold_target: Callable,
    judge: Callable,
    mutants: list,              # [(label, tamper: (sample, target) -> target)] 篡改后必须判错
    required_true: list[str],   # 与 gold_gate 同一口径：required 全真 = 判对
    extra_checks: dict[str, bool] | None = None,
    name: str = "negative-controls",
) -> GateResult:
    """阴性对照（防恒真判分器）：每个 mutant 必须被判"错"，任一判"对"即 FAIL。

    对照只守它所扰动的那类错误——mutants 至少应含幅值与符号两类独立扰动
    （对照只做幅值×0.5 时，对"符号写反"失明的判分器可以安然通过）。
    extra_checks: 别名回归等附加布尔（键名即证据）。
    """
    missed: list[dict] = []
    n_mut = 0
    for s in samples:
        target = gold_target(s)
        for label, tamper in mutants:
            n_mut += 1
            rec = judge(s, tamper(s, target))
            # 篡改后 required 任一仍全真 = 判分器对该 mutant 失明
            if all(rec.get(k) for k in required_true):
                missed.append({"id": s.get("id", "?"), "mutant": label})
    extra = extra_checks or {}
    extra_bad = [k for k, ok in extra.items() if not ok]
    return GateResult(name, not missed and not extra_bad, {
        "n_mutants": n_mut, "missed": missed,
        "mutant_labels": [m[0] for m in mutants],
        "extra_checks": extra, "extra_failed": extra_bad,
    })


def checks_gate(checks: dict[str, bool], name: str = "checks") -> GateResult:
    """检查表门：{项: 布尔} 全真才过；verdict 带逐项布尔与失败清单。"""
    norm = {k: bool(v) for k, v in checks.items()}
    bad = [k for k, ok in norm.items() if not ok]
    return GateResult(name, not bad,
                      {"failed": bad, "n": len(norm), "checks": norm})


def run_gates(results: list[GateResult]) -> int:
    """链式执行出口：逐 gate 打 verdict，任一 fail 即非零退出（agent 可链式调用）。"""
    for r in results:
        out(r.render())
    return 1 if any(not r.passed for r in results) else 0
