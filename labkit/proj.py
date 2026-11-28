# proj — labkit CLI：项目生命周期四命令
#   new     从内置模板开新项目仓（占位符替换 + git init）
#   doctor  环境五查：配置/载具/模型/GPU/labkit 可导入（+ 数据指纹）——JSON verdict，全绿才开工
#   wave    PLAN.md 生成波次条目 + 预注册 R# 模板 + reports/<id>/ 目录
#   close   波次收尾门：证据在/判决落表/lessons 批次/晋升记录/git 干净
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
from datetime import date
from importlib.resources import files
from pathlib import Path

from . import __version__, config, gates, gpu
from ._io import err, out, utf8_stdio

TEMPLATES = files(__package__).joinpath("templates")
TEMPLATE_DIR = TEMPLATES.joinpath("project")
EXAMPLE_TOML = TEMPLATES.joinpath("labkit.toml.example")
WAVE_MARKER = "<!-- labkit:wave-insert"
TODAY = date.today().isoformat()
# 项目名 = 仓目录名 = 仓内 skill 的目录名与 name。Agent Skills 开放标准要求 skill 的
# name 只含小写字母、数字与连字符，且与目录名一致——项目名同此规则，另限 1–64 字符。
PROJECT_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
PROJECT_NAME_MAX = 64
# 波次 id 进标题、reports/<id>/ 路径与正则：限定字符集，防路径穿越。
WAVE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# 指纹文件的一行（sha256sum 格式）：`<sha256 十六进制>` + 空格 + 文本/二进制标记 + `<相对路径>`
_SUMS_LINE = re.compile(r"^(?P<digest>[0-9a-fA-F]{64}) [ *](?P<name>.+)$")


def _valid_project_name(name: str) -> bool:
    return len(name) <= PROJECT_NAME_MAX and bool(PROJECT_NAME_RE.fullmatch(name))


# ---------------------------------------------------------------- new
def _template_files(root, parts=()):
    """递归枚举模板文件 → (目录分量, 文件)。走 importlib.resources，zip 安装同样可用。"""
    for entry in sorted(root.iterdir(), key=lambda e: e.name):
        if entry.is_dir():
            yield from _template_files(entry, (*parts, entry.name))
        else:
            yield parts, entry


def cmd_new(name: str, parent: Path) -> int:
    """内置模板 → <parent>/<name>/：{{PROJECT}}/{{DATE}} 替换、PROJECT 目录段改名、git init。"""
    if not _valid_project_name(name):
        err(f"[new] 非法项目名：{name!r}（1–64 个字符，只许小写字母、数字与单个连字符，"
            "首尾须为字母或数字——它同时是仓内 skill 的目录名与 name）")
        return 1
    dst = parent / name
    if dst.exists():
        err(f"[new] 目标已存在：{dst}")
        return 1
    if not TEMPLATE_DIR.is_dir():
        err(f"[new] 模板缺失：{TEMPLATE_DIR}"
            "（安装不完整？重装：pip install --force-reinstall ft-labkit）")
        return 1
    n_files = 0
    for parts, src in _template_files(TEMPLATE_DIR):
        rel = Path(*[name if p == "PROJECT" else p for p in parts], src.name)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        target.write_text(text.replace("{{PROJECT}}", name)
                          .replace("{{DATE}}", TODAY), encoding="utf-8")
        n_files += 1
    for d in ("reports", "research", "tests", "data", "notes"):
        (dst / d).mkdir(parents=True, exist_ok=True)
    # 数据指纹占位（有数据后 sha256sum 生成真值）
    sums = dst / "data" / "SHA256SUMS"
    if not sums.exists():
        sums.write_text("# 有数据后：cd data && sha256sum <文件>... > SHA256SUMS\n",
                        encoding="utf-8")
    # 本机实况配置：从样例拷一份，待填（含本机路径，已被模板 .gitignore 忽略）
    (dst / "labkit.toml").write_text(EXAMPLE_TOML.read_text(encoding="utf-8"),
                                      encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dst, check=True)
    out(f"[new] {name} ← 内置模板（{n_files} 文件）→ {dst}")
    out(f"[new] 下一步：cd {dst} && 编辑 CONSTITUTION.md 与 labkit.toml，然后 labkit doctor")
    return 0


# ---------------------------------------------------------------- doctor
def _resolve_exec(spec: str) -> Path | None:
    """可执行文件定位：路径直接认；裸命令名（如已激活 venv 里的 swift）按 PATH 查找。"""
    if not spec:
        return None
    path = Path(spec)
    if path.is_file():
        return path
    found = shutil.which(spec)
    return Path(found) if found else None


# 冒烟命令：ms-swift 的启动器把第一个参数当子命令名查表，没有 --version / -h / --help
# （都以 KeyError 退出 1）；`sft -h` 只读、不碰 GPU，1–2 秒返回（4.5.3 实测）。
_ENGINE_SMOKE_ARGS = ("sft", "-h")
_ENGINE_SMOKE_TIMEOUT = 60  # 秒；命令要加载训练框架，慢机器上留足余量


def _smoke_engine(engine: Path | None) -> bool:
    """引擎冒烟：真跑一次 `sft -h`，退出码 0 才算绿；失败时打一行可读的原因。

    只看"文件在位 + 可执行位"时，venv 里的入口脚本在底座解释器被系统升级抽走后
    仍然在位，一执行就 bad interpreter——门是绿的，训练起跑时才失败。冒烟把这种
    失败提前到 doctor。
    """
    if engine is None or not os.access(engine, os.X_OK):
        return False
    cmd = f"{engine} {' '.join(_ENGINE_SMOKE_ARGS)}"
    try:
        r = subprocess.run([str(engine), *_ENGINE_SMOKE_ARGS], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=_ENGINE_SMOKE_TIMEOUT,
                           check=False)
    except subprocess.TimeoutExpired:
        out(f"[doctor] engine: {cmd} 超过 {_ENGINE_SMOKE_TIMEOUT} 秒未返回")
        return False
    except OSError as e:
        out(f"[doctor] engine: {engine} 无法执行（{e.strerror or e}）——文件在位却起不来："
            "入口脚本指向的解释器多半已不在（bad interpreter）")
        return False
    if r.returncode != 0:
        lines = (r.stderr or r.stdout).strip().splitlines()
        out(f"[doctor] engine: {cmd} 退出码 {r.returncode}"
            + (f"；输出末行：{lines[-1][:200]}" if lines else ""))
        return False
    return True


def _probe_labkit_import(interp: str) -> bool:
    """探指定解释器能否 import labkit，并回报它导入的是哪一份。

    venv 解释器跑子进程脚本而 labkit 不可导入时，此前只会在跑到一半静默失败；
    本门把"跑中静默失败"提前为"起跑前可见读数"。导入了**另一份**同名包
    （PYTHONPATH 或另一处安装遮蔽了预期的那份）同属静默失败，故一并回报路径。
    """
    located = _resolve_exec(interp) if interp else None
    if not located:
        return True  # 未配置/不在位不计门（在位性归 doctor/engine）
    r = subprocess.run([str(located), "-c", "import labkit; print(labkit.__file__)"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, check=False)
    if r.returncode != 0:
        out(f"[doctor] labkit_import: {interp} 无法 import labkit——其上的内嵌/子进程"
            "脚本会静默失败；修法：pip install -e <labkit 仓> 或 export PYTHONPATH=<labkit 仓>")
        return False
    printed = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    here = Path(__file__).resolve().parent
    if printed:
        imported = Path(printed[-1]).resolve().parent
        if imported != here:
            out(f"[doctor] labkit_import: {interp} 导入的是另一份 labkit：{imported}"
                f"（当前运行的是 {here}）——同名包遮蔽，检查 PYTHONPATH 与 pip 安装来源")
    return True


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sums(sums: str | Path) -> tuple[bool, list[str]]:
    """校验指纹文件（sha256sum 格式：每行 `<sha256>  <相对路径>`，路径相对指纹文件所在目录）。

    返回 (是否登记了条目且全过, 失败明细)。纯 Python 实现，不依赖 sha256sum 命令
    （macOS 与 Windows 上没有它）。登记了但缺文件、指纹不符、格式错的行都算失败。
    """
    sums = Path(sums)
    failures: list[str] = []
    n = 0
    for raw in sums.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _SUMS_LINE.match(line)
        if not m:
            failures.append(f"格式错：{line[:60]}")
            continue
        n += 1
        name = m.group("name").strip()
        target = sums.parent / name
        if not target.is_file():
            failures.append(f"缺文件：{name}")
        elif _sha256_of(target) != m.group("digest").lower():
            failures.append(f"指纹不符：{name}")
    return n > 0 and not failures, failures


def cmd_doctor() -> int:
    """环境五查（在项目根跑；无 labkit.toml 时按缺省+环境变量）。"""
    results = []
    cfg = config.load()
    results.append(gates.checks_gate(
        {"配置文件": Path("labkit.toml").is_file()}, name="doctor/config"))
    engine = _resolve_exec(cfg.swift_bin)
    train_py = _resolve_exec(cfg.train_python) if cfg.train_python else None
    results.append(gates.checks_gate(
        {"引擎 sft -h 退出码 0": _smoke_engine(engine),
         "训练解释器在位": not cfg.train_python or train_py is not None},
        name="doctor/engine"))
    existing = [d for d in cfg.model_dirs if Path(d).is_dir()]
    results.append(gates.checks_gate(
        {"模型目录 ≥1": bool(cfg.model_dirs) and bool(existing)},
        name="doctor/models"))
    results.append(gates.checks_gate(
        {"GPU 可查": bool(gpu.precheck(0)["pass"])}, name="doctor/gpu"))
    results.append(gates.checks_gate(
        {"train_python 可 import labkit": _probe_labkit_import(cfg.train_python),
         "ref_python 可 import labkit": _probe_labkit_import(cfg.ref_python)},
        name="doctor/labkit_import"))
    sums = Path("data") / "SHA256SUMS"
    if sums.is_file():
        ok, failures = verify_sums(sums)
        if not failures and not ok:
            out("[doctor] data: SHA256SUMS 未登记条目（新仓，占位注释）——"
                "有数据后生成真值，暂不计门")
        elif failures:
            # 文件参数与 cwd 必须同基准——双重前缀会让真实条目必红
            # （新仓只走"占位不计门"分支时，这条绿路径从未被测过）。
            out(f"[doctor] data: 指纹校验失败 {len(failures)} 项：" + "；".join(failures[:5]))
            results.append(gates.checks_gate({"数据指纹全过": False}, name="doctor/data"))
        else:
            results.append(gates.checks_gate({"数据指纹全过": True}, name="doctor/data"))
    for d in existing:
        out(f"[doctor] model_dir: {d}")
    return gates.run_gates(results)


# ---------------------------------------------------------------- wave
WAVE_BLOCKS = {
    "zh": """### {wid} {name} —— pending {today}
- 动作形态：（数据/训练/评测形态一句话）
- 预注册：**R-{wid}** <主判据：量化判据 + 测量口径> + 护栏（<不回退轴及阈值>）
  - 过 → <下一步>
  - 不过 → <下一步（含诚实停止分支）>
- 判决落表（跑后回填）：待填（中/不中 + 读数 + 指针）
""",
    "en": """### {wid} {name} —— pending {today}
- Action: (one line: the data / training / evaluation setup)
- Pre-registration: **R-{wid}** <primary criterion: quantified metric + measurement protocol> + guardrails (<non-regression axes and thresholds>)
  - pass → <next step>
  - fail → <next step (including the honest-stop branch)>
- Verdict (fill in after the run): TBD (pass/fail + readings + pointers)
""",
}


def cmd_wave(wid: str, name: str, lang: str = "zh") -> int:
    if lang not in WAVE_BLOCKS:
        err(f"[wave] 未知语言：{lang}（可选 {'/'.join(sorted(WAVE_BLOCKS))}）")
        return 1
    if not WAVE_ID_RE.fullmatch(wid):
        err(f"[wave] 非法波次 id：{wid!r}（只许字母数字与 . _ -，且以字母数字开头）")
        return 1
    plan = Path("PLAN.md")
    if not plan.is_file():
        err("[wave] 不在项目根（无 PLAN.md）")
        return 1
    text = plan.read_text(encoding="utf-8")
    if WAVE_MARKER not in text:
        err("[wave] PLAN.md 缺 wave-insert 标记（勿删模板标记行）")
        return 1
    if re.search(rf"^### {re.escape(wid)}\b", text, re.MULTILINE):
        err(f"[wave] 波次 {wid} 已存在")
        return 1
    block = WAVE_BLOCKS[lang].format(wid=wid, name=name, today=TODAY)
    head, _, tail = text.partition(WAVE_MARKER)
    plan.write_text(head + block + "\n" + _ + tail, encoding="utf-8")
    rep = Path("reports") / wid
    rep.mkdir(parents=True, exist_ok=True)
    out(f"[wave] {wid} {name}：预注册模板已入 PLAN §4，证据目录 {rep}/")
    out("[wave] 判决规则填写后才许跑实验（预注册纪律）")
    return 0


# ---------------------------------------------------------------- close
# close 门认的关键词：治理模板用中文或英文书写都可以，两种都认。
_VERDICT_FILLED = (
    re.compile(r"判决落表[^\n]*：\s*(中|不中)"),          # 判决词紧跟冒号（占位态不匹配）
    re.compile(r"[Vv]erdict[^\n]*:\s*(pass|fail|hit|miss)\b"),
)
_PLACEHOLDER_LEFT = ("待填", "TBD")
_PROMOTION_LINE = re.compile(r"晋升记录|[Pp]romotion")
# 一个批次：行首的二级标题到下一个行首二级标题之前。必须锚定行首——否则说明文字里
# 引用的示例 "`## YYYY-MM-DD · XX批`" 也会被当成批次的开始。
_BATCH_HEADING = re.compile(r"^## [^\n]*\n(?:(?!^## ).)*", re.MULTILINE | re.DOTALL)


def _squash_lines(text: str) -> str:
    return "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())


def _template_lessons_batch() -> str | None:
    """模板自带的占位批次按今日日期渲染后的样子（模板读不到时返回 None，门退回不比占位）。"""
    try:
        text = TEMPLATE_DIR.joinpath("notes", "lessons.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    m = _BATCH_HEADING.search(text.replace("{{DATE}}", TODAY))
    return m.group(0) if m else None


def _wave_section(text: str, wid: str) -> str | None:
    m = re.search(rf"^### {re.escape(wid)}\b.*?(?=^### |\Z)", text,
                  re.MULTILINE | re.DOTALL)
    return m.group(0) if m else None


def cmd_close(wid: str, allow_dirty: bool = False) -> int:
    if not WAVE_ID_RE.fullmatch(wid):
        err(f"[close] 非法波次 id：{wid!r}")
        return 1
    plan = Path("PLAN.md")
    if not plan.is_file():
        err("[close] 不在项目根（无 PLAN.md）")
        return 1
    section = _wave_section(plan.read_text(encoding="utf-8"), wid)
    rep = Path("reports") / wid
    lessons = Path("notes") / "lessons.md"
    lessons_text = lessons.read_text(encoding="utf-8") if lessons.is_file() else ""

    def _verdict_filled(s: str) -> bool:
        # 口径：判决行冒号后紧跟判决词（模板行冒号后是占位词→不匹配），
        # 且全节无残留占位。
        return (any(rx.search(s) for rx in _VERDICT_FILLED)
                and not any(ph in s for ph in _PLACEHOLDER_LEFT))

    batches = _BATCH_HEADING.findall(lessons_text)
    latest = batches[-1] if batches else ""
    # 模板自带的占位批次带建仓当日日期和一行"晋升记录：无"，一条教训都没写时也能让下面
    # 两道检查通过（纸门）。最新一批与模板原样渲染的一字不差，就按占位态判红。
    placeholder = _template_lessons_batch()
    only_placeholder = bool(latest) and placeholder is not None \
        and _squash_lines(latest) == _squash_lines(placeholder)
    # 最新批次须带"晋升记录"行（含"无（首现，留观）"也算——纪律是显式决策）
    promotion_line = bool(_PROMOTION_LINE.search(latest)) and not only_placeholder

    def _git_clean() -> bool:
        r = subprocess.run(["git", "status", "--porcelain"],
                           capture_output=True, text=True, encoding="utf-8",
                           check=False)
        return r.returncode == 0 and not r.stdout.strip()

    checks = {
        "波次条目在": section is not None,
        "证据目录非空": rep.is_dir() and any(rep.iterdir()),
        "判决已落表": bool(section) and _verdict_filled(section),
        "lessons 今日批次": bool(lessons_text) and TODAY in lessons_text and not only_placeholder,
        "晋升记录行": promotion_line,
        "git 工作区干净": allow_dirty or _git_clean(),
    }
    if only_placeholder:
        out("[close] notes/lessons.md 最新一批仍是模板自带的占位批次：本波教训未落账——"
            "追加今日批次并写晋升记录（无晋升也要写明）")
    rc = gates.run_gates([gates.checks_gate(checks, name=f"close/{wid}")])
    if rc == 0:
        out(f"[close] {wid} 收尾通过：判决/证据/沉淀齐备")
    else:
        out(f"[close] {wid} 未过：按上方失败项补齐后重跑（不许带病翻篇）")
    return rc


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()  # 先把控制台输出调到不会因编码抛错（见 _io）
    ap = argparse.ArgumentParser(
        prog="labkit",
        description="labkit — 微调项目脚手架 CLI（new/doctor/wave/close）")
    # --version 自己打印：argparse 的 version 动作会按终端宽度折行，装进 site-packages 后
    # 路径变长就会被折成两行，调用方拿不到完整路径。
    ap.add_argument("--version", action="store_true",
                    help="显示版本与实际运行的那份 labkit 的路径")
    sub = ap.add_subparsers(dest="cmd")  # 不设 required：--version 单独出现时没有子命令
    p_new = sub.add_parser("new", help="从内置模板开新项目仓")
    p_new.add_argument("name")
    p_new.add_argument("--parent", type=Path, default=Path.cwd(),
                       help="新仓的父目录（缺省当前目录）")
    sub.add_parser("doctor", help="环境五查（项目根下运行）")
    p_wave = sub.add_parser("wave", help="开波：预注册模板入 PLAN")
    p_wave.add_argument("wid"), p_wave.add_argument("name")
    p_wave.add_argument("--lang", choices=sorted(WAVE_BLOCKS), default="zh",
                        help="预注册模板的语言 / language of the inserted block")
    p_close = sub.add_parser("close", help="波次收尾门")
    p_close.add_argument("wid")
    p_close.add_argument("--allow-dirty", action="store_true",
                         help="跳过 git 干净检查（如收尾提交前先验其余项）")
    args = ap.parse_args(argv)
    if args.version:
        if args.cmd is not None:
            ap.error("--version 不能与子命令同用")
        out(f"ft-labkit {__version__} ({Path(__file__).resolve().parent})")
        return 0
    if args.cmd is None:
        ap.error("the following arguments are required: cmd")
    if args.cmd == "new":
        return cmd_new(args.name, args.parent)
    if args.cmd == "doctor":
        return cmd_doctor()
    if args.cmd == "wave":
        return cmd_wave(args.wid, args.name, args.lang)
    return cmd_close(args.wid, args.allow_dirty)


if __name__ == "__main__":
    raise SystemExit(main())
