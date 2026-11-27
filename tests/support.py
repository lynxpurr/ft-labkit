# tests/support.py — 测试公共件：区分"对源码树测"与"对已安装的包测"
#
# 同一套测试跑两遍：仓根下直接跑是对源码树测；把 tests/ 拷到别处、在装好 ft-labkit 的
# 环境里跑，是对已安装的包测（模板必须随 wheel 走，就是靠这一遍钉住的）。
import os
import subprocess
from pathlib import Path

import labkit

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
# 被测的 labkit 就是源码树里那份 → "对源码树测"；否则 → "对已安装的包测"
SOURCE_TREE = Path(labkit.__file__).resolve().parent == REPO / "labkit"
# 两种模式下都成立的仓根：源码树模式下即 REPO
PKG = Path(labkit.__file__).resolve().parent


def sh(*cmd, cwd=None, env=None, path=None):
    """跑子命令并捕获输出（一律按 utf-8 解码，与区域设置无关）。

    env 给整份环境变量（不给则继承）；path 覆盖 PATH。
    源码树模式下把仓根放进 PYTHONPATH，子进程才 import 得到 labkit；
    已安装模式不加——确保子进程用的也是已安装的那份。
    """
    base = dict(os.environ) if env is None else dict(env)
    if path is not None:
        base["PATH"] = path
    if SOURCE_TREE:
        base["PYTHONPATH"] = os.pathsep.join(
            p for p in (str(REPO), base.get("PYTHONPATH")) if p)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          cwd=cwd, env=base, check=False)


def fake_exec(directory: Path, name: str, body: str) -> Path:
    """在 directory 下造一个可执行脚本。"""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path
