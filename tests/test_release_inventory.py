# 发布清单门：仓内每个文件都必须在 .github/workflows/release-files.json 里逐个登记，
# 且两边集合完全相等——多一个未登记的文件即红。文件清单即批准发布的范围。
import json
import subprocess
import unittest

from tests.support import REPO

INVENTORY = REPO / ".github" / "workflows" / "release-files.json"
# 清单的分组（顺序即文件里的顺序）；各组的含义见 AGENTS.md 与 tools/verify_dist.py
GROUPS = ("repository", "build", "package", "licenses", "docs", "tests", "tools")


def load_inventory() -> dict[str, list[str]]:
    with open(INVENTORY, encoding="utf-8") as f:
        return json.load(f)


@unittest.skipUnless(INVENTORY.exists(), "清单文件缺失")
class ReleaseInventory(unittest.TestCase):
    def test_inventory_lists_itself(self):
        self.assertIn(".github/workflows/release-files.json",
                      load_inventory()["repository"])

    def test_groups_are_known_sorted_and_duplicate_free(self):
        inventory = load_inventory()
        self.assertEqual(tuple(inventory), GROUPS)
        seen = set()
        for group, paths in inventory.items():
            self.assertTrue(paths, f"{group} 组为空")
            self.assertEqual(paths, sorted(paths), f"{group} 组未按路径排序")
            for p in paths:
                self.assertNotIn(p, seen, f"重复登记：{p}")
                seen.add(p)

    def test_repository_inventory_matches_exactly(self):
        """仓内受版本管理的文件集合 == 清单全集。多出来的即未经批准发布，缺的即清单失效。"""
        listed = {p for paths in load_inventory().values() for p in paths}
        r = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z"],
                           capture_output=True, check=True)
        tracked = {p for p in r.stdout.decode("utf-8").split("\0") if p}
        self.assertEqual(sorted(tracked - listed), [], "仓里有未登记进发布清单的文件")
        self.assertEqual(sorted(listed - tracked), [], "清单里有仓中不存在的文件")

    def test_group_membership_rules(self):
        inventory = load_inventory()
        for p in inventory["build"]:
            self.assertIn(p, {"pyproject.toml", "MANIFEST.in"}, f"build 组只收构建配置：{p}")
        for p in inventory["package"]:
            self.assertTrue(p.startswith("labkit/"), f"package 组只收随包安装的文件：{p}")
        for p in inventory["licenses"]:
            self.assertEqual(p, p.upper(), f"licenses 组只收许可/声明文件：{p}")
        for p in inventory["docs"]:
            self.assertTrue(p.endswith(".md"), f"docs 组只收 Markdown：{p}")
        for p in inventory["tests"]:
            self.assertTrue(p.startswith("tests/"), f"tests 组只收测试：{p}")
        for p in inventory["tools"]:
            self.assertTrue(p.startswith("tools/"), f"tools 组只收仓内工具：{p}")


if __name__ == "__main__":
    unittest.main()
