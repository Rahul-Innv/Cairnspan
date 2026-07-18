from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
SCRIPT = SCRIPTS / "artifact_route_receipt.py"
sys.path.insert(0, str(SCRIPTS))

from workspace_manifest import snapshot  # noqa: E402
from prepare_artifact_handoff import build_prompt, validate_spec  # noqa: E402


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cairnspan_artifact_route_receipt", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load artifact route receipt module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ArtifactRouteReceiptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = load_module()

    def fixture(self, root: Path) -> argparse.Namespace:
        design_workspace = root / "design"
        design_workspace.mkdir()
        design_before = root / "design-before.json"
        design_after = root / "design-after.json"
        write_json(design_before, snapshot(design_workspace, strict=True))
        write_json(design_after, snapshot(design_workspace, strict=True))
        design_prompt = root / "design-prompt.txt"
        design_prompt.write_text("Return one synthetic design spec.", encoding="utf-8")
        design_final = root / "design-final.json"
        write_json(design_final, {
            "status": "design-spec-complete", "artifact_role": "probe", "format": "png",
            "width": 512, "height": 512, "subject": "Synthetic paper compass",
            "composition": "Centered on a pale background", "palette": ["red", "white"],
            "text_policy": "No text", "prohibited": ["logos"],
            "provenance_note": "Synthetic with no reference assets.",
        })
        design_summary = root / "design-summary.json"
        write_json(design_summary, {
            "status": "succeeded", "return_code": 0, "target_agent": "claude-code",
            "descendant_cleanup_verified": True, "containment": "job-object", "target_cli_version": "fake-claude 1.0", "run_depth": 0, "max_depth": 1,
            "run_id": "design-run", "elapsed_seconds": 8, "prompt_sha256": digest(design_prompt),
            "requested_model": "claude-sonnet-5", "safe_mode": True, "strict_mcp_config": True,
            "tools": "", "tool_use_count": 0, "mcp_tool_use_count": 0, "tool_names": [],
            "init_capabilities": {"tools": [], "mcp_servers": []}, "total_cost_usd": 0.02,
            "usage": {"server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}},
        })
        generation_prompt = root / "generation-prompt.txt"
        generation_prompt.write_text(
            build_prompt(validate_spec(json.loads(design_final.read_text(encoding="utf-8"))), "output/probe.png"),
            encoding="utf-8",
        )
        producer_summary = root / "producer-summary.json"
        write_json(producer_summary, {
            "status": "succeeded", "return_code": 0, "target_agent": "codex",
            "descendant_cleanup_verified": True, "containment": "job-object", "target_cli_version": "fake-codex 1.0", "run_depth": 0, "max_depth": 1,
            "run_id": "producer-run", "elapsed_seconds": 100,
            "prompt_sha256": digest(generation_prompt),
        })
        producer_final = root / "producer-final.md"
        producer_final.write_text("image-artifact-ready\n", encoding="utf-8")
        staging = root / "staging"
        artifact = staging / "output" / "probe.png"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"synthetic png fixture bytes")
        artifact_manifest = root / "artifact-manifest.json"
        write_json(artifact_manifest, {
            "status": "accepted", "final_disposition": "accepted-for-human-review",
            "producer_run_id": "producer-run", "producer_summary_sha256": digest(producer_summary),
            "producer_cli_version": "fake-codex 1.0",
            "generation_prompt_sha256": digest(generation_prompt), "relative_path": "output/probe.png",
            "sha256": digest(artifact), "validation": {"width": 512, "height": 512},
        })
        return argparse.Namespace(
            design_summary=design_summary, design_final=design_final, design_prompt=design_prompt,
            design_before_manifest=design_before, design_after_manifest=design_after,
            producer_summary=producer_summary, producer_final=producer_final,
            generation_prompt=generation_prompt, artifact_manifest=artifact_manifest,
            staging_root=staging, claude_model="claude-sonnet-5", max_claude_budget_usd="0.05",
            max_route_elapsed_seconds="300", producer_marker="image-artifact-ready",
            visual_review_status="passed", visual_review_note="Synthetic fixture matches the declared subject.",
        )

    def test_closes_valid_route_without_product_integration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            value = self.receipt.close(self.fixture(Path(tmp)))

            self.assertEqual(value["status"], "closed")
            self.assertEqual(value["product_integration"], "not-run")
            self.assertIn("awaiting-separate-human", value["disposition"])

    def test_rejects_claude_tool_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            summary = json.loads(args.design_summary.read_text(encoding="utf-8"))
            summary["tool_use_count"] = 1
            write_json(args.design_summary, summary)
            with self.assertRaises(self.receipt.ArtifactRouteError):
                self.receipt.close(args)

    def test_rejects_artifact_replay_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            (args.staging_root / "output" / "probe.png").write_bytes(b"changed after validation")
            with self.assertRaises(self.receipt.ArtifactRouteError):
                self.receipt.close(args)

    def test_rejects_generation_prompt_not_derived_from_validated_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            args.generation_prompt.write_text("Create something else.\n", encoding="utf-8")
            producer = json.loads(args.producer_summary.read_text(encoding="utf-8"))
            producer["prompt_sha256"] = digest(args.generation_prompt)
            write_json(args.producer_summary, producer)
            manifest = json.loads(args.artifact_manifest.read_text(encoding="utf-8"))
            manifest["producer_summary_sha256"] = digest(args.producer_summary)
            manifest["generation_prompt_sha256"] = digest(args.generation_prompt)
            write_json(args.artifact_manifest, manifest)

            with self.assertRaisesRegex(self.receipt.ArtifactRouteError, "exact prompt derived"):
                self.receipt.close(args)


if __name__ == "__main__":
    unittest.main()
