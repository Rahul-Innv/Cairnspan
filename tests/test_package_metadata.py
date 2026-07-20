from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTest(unittest.TestCase):
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
