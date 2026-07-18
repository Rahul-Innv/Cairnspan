from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "cairnspan" / "scripts" / "prepare_tracked_snapshot.py"


class TrackedSnapshotTest(unittest.TestCase):
    def git(self, repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-C", str(repo), *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def make_repo(self, root: Path) -> Path:
        repo = root / "source"
        repo.mkdir()
        self.git(repo, "init", "-b", "main")
        self.git(repo, "config", "user.email", "snapshot@example.invalid")
        self.git(repo, "config", "user.name", "Snapshot Test")
        (repo / "README.md").write_text("tracked\n", encoding="utf-8")
        (repo / ".env.example").write_text("TOKEN=example-only\n", encoding="utf-8")
        self.git(repo, "add", "README.md", ".env.example")
        self.git(repo, "commit", "-m", "fixture")
        return repo

    def run_snapshot(
        self, repo: Path, out_dir: Path, manifest: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source-repo", str(repo),
                "--out-dir", str(out_dir),
                "--manifest-out", str(manifest),
                *extra,
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_exports_only_committed_regular_files_and_ignores_untracked_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            (repo / ".env").write_text("TOKEN=must-not-copy\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("ignore me\n", encoding="utf-8")
            out_dir = root / "snapshot"
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(repo, out_dir, manifest_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((out_dir / "README.md").read_text(encoding="utf-8"), "tracked\n")
            self.assertTrue((out_dir / ".env.example").is_file())
            self.assertFalse((out_dir / ".env").exists())
            self.assertFalse((out_dir / "untracked.txt").exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["file_count"], 2)
            self.assertEqual({item["path"] for item in manifest["files"]}, {".env.example", "README.md"})
            self.assertNotIn(str(repo), manifest_path.read_text(encoding="utf-8"))

    def test_dirty_tracked_file_fails_before_creating_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            (repo / "README.md").write_text("dirty\n", encoding="utf-8")
            out_dir = root / "snapshot"
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(repo, out_dir, manifest_path)

            self.assertEqual(result.returncode, 2)
            self.assertIn("dirty", result.stderr.lower())
            self.assertFalse(out_dir.exists())
            self.assertFalse(manifest_path.exists())

    def test_include_prefix_exports_only_selected_tracked_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            docs = repo / "docs"
            docs.mkdir()
            (docs / "design.md").write_text("public design\n", encoding="utf-8")
            private = repo / "internal"
            private.mkdir()
            (private / "notes.md").write_text("not selected\n", encoding="utf-8")
            self.git(repo, "add", "docs/design.md", "internal/notes.md")
            self.git(repo, "commit", "-m", "prefix fixture")
            out_dir = root / "snapshot"
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(
                repo, out_dir, manifest_path,
                "--include-prefix", "README.md",
                "--include-prefix", "docs",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out_dir / "README.md").is_file())
            self.assertTrue((out_dir / "docs" / "design.md").is_file())
            self.assertFalse((out_dir / ".env.example").exists())
            self.assertFalse((out_dir / "internal").exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["policy"]["include_prefixes"], ["README.md", "docs"])

    def test_tracked_env_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            (repo / ".env").write_text("TOKEN=fixture\n", encoding="utf-8")
            self.git(repo, "add", "-f", ".env")
            self.git(repo, "commit", "-m", "tracked env fixture")
            out_dir = root / "snapshot"
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(repo, out_dir, manifest_path)

            self.assertEqual(result.returncode, 2)
            self.assertIn("environment file", result.stderr.lower())
            self.assertFalse(out_dir.exists())

    def test_file_count_file_size_and_aggregate_limits_fail_before_export(self) -> None:
        cases = (
            ("files", ("--max-files", "1"), "file count"),
            ("single", ("--max-file-bytes", "4"), "size"),
            ("aggregate", ("--max-total-bytes", "10"), "aggregate"),
        )
        for label, extra, expected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo = self.make_repo(root)
                out_dir = root / "snapshot"
                manifest_path = root / "snapshot-manifest.json"

                result = self.run_snapshot(repo, out_dir, manifest_path, *extra)

                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr.lower())
                self.assertFalse(out_dir.exists())
                self.assertFalse(manifest_path.exists())

    def test_tracked_secret_content_is_rejected_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            (repo / "notes.txt").write_text(
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456", encoding="utf-8"
            )
            self.git(repo, "add", "notes.txt")
            self.git(repo, "commit", "-m", "secret fixture")
            out_dir = root / "snapshot"
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(repo, out_dir, manifest_path)

            self.assertEqual(result.returncode, 2)
            self.assertIn("publish-safety scan", result.stderr.lower())
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456", result.stderr)
            self.assertFalse(out_dir.exists())

    def test_gitlink_submodule_entry_is_rejected_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            commit = self.git(repo, "rev-parse", "HEAD").stdout.strip()
            self.git(repo, "update-index", "--add", "--cacheinfo", f"160000,{commit},vendor/child")
            self.git(repo, "commit", "-m", "submodule fixture")
            (repo / "vendor" / "child").mkdir(parents=True)
            out_dir = root / "snapshot"
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(repo, out_dir, manifest_path)

            self.assertEqual(result.returncode, 2)
            self.assertIn("regular file blob", result.stderr.lower())
            self.assertFalse(out_dir.exists())

    def test_existing_destination_or_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            out_dir = root / "snapshot"
            out_dir.mkdir()
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(repo, out_dir, manifest_path)

            self.assertEqual(result.returncode, 2)
            self.assertIn("already exists", result.stderr.lower())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support unavailable")
    def test_tracked_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            link = repo / "linked.txt"
            try:
                link.symlink_to("README.md")
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            self.git(repo, "add", "linked.txt")
            self.git(repo, "commit", "-m", "symlink fixture")
            out_dir = root / "snapshot"
            manifest_path = root / "snapshot-manifest.json"

            result = self.run_snapshot(repo, out_dir, manifest_path)

            self.assertEqual(result.returncode, 2)
            self.assertIn("regular file blob", result.stderr.lower())
            self.assertFalse(out_dir.exists())


if __name__ == "__main__":
    unittest.main()
