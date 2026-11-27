# evidence — 证据只增不改 / 按 generated 取最新 / 可再聚合 schema
# 三条纪律：
#  - 证据只增不改：写定即冻结，口径修订走 rejudge（只读重判、新旧并列）
#  - 不赌文件名字典序：`-`(0x2D) < `.`(0x2E) 曾让旧文件后写覆盖新键
#    → 聚合时按 generated 时间戳取最新
#  - 证据存"可再推导的原料"不存"加工后的结论"：逐条记录必须含可再聚合的
#    明细字段，事后分层才可行
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class EvidenceExistsError(FileExistsError):
    """产物已存在即拒绝写入——证据只增不改的门（调用方不捕获即大声失败）。"""


def write_new(path: str | Path, text: str) -> Path:
    """写定即冻结：目标已存在则拒写。文本一律按 utf-8 落盘（与区域设置无关）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        raise EvidenceExistsError(
            f"[evidence] {p} 已存在（证据只增不改；重判请走 rejudge 落新文件）")
    p.write_text(text, encoding="utf-8")
    return p


def write_new_json(path: str | Path, obj: Any) -> Path:
    return write_new(path, json.dumps(obj, ensure_ascii=False, indent=2))


def latest_by_key(
    entries: list[dict],
    key_fields: list[str],
    payload_get: str = "summary",
    generated_field: str = "generated",
) -> dict:
    """同键多份明细并存 → 按 generated 取最新。

    entries: 每条含 key_fields 各字段 + generated + payload（dict 或含 sub-keys）。
    返回 {key_tuple: payload}，key 为 "-" 连接的字符串便于直接落 markdown 表。
    """
    latest: dict = {}
    for e in entries:
        key = "-".join(str(e.get(k, "")) for k in key_fields)
        gen = e.get(generated_field, "")
        if key not in latest or gen > latest[key][0]:
            payload = e.get(payload_get)
            if isinstance(payload, dict):
                payload = dict(payload)
            latest[key] = (gen, payload)
    return {k: v[1] for k, v in latest.items()}


def ensure_detail_fields(
    records: list[dict], required: list[str], name: str = "records",
) -> None:
    """可再聚合 schema 门：每条明细必须带 required 字段，缺即大声失败。

    评测产物落盘前调用——保证产物事后可分层/再聚合（事后分层之所以可行，
    靠的是逐条记录里存了原始明细）。
    """
    missing = [
        {"i": i, "id": r.get("id", "?"),
         "missing": [k for k in required if k not in r]}
        for i, r in enumerate(records)
        if any(k not in r for k in required)
    ]
    if missing:
        raise AssertionError(
            f"[evidence] {name} 有 {len(missing)} 条缺明细字段（不可再聚合）: "
            + json.dumps(missing[:3], ensure_ascii=False))
