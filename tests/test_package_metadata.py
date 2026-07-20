from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTest(unittest.TestCase):
    def test_discovery_metadata_is_provider_neutral(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata["project"]
        self.assertEqual(
            project["description"],
            "Bounded, receipt-producing task handoffs between independently "
            "authenticated local agent harnesses.",
        )
        self.assertEqual(
            project["keywords"],
            [
                "agents",
                "agent-harnesses",
                "multi-agent",
                "delegation",
                "local-first",
                "cli",
                "receipts",
            ],
        )
        discovery_copy = " ".join([project["description"], *project["keywords"]]).lower()
        for provider_name in (
            "anthropic",
            "claude",
            "codex",
            "cursor",
            "gemini",
            "google",
            "openai",
        ):
            self.assertNotIn(provider_name, discovery_copy)

    def test_project_urls_link_to_canonical_public_surfaces(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            metadata["project"]["urls"],
            {
                "Repository": "https://gitlab.com/krahul02004/Cairnspan",
                "Issues": "https://gitlab.com/krahul02004/Cairnspan/-/work_items",
                "Changelog": "https://gitlab.com/krahul02004/Cairnspan/-/blob/main/CHANGELOG.md",
            },
        )


if __name__ == "__main__":
    unittest.main()
