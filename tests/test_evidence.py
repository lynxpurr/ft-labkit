# evidence 单测：证据只增不改 / 按 generated 取最新 / 可再聚合 schema 门
import json
import tempfile
import unittest
from pathlib import Path

from labkit import evidence


class TestEvidence(unittest.TestCase):
    def test_write_new_once_then_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "ev.json"
            evidence.write_new_json(p, {"a": 1})
            with self.assertRaises(evidence.EvidenceExistsError):
                evidence.write_new_json(p, {"a": 2})
            self.assertEqual(json.loads(p.read_text(encoding="utf-8")), {"a": 1})  # 原文未动

    def test_write_new_is_utf8_bytes(self):
        """回归：证据含中文时，缺省编码落盘在非 UTF-8 区域设置下会抛错或写成乱码。"""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ev.json"
            evidence.write_new_json(p, {"判据": "证据只增不改"})
            self.assertEqual(p.read_bytes(),
                             json.dumps({"判据": "证据只增不改"}, ensure_ascii=False,
                                        indent=2).encode("utf-8"))

    def test_latest_by_key_generated_not_lex(self):
        # 教训：不赌字典序，按 generated 取最新
        entries = [
            {"arm": "g", "src": "h", "generated": "2001-02-03T12:34:56+00:00",
             "summary": {"old": 1}},
            {"arm": "g", "src": "h", "generated": "2001-02-04T09:30:00+00:00",
             "summary": {"new": 2}},
            {"arm": "z", "src": "h", "generated": "2001-02-03T18:00:00+00:00",
             "summary": {"z": 3}},
        ]
        out = evidence.latest_by_key(entries, ["arm", "src"])
        self.assertEqual(out["g-h"], {"new": 2})
        self.assertEqual(out["z-h"], {"z": 3})

    def test_ensure_detail_fields(self):
        ok = [{"id": "1", "pred": [1], "cov": 0.5}]
        evidence.ensure_detail_fields(ok, ["pred", "cov"])
        bad = [{"id": "1", "pred": [1]}, {"id": "2"}]
        with self.assertRaises(AssertionError):
            evidence.ensure_detail_fields(bad, ["pred", "cov"])

    def test_stamp_is_utc_iso(self):
        self.assertRegex(evidence.stamp(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")


if __name__ == "__main__":
    unittest.main()
