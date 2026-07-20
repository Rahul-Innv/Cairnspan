from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import release_readiness


class ReleaseReadinessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_source_root(self) -> Path:
        root = Path(self.temporary.name)
        for relative in release_readiness.REQUIRED_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")
        (root / "VERSION").write_text("0.1.1\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            '[project]\nname = "cairnspan"\nversion = "0.1.1"\n',
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "Do not describe Cairnspan as production-ready.\n"
            "Do not describe Cairnspan as enterprise-ready or three-agent capable\n",
            encoding="utf-8",
        )
        return root

    @staticmethod
    def clean_scanner(_root: Path, target: str) -> tuple[bool, str]:
        return True, f"{target}: zero scanner findings"

    def test_source_profile_passes_complete_fixture(self) -> None:
        root = self.make_source_root()
        report = release_readiness.build_report(root, "source", scanner=self.clean_scanner)
        self.assertTrue(report["ready"])
        self.assertEqual(report["version"], "0.1.1")

    def test_source_profile_rejects_mismatched_version(self) -> None:
        root = self.make_source_root()
        (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        report = release_readiness.build_report(root, "source", scanner=self.clean_scanner)
        self.assertFalse(report["ready"])
        version_check = next(item for item in report["checks"] if item["id"] == "source-version")
        self.assertEqual(version_check["status"], "block")

    def test_public_alpha_binds_tag_and_attestations_to_commit(self) -> None:
        root = self.make_source_root()
        (root / "docs" / "threat-model.md").write_text(
            "- [x] The separately specified write-enabled hostile-workspace matrix passes;\n",
            encoding="utf-8",
        )
        commit = "a" * 40
        attestation_path = root / "attestations.json"
        payload = {
            "schema_version": "0.1",
            "reviewed_commit": commit,
            **{field: True for field in release_readiness.ATTESTATION_FIELDS},
        }
        attestation_path.write_text(json.dumps(payload), encoding="utf-8")

        def clean_git(_root: Path, *args: str) -> tuple[int, str]:
            if args == ("rev-parse", "HEAD"):
                return 0, commit
            if args == ("status", "--porcelain", "--untracked-files=all"):
                return 0, ""
            if args == ("remote",):
                return 0, "origin"
            if args == ("tag", "--points-at", "HEAD"):
                return 0, "v0.1.1"
            raise AssertionError(args)

        report = release_readiness.build_report(
            root,
            "public-alpha",
            attestations=attestation_path,
            scanner=self.clean_scanner,
            git=clean_git,
        )
        self.assertTrue(report["ready"])
        self.assertEqual(report["commit"], commit)

    def test_public_alpha_blocks_missing_attestations_and_open_write_gate(self) -> None:
        root = self.make_source_root()
        commit = "b" * 40

        def git(_root: Path, *args: str) -> tuple[int, str]:
            responses = {
                ("rev-parse", "HEAD"): (0, commit),
                ("status", "--porcelain", "--untracked-files=all"): (0, ""),
                ("remote",): (0, "origin"),
                ("tag", "--points-at", "HEAD"): (0, "v0.1.1"),
            }
            return responses[args]

        report = release_readiness.build_report(root, "public-alpha", scanner=self.clean_scanner, git=git)
        self.assertFalse(report["ready"])
        blocked = {item["id"] for item in report["checks"] if item["status"] == "block"}
        self.assertIn("write-hostile-matrix", blocked)
        self.assertIn("release-attestations", blocked)

    def test_public_alpha_refuses_old_or_downgraded_versions(self) -> None:
        for version in ("0.1.0", "0.0.1"):
            with self.subTest(version=version):
                root = self.make_source_root()
                (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
                (root / "pyproject.toml").write_text(
                    f'[project]\nname = "cairnspan"\nversion = "{version}"\n',
                    encoding="utf-8",
                )
                commit = "c" * 40

                def git(_root: Path, *args: str) -> tuple[int, str]:
                    responses = {
                        ("rev-parse", "HEAD"): (0, commit),
                        ("status", "--porcelain", "--untracked-files=all"): (0, ""),
                        ("remote",): (0, "origin"),
                        ("tag", "--points-at", "HEAD"): (0, f"v{version}"),
                    }
                    return responses[args]

                report = release_readiness.build_report(
                    root,
                    "public-alpha",
                    scanner=self.clean_scanner,
                    git=git,
                )
                blocked = {item["id"] for item in report["checks"] if item["status"] == "block"}
                self.assertIn("new-release-version", blocked)

        name_check = (ROOT / "docs" / "name-check.md").read_text(encoding="utf-8")
        plan = (ROOT / "docs" / "plan.md").read_text(encoding="utf-8")
        combined = f"{name_check}\n{plan}"
        self.assertNotIn("The repository remains private alpha.", combined)
        self.assertNotIn("Keep the repo private until", combined)
        self.assertIn("source-public alpha", combined)
        self.assertIn("next package release", combined)
        self.assertIn("do not retroactively tag current source as `v0.1.0`", combined)


if __name__ == "__main__":
    unittest.main()
