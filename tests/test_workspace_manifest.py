from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "cairnspan" / "scripts" / "workspace_manifest.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cairnspan_workspace_manifest", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load workspace manifest module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkspaceManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_module()

    def test_snapshot_includes_hidden_files_and_excludes_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".hidden").write_text("visible to manifest", encoding="utf-8")
            runtime = root / ".cairnspan" / "run"
            runtime.mkdir(parents=True)
            (runtime / "events.jsonl").write_text("runtime", encoding="utf-8")

            payload = self.manifest.snapshot(root)
            paths = {entry["path"] for entry in payload["entries"]}

            self.assertIn(".hidden", paths)
            self.assertNotIn(".cairnspan/run/events.jsonl", paths)

    def test_compare_detects_add_change_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.txt"
            changed = root / "changed.txt"
            old.write_text("old", encoding="utf-8")
            changed.write_text("before", encoding="utf-8")
            before = self.manifest.snapshot(root)
            old.unlink()
            changed.write_text("after", encoding="utf-8")
            (root / "new.txt").write_text("new", encoding="utf-8")
            after = self.manifest.snapshot(root)

            differences = self.manifest.compare(before, after)
            self.assertEqual({item["path"] for item in differences}, {"old.txt", "changed.txt", "new.txt"})

    def test_strict_snapshot_includes_runtime_and_empty_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cairnspan-hidden").mkdir()
            (root / "empty").mkdir()

            payload = self.manifest.snapshot(root, strict=True)
            by_path = {entry["path"]: entry for entry in payload["entries"]}

            self.assertTrue(payload["strict"])
            self.assertEqual(by_path[".cairnspan-hidden"]["type"], "directory")
            self.assertEqual(by_path["empty"]["type"], "directory")

    def test_compare_rejects_cross_root_or_policy_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            first = parent / "first"
            second = parent / "second"
            first.mkdir()
            second.mkdir()

            before = self.manifest.snapshot(first, strict=True)
            other_root = self.manifest.snapshot(second, strict=True)
            weaker_policy = self.manifest.snapshot(first, strict=False)

            self.assertIn("<manifest:root>", {item["path"] for item in self.manifest.compare(before, other_root)})
            self.assertIn("<manifest:strict>", {item["path"] for item in self.manifest.compare(before, weaker_policy)})

    def test_strict_snapshot_records_hardlink_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "workspace"
            root.mkdir()
            source = parent / "source.txt"
            source.write_text("linked", encoding="utf-8")
            linked = root / "linked.txt"
            os.link(source, linked)

            payload = self.manifest.snapshot(root, strict=True)
            entry = next(item for item in payload["entries"] if item["path"] == "linked.txt")

            self.assertGreaterEqual(entry["nlink"], 2)
            self.assertEqual(len(entry["file_id"]), 2)

    @unittest.skipUnless(os.name == "nt", "alternate data streams are Windows-specific")
    def test_strict_snapshot_records_alternate_data_streams(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "file.txt"
            target.write_text("default", encoding="utf-8")
            Path(str(target) + ":probe").write_text("hidden", encoding="utf-8")

            payload = self.manifest.snapshot(root, strict=True)
            entry = next(item for item in payload["entries"] if item["path"] == "file.txt")

            self.assertEqual(entry["streams"][0]["name"], ":probe:$DATA")
            self.assertEqual(entry["streams"][0]["size"], 6)

    def test_cli_compare_returns_nonzero_for_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            before_path = root / "before.json"
            after_path = root / "after.json"
            (workspace / "file.txt").write_text("before", encoding="utf-8")
            subprocess.run(
                [sys.executable, str(SCRIPT), "snapshot", "--root", str(workspace), "--output", str(before_path)],
                check=True, capture_output=True, text=True,
            )
            (workspace / "file.txt").write_text("after", encoding="utf-8")
            subprocess.run(
                [sys.executable, str(SCRIPT), "snapshot", "--root", str(workspace), "--output", str(after_path)],
                check=True, capture_output=True, text=True,
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "compare", str(before_path), str(after_path)],
                check=False, capture_output=True, text=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["status"], "changed")


if __name__ == "__main__":
    unittest.main()
