# ckpt 单测：末步动态计算 / 数字序选择 / 幂等判据 / 末步硬门 / 参数快照读取
import json
import tempfile
import unittest
from pathlib import Path

from labkit import ckpt


class TestCkpt(unittest.TestCase):
    def test_last_step_anchors(self):
        # 向上取整的两侧：除得尽与除不尽
        self.assertEqual(ckpt.last_step(256, 2, 8, 3), 48)    # 16 步/epoch，除得尽
        self.assertEqual(ckpt.last_step(257, 2, 8, 3), 51)    # 16.06 → 17 步/epoch
        self.assertEqual(ckpt.last_step(1000, 1, 16, 3), 189)
        self.assertEqual(ckpt.last_step(1010, 1, 16, 3), 192)

    def test_pick_last_numeric_not_lex(self):
        # 教训：字典序 73 < 9（按字符串比较）——必须按数字
        with tempfile.TemporaryDirectory() as td:
            for n in (9, 73):
                (Path(td) / f"checkpoint-{n}").mkdir()
            self.assertEqual(ckpt.pick_last(td).name, "checkpoint-73")

    def test_pick_last_empty_loud(self):
        with tempfile.TemporaryDirectory() as td, self.assertRaises(FileNotFoundError):
            ckpt.pick_last(td)

    def test_is_done_residual_dir_not_done(self):
        # 目录存在但零 ckpt = 未完成（残留目录不许当完成）
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "output-x").mkdir()  # 残留目录
            self.assertFalse(ckpt.is_done(Path(td) / "output-x"))
            (Path(td) / "output-x" / "checkpoint-3").mkdir()
            self.assertTrue(ckpt.is_done(Path(td) / "output-x"))
            self.assertFalse(ckpt.is_done(Path(td) / "output-x", steps=5))
            self.assertTrue(ckpt.is_done(Path(td) / "output-x", steps=3))

    def test_verify_last_mismatch_loud(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "checkpoint-73").mkdir()
            with self.assertRaises(AssertionError):
                ckpt.verify_last(td, 219)  # 末步 73 ≠ 期望 219 → 拒
            self.assertEqual(ckpt.verify_last(td, 73).name, "checkpoint-73")

    def test_load_train_args(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "args.json").write_text('{"seed": 7}', encoding="utf-8")
            self.assertEqual(ckpt.load_train_args(Path(td) / "checkpoint-1"),
                             {"seed": 7})
        with tempfile.TemporaryDirectory() as empty, self.assertRaises(FileNotFoundError):
            ckpt.load_train_args(Path(empty) / "checkpoint-1")

    def test_load_train_args_reads_utf8_regardless_of_locale(self):
        """回归：训练框架写的参数快照含非 ASCII 路径/备注时，缺省编码读取会出错。"""
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "args.json").write_text(
                json.dumps({"dataset": "/数据/train.jsonl", "note": "备注"}, ensure_ascii=False),
                encoding="utf-8")
            got = ckpt.load_train_args(Path(td) / "checkpoint-1")
        self.assertEqual(got["note"], "备注")


if __name__ == "__main__":
    unittest.main()
