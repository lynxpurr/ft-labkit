# config 单测：labkit.toml 合并 / [paths] 自由键值 / LABKIT_* 环境变量覆盖
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from labkit import config

ENV_KEYS = ("LABKIT_SWIFT_BIN", "LABKIT_TRAIN_PYTHON", "LABKIT_REF_PYTHON",
            "LABKIT_MODEL_DIRS")


class TestConfig(unittest.TestCase):
    def setUp(self):
        # 环境里若恰好设了 LABKIT_*，会让"缺省"断言失真——逐个清掉
        for k in ENV_KEYS:
            os.environ.pop(k, None)

    def test_defaults_when_no_file(self):
        cfg = config.load(path="/nonexistent/labkit.toml")
        self.assertEqual(cfg.swift_bin, "")
        self.assertEqual(cfg.paths, {})
        self.assertEqual(cfg.default_need_mib, 12000)

    def test_paths_section_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "labkit.toml"
            p.write_text('[paths]\nsolver = "/x/solver"\nother = "/y"\n',
                         encoding="utf-8")
            cfg = config.load(path=p)
        self.assertEqual(cfg.paths, {"solver": "/x/solver", "other": "/y"})

    def test_partial_file_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "labkit.toml"
            p.write_text('[engine]\nswift_bin = "/bin/swift"\n[gpu]\n'
                         'default_need_mib = 9000\n', encoding="utf-8")
            cfg = config.load(path=p)
        self.assertEqual(cfg.swift_bin, "/bin/swift")
        self.assertEqual(cfg.default_need_mib, 9000)
        self.assertEqual(cfg.sample_interval_s, 30)  # 未写的键取缺省
        self.assertEqual(cfg.paths, {})

    def test_env_overrides_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "labkit.toml"
            p.write_text('[engine]\nswift_bin = "/bin/swift"\n[models]\n'
                         'dirs = ["/a"]\n', encoding="utf-8")
            env = {"LABKIT_SWIFT_BIN": "/env/swift",
                   "LABKIT_TRAIN_PYTHON": "/env/python",
                   "LABKIT_REF_PYTHON": "/env/ref-python",
                   "LABKIT_MODEL_DIRS": "/m1:/m2:"}
            with patch.dict(os.environ, env):
                cfg = config.load(path=p)
        self.assertEqual(cfg.swift_bin, "/env/swift")
        self.assertEqual(cfg.train_python, "/env/python")
        self.assertEqual(cfg.ref_python, "/env/ref-python")
        self.assertEqual(cfg.model_dirs, ["/m1", "/m2"])  # 空段剔除

    def test_resolve_model_search_order(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / "a", Path(td) / "b"
            (b / "m-small").mkdir(parents=True)
            cfg = config.Config(model_dirs=[str(a), str(b)])
            self.assertEqual(cfg.resolve_model("m-small"), b / "m-small")
            with self.assertRaises(FileNotFoundError):
                cfg.resolve_model("m-missing")


if __name__ == "__main__":
    unittest.main()
