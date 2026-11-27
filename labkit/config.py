# config — labkit.toml + LABKIT_* 环境变量注入（去硬编码的统一解法）
# 约定：本包任何模块不得出现本机绝对路径；一律经 load() 返回的 Config。
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # python>=3.11 stdlib
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

DEFAULTS = {
    "engine": {"swift_bin": "", "train_python": "", "ref_python": ""},
    "models": {"dirs": []},
    "gpu": {"default_need_mib": 12000, "sample_interval_s": 30},
    "harness": {"reports_dir": "reports", "data_dir": "data", "output_dir": "output"},
    "paths": {},
}


@dataclass
class Config:
    swift_bin: str = ""
    train_python: str = ""
    ref_python: str = ""
    model_dirs: list[str] = field(default_factory=list)
    default_need_mib: int = 12000
    sample_interval_s: int = 30
    reports_dir: str = "reports"
    data_dir: str = "data"
    output_dir: str = "output"
    # 跨项目只读借用路径（自定义键值，如 solver = "/path/to/solver"）——
    # 项目脚本经 paths["<key>"] 取用，代码层零绝对路径。
    paths: dict[str, str] = field(default_factory=dict)

    def resolve_model(self, name: str) -> Path:
        """在 model_dirs 中按序查找模型目录，找不到大声失败。"""
        for d in self.model_dirs:
            cand = Path(d) / name
            if cand.is_dir():
                return cand
        raise FileNotFoundError(
            f"[config] 模型 {name} 不在候选目录 {self.model_dirs} 中"
            "（检查 labkit.toml [models].dirs）")


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _env_overrides(raw: dict) -> dict:
    """LABKIT_SWIFT_BIN / LABKIT_TRAIN_PYTHON / LABKIT_REF_PYTHON /
    LABKIT_MODEL_DIRS(冒号分隔) 覆盖文件值——CI 与临时换机用。"""
    env = os.environ
    if v := env.get("LABKIT_SWIFT_BIN"):
        raw["engine"]["swift_bin"] = v
    if v := env.get("LABKIT_TRAIN_PYTHON"):
        raw["engine"]["train_python"] = v
    if v := env.get("LABKIT_REF_PYTHON"):
        raw["engine"]["ref_python"] = v
    if v := env.get("LABKIT_MODEL_DIRS"):
        raw["models"]["dirs"] = [x for x in v.split(":") if x]
    return raw


def load(path: str | Path | None = None) -> Config:
    """读 labkit.toml（缺省从 CWD 向上找一层，再退 DEFAULTS）→ 环境变量覆盖。"""
    if path is None:
        cand = Path.cwd() / "labkit.toml"
        path = cand if cand.exists() else Path.cwd().parent / "labkit.toml"
    raw = json.loads(json.dumps(DEFAULTS))  # deep copy
    p = Path(path)
    if p.exists():
        if tomllib is None:  # pragma: no cover
            raise RuntimeError("python<3.11 无 tomllib，请升级或显式传配置")
        with open(p, "rb") as f:
            raw = _deep_merge(raw, tomllib.load(f))
    raw = _env_overrides(raw)
    return Config(
        swift_bin=raw["engine"]["swift_bin"],
        train_python=raw["engine"]["train_python"],
        ref_python=raw["engine"]["ref_python"],
        model_dirs=list(raw["models"]["dirs"]),
        default_need_mib=int(raw["gpu"]["default_need_mib"]),
        sample_interval_s=int(raw["gpu"]["sample_interval_s"]),
        reports_dir=raw["harness"]["reports_dir"],
        data_dir=raw["harness"]["data_dir"],
        output_dir=raw["harness"]["output_dir"],
        paths=dict(raw.get("paths", {})),
    )
