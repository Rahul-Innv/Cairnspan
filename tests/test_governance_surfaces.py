from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GovernanceSurfacesTest(unittest.TestCase):
    def test_readme_entry_copy_is_harness_first_and_provider_neutral(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        entry_copy = readme.split("## Getting started", 1)[0].lower()
        self.assertIn("independently authenticated local agent harnesses", entry_copy)
        for provider_name in (
            "anthropic",
            "claude",
            "codex",
            "cursor",
            "gemini",
            "google",
            "openai",
        ):
            self.assertNotIn(provider_name, entry_copy)

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

    def test_security_policy_names_the_private_reporting_channel(self) -> None:
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

        self.assertIn(
            "contact-project+krahul02004-cairnspan-84576401-issue-@incoming.gitlab.com",
            security,
        )
        self.assertIn("confidential Service Desk ticket", security)
        self.assertNotIn("While this repository is private", security)
        self.assertNotIn("Before public release", security)


if __name__ == "__main__":
    unittest.main()
