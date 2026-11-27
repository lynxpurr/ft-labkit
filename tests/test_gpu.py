# gpu 单测：预检门 / 等待-重试 / 采样器 / 真查询函数（假 nvidia-smi）
# 查询函数全部可注入——单测不依赖真 GPU。
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from labkit import gpu


class TestGpu(unittest.TestCase):
    def test_precheck_pass_fail_injected(self):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            got = gpu.precheck(4100, "t/pass", free_query=lambda: 5100,
                               apps_query=list)
            self.assertTrue(got["pass"])
            got = gpu.precheck(6100, "t/fail", free_query=lambda: 5100,
                               apps_query=lambda: [{"pid": "1", "name": "proc-A",
                                                    "mib": 610}])
        self.assertFalse(got["pass"])
        self.assertEqual(got["compute_apps"][0]["name"], "proc-A")
        # 无论过否都打进程表（双查）
        self.assertIn('"compute_apps": [{"pid": "1"', buf.getvalue())

    def test_precheck_no_gpu_tool(self):
        def boom():
            raise RuntimeError("nvidia-smi 不在 PATH")
        with contextlib.redirect_stdout(io.StringIO()):
            got = gpu.precheck(1, "t/nogpu", free_query=boom)
        self.assertFalse(got["pass"])
        self.assertIn("error", got)

    def test_wait_for_free(self):
        state = {"n": 0}

        def poll():
            state["n"] += 1
            return 5100 if state["n"] >= 2 else 1000
        self.assertTrue(gpu.wait_for_free(5000, poll_s=0,
                                          free_query=poll))
        never = gpu.wait_for_free(10000, poll_s=0, timeout_s=0.2,
                                  free_query=lambda: 100)
        self.assertFalse(never)

    def test_sampler_stop(self):
        with tempfile.TemporaryDirectory() as td, \
                gpu.start_sampler(os.path.join(td, "gpu-sample.log"), 3600) as s:
            pass
        self.assertIsNotNone(s.proc.poll())  # 退出即回收


class TestGpuQueries(unittest.TestCase):
    """真查询函数回归（假 nvidia-smi，按参数分派输出）。

    回归点：查询已带 `-i <gpu>`，输出只有该卡一行——若再按 gpu 下标取行，
    非 0 号卡必越界；进程表也必须按 `-i` 过滤到该卡。
    """
    FAKE: ClassVar[str] = (
        "#!/bin/sh\n"
        'case " $* " in\n'
        '  *--query-gpu*)\n'
        '    case " $* " in\n'
        '      *" -i 1 "*) echo 4321 ;;\n'
        '      *" -i 0 "*) echo 5100 ;;\n'
        '      *) echo 11111 ;;\n'
        '    esac ;;\n'
        '  *--query-compute-apps*)\n'
        '    case " $* " in\n'
        '      *" -i 1 "*) echo "42,proc-C,64" ;;\n'
        '      *" -i 0 "*) echo "7,proc-B,300"; echo "8,proc-B,200" ;;\n'
        '    esac ;;\n'
        "esac\n")

    def _with_fake(self, script=FAKE):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        smi = Path(td.name) / "nvidia-smi"
        smi.write_text(script, encoding="utf-8")
        smi.chmod(0o755)
        p = patch.dict(os.environ, {"PATH": f"{td.name}:{os.environ['PATH']}"})
        p.start()
        self.addCleanup(p.stop)

    def test_free_mib_any_gpu_index(self):
        self._with_fake()
        self.assertEqual(gpu.free_mib(0), 5100)
        self.assertEqual(gpu.free_mib(1), 4321)  # 回归：此前 IndexError

    def test_compute_apps_filtered_by_gpu(self):
        self._with_fake()
        self.assertEqual([a["pid"] for a in gpu.compute_apps(0)], ["7", "8"])
        self.assertEqual(gpu.compute_apps(1),
                         [{"pid": "42", "name": "proc-C", "mib": 64}])

    def test_free_mib_malformed_reading_loud(self):
        self._with_fake("#!/bin/sh\necho '[N/A]'\n")
        with self.assertRaises(RuntimeError):
            gpu.free_mib(2)

    def test_missing_binary_is_runtime_error(self):
        with patch.dict(os.environ, {"PATH": "/nonexistent-bin"}), \
                self.assertRaises(RuntimeError):
            gpu.free_mib(0)


if __name__ == "__main__":
    unittest.main()
