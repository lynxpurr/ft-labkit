# gpu — 预检门 / 计算进程表 / 等待-重试 / 后台采样器
# NEED 纪律：实测峰值 + 余量，不乐观估计（实录：余量只差几十 MiB，也会在首步 OOM）。
# 查询函数全部可注入（tests 不依赖真 GPU）。
from __future__ import annotations

import json
import shlex
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from ._io import out

GatesResult = dict  # {"gate": ..., "pass": ..., ...} JSON verdict


def _nvidia_smi(args: list[str], gpu: int | None = None) -> str:
    cmd = ["nvidia-smi"]
    if gpu is not None:
        cmd += ["-i", str(gpu)]
    try:
        result = subprocess.run([*cmd, *args], capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                timeout=15, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("nvidia-smi 不在 PATH（无 GPU 机器？）")
    except subprocess.TimeoutExpired:
        raise RuntimeError("nvidia-smi 超时（15s）")


def free_mib(gpu: int = 0) -> int:
    """指定 GPU 的 free 显存（MiB）。带 -i 查询，输出恰为该卡一行。"""
    result = _nvidia_smi(
        ["--query-gpu=memory.free", "--format=csv,noheader,nounits"], gpu)
    lines = result.splitlines()
    if not lines or not lines[0].strip().isdigit():
        raise RuntimeError(f"nvidia-smi free 读数异常：{result!r}")
    return int(lines[0])


def compute_apps(gpu: int = 0) -> list[dict]:
    """该 GPU 上的计算进程表（共享卡第三方进程是硬变量：会在训练中途上卡）。"""
    result = _nvidia_smi(
        ["--query-compute-apps=pid,process_name,used_memory",
         "--format=csv,noheader,nounits"], gpu)
    apps = []
    for ln in result.splitlines():
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) == 3:
            apps.append({"pid": parts[0], "name": parts[1], "mib": int(parts[2])})
    return apps


def precheck(
    need_mib: int,
    label: str = "",
    free_query: Callable[[], int] = free_mib,
    apps_query: Callable[[], list[dict]] = compute_apps,
) -> GatesResult:
    """GPU 预检门：free ≥ need 才放行；无论过否都打印进程表（双查——
    free 数字好但被第三方进程轮换抢卡的风险要看表）。"""
    try:
        free = free_query()
        apps = apps_query()
    except RuntimeError as e:
        v = {"gate": "gpu-precheck", "pass": False, "error": str(e), "label": label}
        out(json.dumps(v, ensure_ascii=False))
        return v
    ok = free >= need_mib
    v = {"gate": "gpu-precheck", "pass": ok, "label": label,
         "need_mib": need_mib, "free_mib": free,
         "compute_apps": apps,
         "hint": "" if ok else "不足：勿静默 OOM，等释放或处置第三方进程后重跑"}
    out(json.dumps(v, ensure_ascii=False))
    return v


def wait_for_free(
    need_mib: int,
    poll_s: int = 30,
    timeout_s: int | None = None,
    free_query: Callable[[], int] = free_mib,
) -> bool:
    """等待-重试循环。timeout 未到 free 返回 False 由调用方处置。"""
    deadline = time.time() + timeout_s if timeout_s else None
    while True:
        try:
            if free_query() >= need_mib:
                return True
        except RuntimeError:
            pass  # nvidia-smi 瞬态失败继续等
        if deadline and time.time() >= deadline:
            return False
        time.sleep(poll_s)


@dataclass
class Sampler:
    """后台显存采样器（while/sleep 30 → gpu-sample.log，trap kill 对应物）。

    with start_sampler(path) as s:  # 跑训练/推理
        ...
    # 退出时自动 kill；log 留在 out 目录作显存证据。
    """

    proc: subprocess.Popen
    log_path: str

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def start_sampler(log_path: str, interval_s: int = 30) -> Sampler:
    """起后台采样循环。采样器自己持有日志句柄的副本，本函数返回后父进程即可关闭自己那份。"""
    loop = (
        f"while :; do echo \"$(date +%T) free=$("
        f"nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits"
        f" | head -1)MiB\"; sleep {int(interval_s)}; done")
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(["bash", "-c", loop],
                                stdout=log, stderr=subprocess.DEVNULL)
    return Sampler(proc, log_path)


def quoted(cmd: list[str]) -> str:
    return " ".join(shlex.quote(c) for c in cmd)
