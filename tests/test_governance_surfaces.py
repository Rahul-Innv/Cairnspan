from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GovernanceSurfacesTest(unittest.TestCase):
    def test_conduct_and_pointer_files_are_present(self) -> None:
        conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        status = (ROOT / "STATUS.md").read_text(encoding="utf-8")

        self.assertIn("SECURITY.md", conduct)
        self.assertIn("docs/plan.md", roadmap)
        self.assertIn("docs/release-readiness.md", roadmap)
        self.assertIn("docs/verification.md", status)
        self.assertIn("docs/release-readiness.md", status)

    def test_readme_uses_sentence_case_for_multiword_h2_headings(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for title_case_heading in (
            "## Why It Exists",
            "## What's Verified",
            "## Safety Model",
            "## Quick Start",
            "## Platform Support",
            "## Project Docs",
        ):
            self.assertNotIn(title_case_heading, readme)


if __name__ == "__main__":
    unittest.main()
