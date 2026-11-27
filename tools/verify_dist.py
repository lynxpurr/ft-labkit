"""发布证据：从确切的提交构建 sdist 与 wheel，对照发布清单逐项核对，落 SHA256SUMS。

用法（仓根，工作区干净）：
    python -m pip install "build>=1.2,<2"
    python tools/verify_dist.py [输出目录，缺省 dist]

核对项（任一不符即非零退出，且不落任何产物）：
  1. 工作区与 HEAD 一致——被审阅的树就是被构建的树
  2. HEAD 里的文件集合 == 发布清单全集（.github/workflows/release-files.json）
  3. wheel：文件集合 == package 组 + licenses 组（装在 dist-info/licenses/ 下）+ 构建生成的
     元数据；其余每个文件与 Git blob 逐字节相同；RECORD 里的哈希与长度逐项复算
  4. sdist：文件集合 == 应进源码包的各组 + 构建生成的元数据；其余每个文件与 Git blob
     逐字节相同
  5. 包元数据里的名称、版本、许可表达式与 pyproject / labkit.__version__ 一致
通过后写 SHA256SUMS（两个归档的 sha256）与 release-manifest.json（提交、树、哈希）。
只用标准库。构建在 HEAD 的一份干净导出里进行，不读工作区。
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ".github/workflows/release-files.json"
WHEEL_GROUPS = ("package", "licenses")                 # 进 wheel 的组
SDIST_GROUPS = ("build", "package", "licenses", "docs", "tests")  # 进源码包的组
WHEEL_GENERATED = ("METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD")
SDIST_GENERATED = ("PKG-INFO", "setup.cfg")
EGG_INFO_GENERATED = ("PKG-INFO", "SOURCES.txt", "dependency_links.txt",
                      "entry_points.txt", "top_level.txt")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"[verify_dist] {message}")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def committed_tree() -> tuple[str, str, dict[str, bytes]]:
    """HEAD 的提交号、树号与每个路径的内容（取自 Git 对象库，不读工作区）。"""
    commit, tree = git("show", "-s", "--format=%H %T", "HEAD").decode().split()
    blobs: dict[str, bytes] = {}
    for entry in git("ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        path = name.decode("utf-8")
        require(kind == "blob" and mode in {"100644", "100755"},
                f"Unsupported repository entry: {path!r} ({mode} {kind})")
        blobs[path] = git("cat-file", "blob", blob)
    return commit, tree, blobs


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def wheel_files(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, f"Wheel is corrupt: {path.name}")
        return {info.filename: archive.read(info)
                for info in archive.infolist() if not info.is_dir()}


def sdist_files(path: Path) -> dict[str, bytes]:
    files = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            require(member.isreg() or member.isdir(), f"Unsupported archive member: {member.name!r}")
            if member.isreg():
                _, _, rest = member.name.partition("/")
                require(bool(rest), f"Archive member outside the top directory: {member.name!r}")
                require(rest not in files, f"Duplicate archive member: {rest!r}")
                files[rest] = archive.extractfile(member).read()
    return files


def diff(expected: set[str], actual: set[str], what: str) -> None:
    missing, extra = sorted(expected - actual), sorted(actual - expected)
    require(not missing and not extra,
            f"{what} differs: missing={missing}, unexpected={extra}")


def check_bytes(files: dict[str, bytes], names: dict[str, str],
                blobs: dict[str, bytes], what: str) -> None:
    """归档里的每个文件都必须与提交树里的对应路径逐字节相同（names: 归档内路径 → 提交树路径）。"""
    for archive_name, committed in names.items():
        require(committed in blobs, f"{what}: not in the committed tree: {committed!r}")
        require(files[archive_name] == blobs[committed],
                f"{what}: source bytes differ: {committed}")


def check_record(files: dict[str, bytes], dist_info: str) -> None:
    rows = list(csv.reader(io.StringIO(files[f"{dist_info}/RECORD"].decode("utf-8"))))
    recorded = {name: (digest, size) for name, digest, size in rows if name != f"{dist_info}/RECORD"}
    diff(set(files) - {f"{dist_info}/RECORD"}, set(recorded), "wheel RECORD")
    for name, (digest, size) in recorded.items():
        want = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(files[name]).digest()).decode().rstrip("=")
        require(digest == want and int(size) == len(files[name]),
                f"wheel RECORD mismatch: {name}")


def check_metadata(files: dict[str, bytes], dist_info: str, project: dict) -> None:
    headers = {}
    for line in files[f"{dist_info}/METADATA"].decode("utf-8").splitlines():
        if not line:
            break
        key, _, value = line.partition(": ")
        headers[key] = value
    require(headers.get("Name") == project["name"], f"Metadata Name: {headers.get('Name')!r}")
    require(headers.get("Version") == project["version"],
            f"Metadata Version: {headers.get('Version')!r}")
    require(headers.get("License-Expression") == project["license"],
            f"Metadata License-Expression: {headers.get('License-Expression')!r}")


def main(argv: list[str]) -> int:
    out = (ROOT / argv[0]) if argv else (ROOT / "dist")
    require(not out.exists() or not any(out.iterdir()),
            f"Use a fresh output directory: {out}")
    require(not git("status", "--porcelain").strip(),
            "Working tree differs from HEAD; commit or clean it first.")
    commit, tree, blobs = committed_tree()
    inventory = json.loads(blobs[INVENTORY])
    listed = [name for paths in inventory.values() for name in paths]
    require(len(listed) == len(set(listed)), "Duplicate path in the repository inventory.")
    diff(set(listed), set(blobs), "Repository inventory")

    project = tomllib.loads(blobs["pyproject.toml"].decode("utf-8"))["project"]
    version_file = blobs["labkit/__init__.py"].decode("utf-8")
    require(f'__version__ = "{project["version"]}"' in version_file,
            "labkit.__version__ differs from pyproject")
    egg_info = f"{project['name'].replace('-', '_')}.egg-info"

    with tempfile.TemporaryDirectory(prefix="labkit-release-") as tmp:
        work = Path(tmp) / "src"
        work.mkdir()
        with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", commit))) as tar:
            tar.extractall(work, filter="data")
        built = Path(tmp) / "out"
        subprocess.run([sys.executable, "-m", "build", "--outdir", str(built)],
                       cwd=work, check=True)
        wheels = sorted(built.glob("*.whl"))
        sdists = sorted(built.glob("*.tar.gz"))
        require(len(wheels) == 1 and len(sdists) == 1,
                f"Expected one wheel and one sdist, found {[p.name for p in built.iterdir()]}")
        wheel, sdist = wheel_files(wheels[0]), sdist_files(sdists[0])
        artifacts = {p.name: p.read_bytes() for p in (*wheels, *sdists)}  # 临时目录还在时读出

    dist_info = f"{project['name'].replace('-', '_')}-{project['version']}.dist-info"
    # 归档内路径 → 提交树路径：wheel 里许可文件装在 dist-info/licenses/ 下
    wheel_names = {name: name for name in inventory["package"]}
    wheel_names |= {f"{dist_info}/licenses/{name}": name for name in inventory["licenses"]}
    wheel_generated = {f"{dist_info}/{name}" for name in WHEEL_GENERATED}
    diff(set(wheel_names) | wheel_generated, set(wheel), "Wheel file list")
    check_bytes(wheel, wheel_names, blobs, "wheel")
    check_record(wheel, dist_info)
    check_metadata(wheel, dist_info, project)

    sdist_names = {name: name for group in SDIST_GROUPS for name in inventory[group]}
    sdist_generated = set(SDIST_GENERATED) | {f"{egg_info}/{name}" for name in EGG_INFO_GENERATED}
    diff(set(sdist_names) | sdist_generated, set(sdist), "sdist file list")
    check_bytes(sdist, sdist_names, blobs, "sdist")

    digests = {name: sha256(data) for name, data in artifacts.items()}
    out.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        (out / name).write_bytes(data)
    (out / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(digests.items())),
        encoding="utf-8")
    # 落盘后从磁盘复核：写出去的字节就是核对过的字节
    for name, digest in digests.items():
        require(sha256((out / name).read_bytes()) == digest,
                f"Written file does not match its digest: {name}")
    (out / "release-manifest.json").write_text(json.dumps({
        "commit": commit, "tree": tree, "project": project["name"],
        "version": project["version"], "license": project["license"],
        "files": {group: len(paths) for group, paths in inventory.items()},
        "sha256": digests}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[verify_dist] OK commit={commit[:12]} tree={tree[:12]} "
          f"files={len(blobs)}")
    for name, digest in sorted(digests.items()):
        print(f"[verify_dist] sha256 {digest}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
