from __future__ import annotations

import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRUNED_DIRECTORIES = {".git", ".cairnspan", ".oauth-parley", "__pycache__"}
TEXT_SUFFIXES = {
    "",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_SOURCE_IDENTIFIERS = (
    "OAuth Parley",
    "oauth-parley",
    "oauth_parley",
    "OAUTH_PARLEY",
    '"OAUTH_" + "CAIRNSPAN_',
    "parley-summary.json",
    "parley-codex:",
    "parley-claude:",
    "parley-closed:",
)
LEGACY_IGNORE_LINES = {".oauth-parley/", ".oauth-parley-imagegen/"}


class CairnspanNamingTest(unittest.TestCase):
    def source_files(self) -> list[Path]:
        paths: list[Path] = []
        for current, directories, files in os.walk(ROOT):
            directories[:] = [name for name in directories if name not in PRUNED_DIRECTORIES]
            current_path = Path(current)
            for name in files:
                path = current_path / name
                if name == ".env" or path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                paths.append(path)
        return paths

    def test_canonical_and_shim_skill_paths_use_cairnspan(self) -> None:
        for path in (
            ROOT / "skills" / "cairnspan" / "SKILL.md",
            ROOT / ".agents" / "skills" / "cairnspan" / "SKILL.md",
            ROOT / ".claude" / "skills" / "cairnspan" / "SKILL.md",
        ):
            self.assertTrue(path.is_file(), path)

        for path in (
            ROOT / "skills" / "oauth-parley",
            ROOT / ".agents" / "skills" / "oauth-parley",
            ROOT / ".claude" / "skills" / "oauth-parley",
        ):
            self.assertFalse(path.exists(), path)

    def test_no_legacy_runtime_identifiers_remain_in_source(self) -> None:
        findings: list[str] = []
        for path in self.source_files():
            if path.resolve() == Path(__file__).resolve():
                continue
            relative = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if relative == ".gitignore" and line.strip() in LEGACY_IGNORE_LINES:
                    continue
                for identifier in FORBIDDEN_SOURCE_IDENTIFIERS:
                    if identifier in line:
                        findings.append(f"{relative}:{line_number}: {identifier}")

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
