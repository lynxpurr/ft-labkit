# _io — 控制台输出的编码纪律
# 包内一切文件读写显式 utf-8；控制台输出在任何区域设置下都不因编码抛错。
# 缘由：提示语与 JSON verdict 的键含中文。区域设置不是 UTF-8 时（Windows 传统代码页、
# 被关闭 UTF-8 模式的 C 区域设置），往管道输出会抛 UnicodeEncodeError——命令做完了事，
# 却在最后一行打印上失败。
from __future__ import annotations

import sys


def utf8_stdio() -> None:
    """把非 UTF-8 的 stdout/stderr 文本流重设为 utf-8（不可编码的字符转义而非抛错）。

    只动"可重设且编码不是 UTF-8"的文本流：StringIO、测试捕获流原样不动。可重复调用。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if reconfigure is None or encoding in ("", "utf8"):
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (ValueError, OSError):  # 流已关闭或不可重设：保持原样
            pass


def out(text: str = "") -> None:
    """向 stdout 输出一行。"""
    utf8_stdio()
    print(text)


def err(text: str = "") -> None:
    """向 stderr 输出一行。"""
    utf8_stdio()
    print(text, file=sys.stderr)
