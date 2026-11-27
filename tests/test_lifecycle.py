# proj 单测：生命周期 new → doctor → wave → close，在临时沙箱里跑。
# 纪律：每道门都要有"占位/缺项形态必须红、真实形态必须绿"的两侧对照。
import contextlib
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import labkit
from labkit import proj
from tests.support import PKG, SOURCE_TREE, fake_exec, sh

TEMPLATE = PKG / "templates" / "project"

# 新仓必须带齐的文件（内置模板的清单）
EXPECTED_FILES = (
    "CONSTITUTION.md", "PLAN.md", "HANDOFF.md", "SPEC-INDEX.md",
    "AGENTS.md", "README.md", "notes/lessons.md", "notes/playbook.md",
    "notes/map.md", "data/PROVENANCE.md", "tools/README.md",
    ".gitignore", "labkit.toml", "data/SHA256SUMS",
    ".agents/skills/demo-lab/SKILL.md",
)
GITIGNORE_MUST = {"output/", ".venv*/", "__pycache__/", "*.pyc",
                  ".pytest_cache/", "*.egg-info/", "labkit.toml"}
# 非 UTF-8 的运行环境：C 区域设置，并关掉 Python 的两道自动兜底（区域设置强制、UTF-8 模式）
ASCII_ENV = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}


def _patterns(text: str) -> set[str]:
    return {ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")}


def _quiet(fn, *a, **kw):
    """进程内调 CLI 函数时收掉人读提示（门的信息由测试断言）。"""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.sandbox, ignore_errors=True)
        self.proj_dir = self.sandbox / "demo-lab"

    def _new(self, parent=None):
        return _quiet(proj.cmd_new, "demo-lab", parent or self.sandbox)

    def _fake_exec(self, name: str, body: str) -> Path:
        return fake_exec(self.sandbox, name, body)

    def _write_config(self):
        # 载具/模型检查的通过配置（假路径只要存在+可执行）
        swift = self._fake_exec("swift", "#!/bin/sh\n")
        models = self.sandbox / "models"
        models.mkdir(exist_ok=True)
        (self.proj_dir / "labkit.toml").write_text(
            f'[engine]\nswift_bin = "{swift}"\ntrain_python = ""\n'
            f'[models]\ndirs = ["{models}"]\n', encoding="utf-8")

    def _git(self, *args):
        return sh("git", "-c", "user.name=t", "-c", "user.email=t@t",
                  *args, cwd=self.proj_dir)

    def _register(self, name: str, content: bytes) -> str:
        """往新仓 data/ 登记一个数据文件的指纹，返回 sha256。"""
        digest = hashlib.sha256(content).hexdigest()
        (self.proj_dir / "data" / name).write_bytes(content)
        sums = self.proj_dir / "data" / "SHA256SUMS"
        with open(sums, "a", encoding="utf-8") as f:
            f.write(f"{digest}  {name}\n")
        return digest

    # ------------------------------------------------------------ new
    def test_new_generates_project(self):
        self.assertEqual(self._new(), 0)
        for f in EXPECTED_FILES:
            self.assertTrue((self.proj_dir / f).exists(), f"缺 {f}")
        # 占位符全部替换
        for f in ("PLAN.md", "README.md", ".agents/skills/demo-lab/SKILL.md"):
            text = (self.proj_dir / f).read_text(encoding="utf-8")
            self.assertNotIn("{{PROJECT}}", text, f)
            self.assertNotIn("{{DATE}}", text, f)
        skill = (self.proj_dir / ".agents/skills/demo-lab/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: demo-lab", skill)  # PROJECT 目录段与 frontmatter 同步改名
        self.assertFalse((self.proj_dir / ".agents/skills/PROJECT").exists())
        plan = (self.proj_dir / "PLAN.md").read_text(encoding="utf-8")
        self.assertIn(proj.WAVE_MARKER, plan)
        self.assertTrue((self.proj_dir / ".git").is_dir())  # git init 过
        self.assertTrue((self.proj_dir / "reports").is_dir())

    def test_new_refuses_existing(self):
        self._new()
        self.assertEqual(self._new(), 1)  # 目标已存在拒建

    def test_new_rejects_nonconforming_names(self):
        """项目名同时是仓内 skill 的目录名与 name，故只许小写字母、数字与连字符。"""
        bad = ("../evil", "a/b", ".hidden", "a b", "", "Demo", "my_project",
               "demo.lab", "-lead", "trail-", "a--b", "x" * 65)
        for name in bad:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(proj.cmd_new(name, self.sandbox), 1, name)
        self.assertEqual(sorted(p.name for p in self.sandbox.iterdir()), [])
        for good in ("a", "p1", "demo-lab", "x" * 64):
            self.assertEqual(_quiet(proj.cmd_new, good, self.sandbox), 0, good)

    def test_new_default_parent_is_cwd(self):
        work = self.sandbox / "work"
        work.mkdir()
        r = sh(sys.executable, "-m", "labkit", "new", "demo-lab", cwd=work)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((work / "demo-lab" / "PLAN.md").exists())

    def test_new_project_carries_gitignore(self):
        """新仓第一天起权重类产物不入库；reports/ 是证据，不得被忽略。"""
        self.assertEqual(self._new(), 0)
        gi = self.proj_dir / ".gitignore"
        self.assertTrue(gi.exists(), "labkit new 产物缺 .gitignore")
        pats = _patterns(gi.read_text(encoding="utf-8"))
        self.assertTrue(GITIGNORE_MUST <= pats, f"缺模式：{GITIGNORE_MUST - pats}")
        self.assertFalse([p for p in pats if "reports" in p],
                         f".gitignore 不得忽略 reports/（证据纪律）：{pats}")
        # 负向对照：labkit.toml（含本机路径）被忽略，PLAN.md 不被忽略
        self.assertEqual(sh("git", "check-ignore", "-q", "labkit.toml",
                            cwd=self.proj_dir).returncode, 0)
        self.assertEqual(sh("git", "check-ignore", "-q", "PLAN.md",
                            cwd=self.proj_dir).returncode, 1)

    # ------------------------------------------------------------ doctor
    def test_doctor_data_gate_real_entries(self):
        """数据门对"真实登记条目"的两侧对照：真值绿 / 篡改红。
        （回归：文件参数与 cwd 双重前缀曾让真实条目必红，而新仓只走
        "占位不计门"分支，这条绿路径此前从未被测过。）"""
        self._new()
        self._write_config()
        self._register("train.jsonl", b'{"a":1}\n')
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir)
        self.assertIn('"doctor/data", "pass": true', r.stdout)
        # 篡改后必须红
        (self.proj_dir / "data" / "train.jsonl").write_bytes(b'{"a":2}\n')
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir)
        self.assertIn('"doctor/data", "pass": false', r.stdout)
        self.assertIn("指纹不符：train.jsonl", r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_doctor_data_gate_needs_no_sha256sum_binary(self):
        """回归：指纹校验曾靠 shell 出去调 sha256sum——macOS/Windows 上没有这个命令。"""
        self._new()
        self._write_config()
        self._register("train.jsonl", b'{"a":1}\n')
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir,
               path="/nonexistent-bin")
        self.assertIn('"doctor/data", "pass": true', r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_verify_sums_formats(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.bin").write_bytes(b"alpha")
            (d / "b.txt").write_bytes(b"beta")
            good_a = hashlib.sha256(b"alpha").hexdigest()
            good_b = hashlib.sha256(b"beta").hexdigest()
            text = ("# 注释行不计\n\n"
                    f"{good_a} *a.bin\n"        # sha256sum 二进制模式标记
                    f"{good_b}  b.txt\n")       # 文本模式：两个空格
            (d / "SHA256SUMS").write_text(text, encoding="utf-8")
            self.assertEqual(proj.verify_sums(d / "SHA256SUMS"), (True, []))
            (d / "SHA256SUMS").write_text("# 只有占位注释\n", encoding="utf-8")
            self.assertEqual(proj.verify_sums(d / "SHA256SUMS"), (False, []))  # 未登记
            (d / "SHA256SUMS").write_text(f"{good_a}  missing.bin\n", encoding="utf-8")
            self.assertEqual(proj.verify_sums(d / "SHA256SUMS")[1], ["缺文件：missing.bin"])
            (d / "SHA256SUMS").write_text(f"{'0' * 64}  a.bin\n", encoding="utf-8")
            self.assertEqual(proj.verify_sums(d / "SHA256SUMS")[1], ["指纹不符：a.bin"])
            (d / "SHA256SUMS").write_text("not-a-sum-line\n", encoding="utf-8")
            self.assertEqual(proj.verify_sums(d / "SHA256SUMS")[1], ["格式错：not-a-sum-line"])

    def test_doctor_pass_with_config(self):
        self._new()
        self._write_config()
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir)
        # 无 GPU 的 CI 沙箱：gpu 门红属如实读数；此处断言配置/载具/模型三门全过。
        for gate in ("doctor/config", "doctor/engine", "doctor/models"):
            verdict = [ln for ln in r.stdout.splitlines() if f'"{gate}"' in ln]
            self.assertTrue(verdict, f"缺 {gate} verdict")
            self.assertIn('"pass": true', verdict[0], f"{gate} 未过：{verdict[0]}")
        self.assertTrue([ln for ln in r.stdout.splitlines() if '"doctor/gpu"' in ln])

    def test_doctor_red_without_config(self):
        """负向对照：样例配置未填（路径不存在）→ 载具门红，不许假绿。"""
        self.assertEqual(self._new(), 0)
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir)
        self.assertIn('"doctor/engine", "pass": false', r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_doctor_engine_resolved_on_path(self):
        """配置里写裸命令名（如已激活 venv 里的 swift）时按 PATH 找，不强制绝对路径。"""
        self._new()
        fake = self._fake_exec("swift", "#!/bin/sh\n")
        (self.proj_dir / "labkit.toml").write_text(
            '[engine]\nswift_bin = "swift"\n', encoding="utf-8")
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir,
               path=f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
        self.assertIn('"doctor/engine", "pass": true', r.stdout)
        # 负向对照：PATH 上没有它 → 红
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir,
               path="/nonexistent-bin")
        self.assertIn('"doctor/engine", "pass": false', r.stdout)

    def test_doctor_import_gate_mixed_readings(self):
        """train 绿 + ref 红 → 门红且子读数逐项如实，修法提示可见。"""
        ok = self._fake_exec("py_ok", "#!/bin/sh\nexit 0\n")
        bad = self._fake_exec("py_bad", "#!/bin/sh\nexit 1\n")
        self._new()
        (self.proj_dir / "labkit.toml").write_text(
            f'[engine]\nswift_bin = "{ok}"\ntrain_python = "{ok}"\n'
            f'ref_python = "{bad}"\n', encoding="utf-8")
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir)
        self.assertIn('"doctor/labkit_import", "pass": false', r.stdout)
        self.assertIn('"train_python 可 import labkit": true', r.stdout)
        self.assertIn('"ref_python 可 import labkit": false', r.stdout)
        self.assertIn("PYTHONPATH", r.stdout)  # 修法提示在输出里

    def test_doctor_import_gate_green(self):
        ok = self._fake_exec("py_ok", "#!/bin/sh\nexit 0\n")
        self._new()
        (self.proj_dir / "labkit.toml").write_text(
            f'[engine]\nswift_bin = "{ok}"\ntrain_python = "{ok}"\n'
            f'ref_python = "{ok}"\n', encoding="utf-8")
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir)
        self.assertIn('"doctor/labkit_import", "pass": true', r.stdout)
        self.assertNotIn("另一份 labkit", r.stdout)

    def test_doctor_import_probe_reports_shadowing(self):
        """导入了另一份同名包：import 成功不算失败，但必须把"是哪一份"喊出来——
        同名包遮蔽是静默失败（两份 labkit 并存时，命令跑的是另一份的模板与门）。"""
        other = self._fake_exec("py_other", '#!/bin/sh\necho "/somewhere/else/labkit/__init__.py"\n')
        self._new()
        (self.proj_dir / "labkit.toml").write_text(
            f'[engine]\nswift_bin = "{other}"\ntrain_python = "{other}"\n',
            encoding="utf-8")
        r = sh(sys.executable, "-m", "labkit", "doctor", cwd=self.proj_dir)
        self.assertIn('"doctor/labkit_import", "pass": true', r.stdout)
        self.assertIn("另一份 labkit", r.stdout)
        self.assertIn("/somewhere/else/labkit", r.stdout)

    # ------------------------------------------------------------ wave / close
    def _wave(self, *extra):
        return sh(sys.executable, "-m", "labkit", "wave", "W1", "baseline",
                  *extra, cwd=self.proj_dir)

    def test_wave_and_close_cycle(self):
        self._new()
        self._write_config()
        r = self._wave()
        self.assertEqual(r.returncode, 0)
        plan = (self.proj_dir / "PLAN.md").read_text(encoding="utf-8")
        self.assertIn("### W1 baseline", plan)
        self.assertIn("R-W1", plan)                    # 预注册编号
        self.assertIn("过 →", plan)                    # 双向枚举
        self.assertIn("不过 →", plan)
        self.assertTrue((self.proj_dir / "reports" / "W1").is_dir())
        # 重复 wave 同 id 拒
        r = sh(sys.executable, "-m", "labkit", "wave", "W1", "again",
               cwd=self.proj_dir)
        self.assertEqual(r.returncode, 1)

        # close：缺项（证据空/判决待填/无 lessons 批/无晋升行/git 脏）→ 必红
        r = sh(sys.executable, "-m", "labkit", "close", "W1", cwd=self.proj_dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn('"证据目录非空": false', r.stdout)
        self.assertIn('"判决已落表": false', r.stdout)
        self.assertIn('"git 工作区干净": false', r.stdout)

        # 补齐全部项 → close 过
        (self.proj_dir / "reports" / "W1" / "evidence.json").write_text("{}", encoding="utf-8")
        plan = re.sub(r"- 判决落表[^\n]*",
                      "- 判决落表（跑后回填）：中（读数 5/8 ≥ 阈值；指针 reports/W1/）",
                      plan, count=1)
        (self.proj_dir / "PLAN.md").write_text(plan, encoding="utf-8")
        lessons = self.proj_dir / "notes" / "lessons.md"
        lessons.write_text(lessons.read_text(encoding="utf-8") + f"""
## {proj.TODAY} · 02批（W1 收尾）
- 例行落账。

晋升记录：无（首现，留观）
""", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "w1")
        r = sh(sys.executable, "-m", "labkit", "close", "W1", cwd=self.proj_dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_close_placeholder_disguised_as_verdict_red(self):
        """负向对照：占位行本身含"中/不中"字样，不得被当成已落表。"""
        self._new()
        self.assertEqual(self._wave().returncode, 0)
        (self.proj_dir / "reports" / "W1" / "evidence.json").write_text("{}", encoding="utf-8")
        lessons = self.proj_dir / "notes" / "lessons.md"
        lessons.write_text(lessons.read_text(encoding="utf-8") +
                           f"\n## {proj.TODAY} · 02批\n- x\n晋升记录：无\n",
                           encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "wip")
        r = sh(sys.executable, "-m", "labkit", "close", "W1", cwd=self.proj_dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn('"判决已落表": false', r.stdout)  # 模板占位行仍在

    def _close_ready(self) -> None:
        """把除 lessons 之外的收尾项全部补齐：证据、判决、提交。"""
        (self.proj_dir / "reports" / "W1" / "evidence.json").write_text("{}", encoding="utf-8")
        plan_path = self.proj_dir / "PLAN.md"
        plan_path.write_text(re.sub(r"- 判决落表[^\n]*", "- 判决落表（跑后回填）：中（读数 5/8）",
                                    plan_path.read_text(encoding="utf-8"), count=1),
                             encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "w1")

    def test_close_template_placeholder_lessons_is_red(self):
        """阴性对照（纸门）：模板自带的占位批次带建仓当日日期和一行"晋升记录：无"，
        曾让"lessons 今日批次"与"晋升记录行"在一条教训都没写时就通过。"""
        self._new()
        self.assertEqual(self._wave().returncode, 0)
        self._close_ready()
        r = sh(sys.executable, "-m", "labkit", "close", "W1", cwd=self.proj_dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn('"lessons 今日批次": false', r.stdout)
        self.assertIn('"晋升记录行": false', r.stdout)
        self.assertIn("占位批次", r.stdout)
        # 真实落账：在占位批次之后追加一批 → 绿
        lessons = self.proj_dir / "notes" / "lessons.md"
        lessons.write_text(lessons.read_text(encoding="utf-8")
                           + f"\n## {proj.TODAY} · 02批（W1）\n- 教训一。\n\n晋升记录：无（首现，留观）\n",
                           encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "lessons")
        r = sh(sys.executable, "-m", "labkit", "close", "W1", cwd=self.proj_dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_close_edited_first_batch_counts(self):
        """就地改写第一批（把占位示例行换成真实教训）也算落账——占位态与真实态两侧都踩过。"""
        self._new()
        self.assertEqual(self._wave().returncode, 0)
        self._close_ready()
        lessons = self.proj_dir / "notes" / "lessons.md"
        lessons.write_text(lessons.read_text(encoding="utf-8").replace(
            "- 建仓即跑 labkit doctor，全绿才开工（占位示例行，可删）。",
            "- 本波教训：评测器自检门先于一切。"), encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "lessons")
        r = sh(sys.executable, "-m", "labkit", "close", "W1", cwd=self.proj_dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_wave_close_cycle_en(self):
        """英文预注册模板：同一道 close 门都要认。"""
        self._new()
        r = self._wave("--lang", "en")
        self.assertEqual(r.returncode, 0)
        plan_path = self.proj_dir / "PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        self.assertIn("pass →", plan)
        self.assertIn("fail →", plan)
        self.assertNotIn("判决落表", plan)
        (self.proj_dir / "reports" / "W1" / "evidence.json").write_text("{}", encoding="utf-8")
        (self.proj_dir / "notes" / "lessons.md").write_text(
            f"# Lessons\n\n## {proj.TODAY} · batch 02\n- routine.\n\n"
            "Promotion: none (first occurrence, watch)\n", encoding="utf-8")
        # 占位态 → 红
        r = sh(sys.executable, "-m", "labkit", "close", "W1", "--allow-dirty",
               cwd=self.proj_dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn('"判决已落表": false', r.stdout)
        self.assertIn('"晋升记录行": true', r.stdout)
        # 真实判决 → 绿
        plan = re.sub(r"- Verdict[^\n]*",
                      "- Verdict (after the run): pass (5/8 >= threshold; reports/W1/)",
                      plan, count=1)
        plan_path.write_text(plan, encoding="utf-8")
        r = sh(sys.executable, "-m", "labkit", "close", "W1", "--allow-dirty",
               cwd=self.proj_dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_wave_rejects_bad_input(self):
        self._new()
        for args, rc in ((["wave", "../x", "y"], 1),        # 路径穿越
                         (["wave", "a b", "y"], 1),          # 空格
                         (["wave", "W1", "y", "--lang", "fr"], 2),  # argparse 用法错
                         (["close", "../x"], 1)):            # close 同样校验波次 id
            r = sh(sys.executable, "-m", "labkit", *args, cwd=self.proj_dir)
            self.assertEqual(r.returncode, rc, args)
        self.assertFalse((self.proj_dir / "x").exists())  # 路径穿越未落地
        self.assertNotIn("### ", (self.proj_dir / "PLAN.md").read_text(encoding="utf-8")
                         .split("## 4.")[1].split("## 5.")[0])

    def test_close_unknown_wave_red(self):
        self._new()
        r = sh(sys.executable, "-m", "labkit", "close", "NOPE",
               cwd=self.proj_dir)
        self.assertEqual(r.returncode, 1)

    def test_outside_project_red(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(proj.cmd_wave("W1", "x"), 1)   # 无 PLAN.md
            self.assertEqual(proj.cmd_close("W1"), 1)       # 无 PLAN.md

    # ------------------------------------------------------------ 版本与编码
    def test_version_reports_running_package(self):
        """--version 报出实际运行的那份 labkit 的路径——两份同名包并存时靠它辨认。

        输出必须恰好一整行：argparse 自带的 version 动作会按终端宽度折行，装进
        site-packages 后路径变长就被折成两行，调用方拿不到完整路径。"""
        r = sh(sys.executable, "-m", "labkit", "--version")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            r.stdout.strip(),
            f"ft-labkit {labkit.__version__} ({Path(labkit.__file__).resolve().parent})")
        # 负向对照：不带子命令也不带 --version → 用法错；--version 不与子命令同用
        self.assertEqual(sh(sys.executable, "-m", "labkit").returncode, 2)
        self.assertEqual(sh(sys.executable, "-m", "labkit", "--version", "doctor").returncode, 2)

    def test_cli_survives_ascii_locale(self):
        """回归：运行环境非 UTF-8 时（Windows 传统代码页、输出被管道捕获、C 区域设置），
        中文提示语与 JSON verdict 的中文键曾让命令在最后一步打印上抛 UnicodeEncodeError——
        事情做完了，退出码却是失败。"""
        env = {"PATH": os.environ["PATH"], "HOME": str(self.sandbox), **ASCII_ENV}
        # 先验前提：这套环境确实让 Python 的缺省输出编码不是 UTF-8（否则本测试是纸门）
        probe = sh(sys.executable, "-c", "import sys; print(sys.stdout.encoding)",
                   cwd=self.sandbox, env=env)
        self.assertFalse(probe.stdout.strip().lower().startswith("utf"), probe.stdout)
        r = sh(sys.executable, "-m", "labkit", "new", "demo-lab",
               cwd=self.sandbox, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("内置模板", r.stdout)                 # 中文提示按 UTF-8 原样到达
        self.assertNotIn("UnicodeEncodeError", r.stderr)
        r = sh(sys.executable, "-m", "labkit", "wave", "W1", "baseline",
               cwd=self.proj_dir, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = sh(sys.executable, "-m", "labkit", "close", "W1", "--allow-dirty",
               cwd=self.proj_dir, env=env)
        self.assertEqual(r.returncode, 1)                  # 未填判决：如实红
        self.assertIn('"证据目录非空": false', r.stdout)    # JSON 的中文键完好
        self.assertNotIn("Traceback", r.stderr)


class TemplateIntegrity(unittest.TestCase):
    def test_template_has_gitignore(self):
        gi = TEMPLATE / ".gitignore"
        self.assertTrue(gi.exists(), "模板缺 .gitignore")
        self.assertTrue(GITIGNORE_MUST <= _patterns(gi.read_text(encoding="utf-8")))

    def test_template_placeholders_consistent(self):
        """模板里出现的占位符只有 {{PROJECT}}/{{DATE}}，且都能被 new 替换。"""
        allowed = {"{{PROJECT}}", "{{DATE}}"}
        for p in TEMPLATE.rglob("*"):
            if not p.is_file():
                continue
            for m in re.findall(r"\{\{[^}]*\}\}", p.read_text(encoding="utf-8")):
                self.assertIn(m, allowed, f"{p.relative_to(TEMPLATE)}: 未知占位符 {m}")


@unittest.skipUnless(SOURCE_TREE, "只对源码树测")
class SourceTreeOnly(unittest.TestCase):
    def test_source_tree_is_the_package_under_test(self):
        # 两种模式的分派前提：仓根下跑时，被测的必须是仓里的 labkit/ 而非另一份安装
        self.assertEqual(Path(labkit.__file__).resolve().parent,
                         (Path(__file__).resolve().parent.parent / "labkit").resolve())


if __name__ == "__main__":
    unittest.main()
