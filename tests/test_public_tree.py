# 公开树约定（对仓自身的门）。
#   包约定（两种模式都测）：
#     1. labkit/ 内零本机绝对路径
#     2. 文件读写显式 utf-8；子进程输出显式按 utf-8 解码
#     3. 包内模块只用标准库与自身
#   仓约定（只对源码树测）：
#     4. 本仓 Markdown 的相对链接都指向存在的文件
#     5. 模板目录里的文件集合与打包清单完全相等
#     6. pyproject 元数据（零运行时依赖、许可）
#     7. README 点名的 CLI 子命令与模块真实存在
import ast
import contextlib
import io
import re
import sys
import tomllib
import unittest
from pathlib import Path

import labkit
from labkit import proj
from tests.support import REPO, SOURCE_TREE

PKG = Path(labkit.__file__).resolve().parent
TEXT_EXT = {".py", ".md", ".example", ".toml", ".txt"}
_USER_ABS = re.compile(r"(?<![\w./-])/(?:home|Users)/[A-Za-z0-9._-]+")
STDLIB = set(sys.stdlib_module_names)
_BINARY_MODE = re.compile(r"""["'][rwax]*b["']""")


def _text_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and (p.suffix in TEXT_EXT or p.name == ".gitignore"):
            yield p


def _call_args(source: str, head: re.Pattern) -> list[str]:
    """取出 source 里每个 `head` 调用的实参文本（括号配平，可跨行）。"""
    args = []
    for m in head.finditer(source):
        depth, i = 0, m.end() - 1  # i 指向 "("
        while i < len(source):
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        args.append(source[m.end():i])
    return args


_CALL_PATHLIB = re.compile(r"\.(?:read_text|write_text)\(")
_CALL_OPEN = re.compile(r"(?<![\w.])open\(")          # 裸 open(，不含 Popen(
_CALL_RUN = re.compile(r"subprocess\.run\(")


class PackageConventions(unittest.TestCase):
    def sources(self) -> dict[Path, str]:
        return {p: p.read_text(encoding="utf-8") for p in PKG.glob("*.py")}

    def test_no_user_absolute_paths_in_package(self):
        bad: dict[str, list[int]] = {}
        for p in _text_files(PKG):
            for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if _USER_ABS.search(ln):
                    bad.setdefault(str(p.relative_to(PKG)), []).append(i)
        self.assertEqual(bad, {}, f"包内出现本机绝对路径：{bad}")

    def test_file_io_is_explicit_utf8(self):
        """回归：包内 read_text/write_text/open 曾用缺省编码——非 UTF-8 区域设置下
        读写含中文的文件会抛错或写成乱码。规则：文本 I/O 必带 encoding，否则必须是二进制模式。"""
        bad = []
        for p, src in self.sources().items():
            for args in _call_args(src, _CALL_PATHLIB):
                if "encoding" not in args:
                    bad.append(f"{p.name}: .read_text/.write_text({args.strip()[:50]})")
            for args in _call_args(src, _CALL_OPEN):
                if "encoding" not in args and not _BINARY_MODE.search(args):
                    bad.append(f"{p.name}: open({args.strip()[:50]})")
            for args in _call_args(src, _CALL_RUN):
                if "text=True" in args and "encoding" not in args:
                    bad.append(f"{p.name}: subprocess.run(text=True) 无 encoding")
        self.assertEqual(bad, [], "隐式编码的 I/O：")

    def test_package_is_stdlib_only(self):
        """包内 import 只许 stdlib 与 labkit 自身。"""
        foreign: dict[str, set[str]] = {}
        for p, src in self.sources().items():
            for node in ast.walk(ast.parse(src)):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    mods = [node.module]
                for m in mods:
                    top = m.split(".")[0]
                    if top not in STDLIB and top != "labkit":
                        foreign.setdefault(p.name, set()).add(top)
        self.assertEqual(foreign, {}, f"包内出现第三方/非 stdlib import：{foreign}")

    def test_cli_subcommands_exist(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                proj.main(["--help"])
            except SystemExit:
                pass
        for sub in ("new", "doctor", "wave", "close"):
            self.assertRegex(buf.getvalue(), rf"\b{sub}\b")


@unittest.skipUnless(SOURCE_TREE, "只对源码树测")
class RepositoryConventions(unittest.TestCase):
    def _pyproject(self) -> dict:
        with open(REPO / "pyproject.toml", "rb") as f:
            return tomllib.load(f)

    def test_pyproject_metadata(self):
        project = self._pyproject()["project"]
        self.assertEqual(project.get("dependencies", []), [])  # 零运行时依赖
        self.assertEqual(project["license"], "Apache-2.0")
        self.assertEqual(project["license-files"], ["LICENSE", "NOTICE"])
        self.assertEqual(project["name"], "ft-labkit")
        self.assertEqual(project["version"], labkit.__version__)
        self.assertIn("readme", project)

    def test_template_files_match_package_data_exactly(self):
        """回归：wheel 曾漏掉模板里的点目录文件（.agents/skills/PROJECT/SKILL.md）——
        glob 的 `**` 不进入点目录。故 package-data 逐文件显式列出，这里核对
        "模板目录里的文件集合"与"打包清单"完全相等：新增模板文件而忘登记即红。"""
        listed = set(self._pyproject()["tool"]["setuptools"]["package-data"]["labkit"])
        on_disk = {str(p.relative_to(PKG)) for p in (PKG / "templates").rglob("*")
                   if p.is_file()}
        self.assertEqual(sorted(on_disk - listed), [], "这些模板文件不在打包清单里，不会进 wheel")
        self.assertEqual(sorted(listed - on_disk), [], "打包清单里有不存在的文件")
        self.assertEqual(len(on_disk), 16)

    def test_readme_names_real_modules(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for mod in ("config", "gates", "evidence", "ckpt", "gpu", "augment", "proj"):
            self.assertTrue((REPO / "labkit" / f"{mod}.py").exists(), mod)
            self.assertIn(f"labkit.{mod}", readme, f"README 未列出 labkit.{mod}")

    def test_relative_markdown_links_resolve(self):
        """本仓 Markdown 的相对链接不得断（模板文件含占位符，另行由生成测试覆盖）。"""
        broken = []
        for p in sorted(REPO.rglob("*.md")):
            rel = p.relative_to(REPO)
            if rel.parts[:2] == ("labkit", "templates") or ".git" in rel.parts:
                continue
            for m in re.finditer(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", p.read_text(encoding="utf-8")):
                target = m.group(1).split("#", 1)[0]
                if not target or re.match(r"[a-z][a-z0-9+.-]*:", target):
                    continue  # 纯锚点、外部 URL、mailto
                if not (p.parent / target).exists():
                    broken.append(f"{rel}: {target}")
        self.assertEqual(broken, [], f"断链：{broken}")


if __name__ == "__main__":
    unittest.main()
