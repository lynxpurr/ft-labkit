# augment 单测：确定性造数骨架（配额/去重/对账/零 RNG）
import json
import unittest
from typing import ClassVar

from labkit import augment


class TestAugment(unittest.TestCase):
    BASE: ClassVar[list[dict]] = [{"id": f"s{i}", "text": f"t{i}"} for i in range(1, 6)]

    def mode(self, name="m", quota=3, suffix="#m", fail_audit=False,
             dup_id=False):
        def make(r):
            new = dict(r)
            if not dup_id:
                new["id"] = r["id"] + suffix
            new["aug"] = name
            return new

        def audit(rows):
            if fail_audit:
                raise AssertionError("audit: 新行缺 aug 标记")
            assert all(r.get("aug") == name for r in rows)

        return augment.ModeSpec(name=name, quota=quota,
                                pool=lambda r: True, make=make, audit=audit)

    def test_gen_arm_ok(self):
        arm = augment.gen_arm(self.BASE, [self.mode()])
        self.assertEqual(len(arm), 5 + 3)
        self.assertEqual([r["id"] for r in arm[:5]],
                         [f"s{i}" for i in range(1, 6)])  # base 原序在前
        self.assertTrue(all(r["id"].endswith("#m") for r in arm[5:]))
        self.assertEqual(augment.arm_stats(arm, [self.mode()]),
                         {"total": 8, "base": 5, "modes": {"m": 3}})

    def test_quota_unfilled_loud(self):
        with self.assertRaises(AssertionError):  # 池 5 凑不出配额 8
            augment.gen_arm(self.BASE, [self.mode(quota=8)])

    def test_used_dedup_across_modes(self):
        # 同一源行不给两个模式用：第二模式只剩 2 条可用源 → 配额 3 凑不满
        with self.assertRaises(AssertionError):
            augment.gen_arm(self.BASE,
                            [self.mode(name="m1", suffix="#m1"),
                             self.mode(name="m2", suffix="#m2")])

    def test_audit_violation_loud(self):
        with self.assertRaises(AssertionError):
            augment.gen_arm(self.BASE, [self.mode(fail_audit=True)])

    def test_arm_id_dup_loud(self):
        # make 不改 id → arm 内 id 重复必须大声失败
        with self.assertRaises(AssertionError):
            augment.gen_arm(self.BASE, [self.mode(dup_id=True)])

    def test_deterministic(self):
        a1 = augment.gen_arm(self.BASE, [self.mode()])
        a2 = augment.gen_arm(self.BASE, [self.mode()])
        self.assertEqual(json.dumps(a1), json.dumps(a2))  # 零 RNG 逐字节稳定
        # 选样按 id 序：base 顺序打乱，增强产物不变（base 段保原序）
        a3 = augment.gen_arm(list(reversed(self.BASE)), [self.mode()])
        self.assertEqual(json.dumps(a1[5:]), json.dumps(a3[5:]))
        self.assertEqual([r["id"] for r in a3[:5]],
                         [f"s{i}" for i in range(5, 0, -1)])


if __name__ == "__main__":
    unittest.main()
