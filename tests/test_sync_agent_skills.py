import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "sync_agent_skills.py"
SPEC = importlib.util.spec_from_file_location("sync_agent_skills", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SkillSyncTest(unittest.TestCase):
    def make_manifest(self, root: Path) -> Path:
        manifest = root / "skill-sync.json"
        manifest.write_text(
            json.dumps(
                {
                    "canonical": ".claude/skills",
                    "generated": ".agents/skills",
                    "skills": ["example"],
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_check_passes_for_identical_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.make_manifest(root)
            body = "---\nname: example\ndescription: Example\n---\n"
            self.write(root / ".claude/skills/example/SKILL.md", body)
            self.write(root / ".agents/skills/example/SKILL.md", body)
            self.assertEqual(MODULE.check(manifest), [])

    def test_check_detects_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.make_manifest(root)
            self.write(root / ".claude/skills/example/SKILL.md", "canonical")
            self.write(root / ".agents/skills/example/SKILL.md", "generated")
            self.assertEqual(MODULE.check(manifest)[0].status, "drift")

    def test_write_repairs_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.make_manifest(root)
            source = root / ".claude/skills/example/SKILL.md"
            self.write(source, "canonical")
            MODULE.synchronize(manifest)
            self.assertEqual(MODULE.check(manifest), [])
            self.assertEqual((root / ".agents/skills/example/SKILL.md").read_text(), "canonical")

    def test_write_refuses_to_delete_generated_only_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.make_manifest(root)
            self.write(root / ".claude/skills/example/SKILL.md", "canonical")
            self.write(root / ".agents/skills/example/SKILL.md", "canonical")
            self.write(root / ".agents/skills/example/local.txt", "keep")
            with self.assertRaises(RuntimeError):
                MODULE.synchronize(manifest)

    def test_manifest_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.make_manifest(root)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["skills"] = ["../outside"]
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.load_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
