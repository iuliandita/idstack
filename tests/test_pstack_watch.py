import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pstack_watch as pw  # noqa: E402

CATALOG = {
    "skills": ["poteto-mode", "principle-fix-root-causes"],
    "playbooks": ["bug-fix", "shipping"],
    "agents": ["poteto-agent"],
}
LOCK = {
    "upstream": {"version": "1.0.0", "commit": "a" * 40},
    "mirror": {"version": "1.0.0"},
    "catalog": CATALOG,
    "watched": {"skills/poteto-mode/playbooks/bug-fix.md": "sha1"},
}


def snap(**over):
    base = {
        "version": "1.0.0",
        "commit": "a" * 40,
        "catalog": CATALOG,
        "blobs": {"skills/poteto-mode/playbooks/bug-fix.md": "sha1"},
    }
    return {**base, **over}


class ReadmeNames(unittest.TestCase):
    def test_only_pstack_rows_count(self):
        text = "| `poteto-mode` | pstack | x |\n| **id-mode** | **idstack** | y |\n| bug-fix | pstack | overlay |\n"
        self.assertEqual(pw.readme_names(text), {"poteto-mode", "bug-fix"})


class Compare(unittest.TestCase):
    def test_in_sync(self):
        diff = pw.compare(LOCK, snap(), "1.0.0", {"bug-fix", "fix-root-causes", "poteto-agent"})
        self.assertFalse(pw.drifted(diff))

    def test_each_drift_is_reported(self):
        gone = {**CATALOG, "playbooks": ["shipping"]}
        cases = {
            "version": (snap(version="1.1.0"), "1.0.0", set(), lambda d: d["version"] == ("1.0.0", "1.1.0")),
            "removed name": (snap(catalog=gone), "1.0.0", {"bug-fix"}, lambda d: d["missing"] == ["bug-fix"]),
            "changed file": (
                snap(blobs={"skills/poteto-mode/playbooks/bug-fix.md": "sha2"}),
                "1.0.0",
                set(),
                lambda d: d["changed"] == [("skills/poteto-mode/playbooks/bug-fix.md", "changed")],
            ),
            "new playbook": (
                snap(catalog={**CATALOG, "playbooks": ["bug-fix", "shipping", "eval"]}),
                "1.0.0",
                set(),
                lambda d: d["added"] == ["playbooks/eval"],
            ),
            "mirror ahead of pin": (snap(), "1.1.0", set(), lambda d: d["mirror"] == ("1.0.0", "1.1.0")),
        }
        for label, (s, mirror_head, names, expect) in cases.items():
            with self.subTest(label):
                diff = pw.compare(LOCK, s, mirror_head, names)
                self.assertTrue(pw.drifted(diff))
                self.assertTrue(expect(diff), diff)

    def test_resolve_finds_principles_and_agents(self):
        self.assertEqual(pw.resolve("fix-root-causes", CATALOG), "skills/principle-fix-root-causes/SKILL.md")
        self.assertEqual(pw.resolve("poteto-agent", CATALOG), "agents/poteto-agent.md")
        self.assertIsNone(pw.resolve("nope", CATALOG))


if __name__ == "__main__":
    unittest.main()
