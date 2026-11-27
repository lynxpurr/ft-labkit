# gates 单测：gold 门 / 阴性对照 / 检查表门
# 纪律：每个门都要有"破坏形态必须红"的阴性对照。
import contextlib
import io
import json
import unittest
from typing import ClassVar

from labkit import gates


def toy_judge(sample, text):
    """玩具判分器：与金标逐字相等才过。"""
    return {"exact": text == sample["gold"], "nonempty": bool(text.strip())}


class TestGates(unittest.TestCase):
    SAMPLES: ClassVar[list[dict]] = [
        {"id": "a", "gold": "answer-a"}, {"id": "b", "gold": "answer-b"}]

    def gold_target(self, s):
        return s["gold"]

    def test_gold_gate_pass(self):
        r = gates.gold_gate(self.SAMPLES, self.gold_target, toy_judge,
                            required_true=["exact", "nonempty"])
        self.assertTrue(r.passed)
        self.assertEqual(r.exit_code(), 0)

    def test_gold_gate_catches_bad_judge(self):
        # 阴性对照：判分器把字段判错（恒错字段）→ gold 门必须红
        def bad_judge(s, t):
            return {"exact": False, "nonempty": True}
        r = gates.gold_gate(self.SAMPLES, self.gold_target, bad_judge,
                            required_true=["exact"])
        self.assertFalse(r.passed)
        self.assertEqual(len(r.detail["failures"]), 2)

    def test_negative_controls_catch_always_true_judge(self):
        # 最重阴性对照（对照与判分器共享盲区的教训）：恒真判分器过得了 gold 门，
        # 但必须过不了阴性对照门。
        def always_true(s, t):
            return {"exact": True, "nonempty": True}
        g = gates.gold_gate(self.SAMPLES, self.gold_target, always_true,
                            required_true=["exact"])
        self.assertTrue(g.passed)  # gold 门抓不到它
        mutants = [("upper", lambda s, t: t.upper()),
                   ("halved", lambda s, t: t[: max(1, len(t) // 2)])]
        nc = gates.negative_controls(self.SAMPLES, self.gold_target,
                                     always_true, mutants,
                                     required_true=["exact"])
        self.assertFalse(nc.passed)  # 阴性对照门必须抓到
        self.assertEqual(len(nc.detail["missed"]), 4)  # 2 样本 × 2 mutant 全失明

    def test_negative_controls_pass_with_good_judge(self):
        mutants = [("upper", lambda s, t: t.upper())]
        nc = gates.negative_controls(self.SAMPLES, self.gold_target, toy_judge,
                                     mutants, required_true=["exact"],
                                     extra_checks={"alias": True})
        self.assertTrue(nc.passed)
        nc2 = gates.negative_controls(self.SAMPLES, self.gold_target, toy_judge,
                                      mutants, required_true=["exact"],
                                      extra_checks={"alias": False})
        self.assertFalse(nc2.passed)  # 附加检查失败也要红

    def test_checks_gate(self):
        self.assertTrue(gates.checks_gate({"a": True, "b": 1}).passed)
        r = gates.checks_gate({"a": True, "b": False})
        self.assertFalse(r.passed)
        self.assertEqual(r.detail["failed"], ["b"])

    def test_verdict_json_render(self):
        r = gates.checks_gate({"a": True})
        v = json.loads(r.render())
        self.assertEqual(v["gate"], "checks")
        self.assertTrue(v["pass"])

    def test_verdict_keeps_non_ascii_keys_as_json(self):
        v = json.loads(gates.checks_gate({"配置文件": True}).render())
        self.assertEqual(v["checks"], {"配置文件": True})

    def test_run_gates_exit_code(self):
        ok = gates.checks_gate({"a": True}, name="ok")
        bad = gates.checks_gate({"a": False}, name="bad")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(gates.run_gates([ok]), 0)
            self.assertEqual(gates.run_gates([ok, bad]), 1)
        self.assertEqual(len(buf.getvalue().splitlines()), 3)  # 逐 gate 一行


if __name__ == "__main__":
    unittest.main()
