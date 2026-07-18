from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "cairnspan" / "scripts" / "critique_route_receipt.py"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def critique() -> dict:
    return {
        "status": "critique-complete",
        "keep": ["Clear hierarchy"],
        "issues": [{
            "severity": "high", "surface": "dashboard-light", "observation": "Footer clips",
            "evidence": "Text ends at boundary", "recommendation": "Allow wrapping",
        }],
        "cross_surface": ["States align"],
        "recommended_first_slice": {
            "goal": "Fix wrapping", "reason": "Trust text is hidden",
            "expected_files_or_surfaces": ["dashboard-light"],
            "verification": ["Check narrow viewport"],
        },
        "do_not_change": ["Keep honest no-price"],
        "questions_for_claude": ["Which breakpoint?"],
    }


def synthesis() -> dict:
    return {
        "status": "synthesis-complete",
        "accepted_findings": [{"finding": "Footer clips", "reason": "Trust evidence is hidden", "priority": "P0"}],
        "rejected_or_deferred": [],
        "needs_source_verification": [{"question": "Is nowrap used?", "likely_location": "dashboard card footer"}],
        "recommended_first_slice": {
            "goal": "Fix responsive footer wrapping",
            "scope": ["footer wrapping"],
            "non_goals": ["verdict logic"],
            "acceptance_checks": ["narrow viewport"],
            "owner_approval_needed": [],
        },
        "risk_notes": ["Avoid changing state semantics"],
        "next_codex_review_prompt": "Review footer wrapping from supplied screenshots only.",
    }


class CritiqueRouteReceiptTest(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=str(ROOT), text=True,
            capture_output=True, check=False,
        )

    def make_prepare_fixture(self, root: Path) -> dict[str, Path]:
        codex_prompt = root / "codex-prompt.txt"
        codex_prompt.write_text("critique", encoding="utf-8")
        codex_final = root / "codex-final.json"
        write_json(codex_final, critique())
        codex_summary = root / "codex-summary.json"
        write_json(codex_summary, {
            "status": "succeeded", "return_code": 0, "sandbox": "read-only",
            "strict_isolation": True, "tool_use_count": 0, "mcp_tool_use_count": 0,
            "terminal_event_count": 1, "thread_id": "thread-1", "observed_thread_ids": ["thread-1"],
            "descendant_cleanup_verified": True, "containment": "job-object", "target_cli_version": "fake-codex 1.0",
            "parse_warnings": [], "process_leak_details": [],
            "disabled_features": ["apps", "image_generation", "plugins", "shell_tool"],
            "prompt_sha256": sha256(codex_prompt), "run_id": "codex-run-1",
        })
        snapshot = root / "snapshot.json"
        write_json(snapshot, {"status": "succeeded", "source_commit": "a" * 40})
        manifest = {
            "schema_version": "0.2", "root": "fixture", "excludes": [], "strict": True,
            "root_metadata": {"path": ".", "type": "directory"}, "entries": [],
        }
        packet_before = root / "packet-before.json"
        packet_after = root / "packet-after.json"
        write_json(packet_before, manifest)
        write_json(packet_after, manifest)
        claude_prompt = root / "claude-prompt.txt"
        claude_prompt.write_text("synthesize", encoding="utf-8")
        return locals()

    def prepare_plan(self, root: Path) -> tuple[Path, dict[str, Path]]:
        fixture = self.make_prepare_fixture(root)
        plan = root / "plan.json"
        result = self.run_script(
            "prepare",
            "--codex-summary", str(fixture["codex_summary"]),
            "--codex-final", str(fixture["codex_final"]),
            "--codex-prompt", str(fixture["codex_prompt"]),
            "--snapshot-manifest", str(fixture["snapshot"]),
            "--packet-before", str(fixture["packet_before"]),
            "--packet-after", str(fixture["packet_after"]),
            "--claude-prompt", str(fixture["claude_prompt"]),
            "--out", str(plan),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return plan, fixture

    def test_prepare_links_verified_codex_edge_and_claude_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, _ = self.prepare_plan(root)
            value = json.loads(plan.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "prepared")
            self.assertEqual(value["codex_edge"]["run_id"], "codex-run-1")
            self.assertEqual(value["claude_edge_policy"]["tools"], "")
            self.assertEqual(value["claude_edge_policy"]["model"], "claude-sonnet-5")

    def test_prepare_rejects_codex_tool_use_or_packet_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_prepare_fixture(root)
            summary = json.loads(fixture["codex_summary"].read_text(encoding="utf-8"))
            summary["tool_use_count"] = 1
            write_json(fixture["codex_summary"], summary)
            result = self.run_script(
                "prepare", "--codex-summary", str(fixture["codex_summary"]),
                "--codex-final", str(fixture["codex_final"]), "--codex-prompt", str(fixture["codex_prompt"]),
                "--snapshot-manifest", str(fixture["snapshot"]), "--packet-before", str(fixture["packet_before"]),
                "--packet-after", str(fixture["packet_after"]), "--claude-prompt", str(fixture["claude_prompt"]),
                "--out", str(root / "plan.json"),
            )
            self.assertEqual(result.returncode, 2)

    def test_close_validates_claude_policy_schema_cost_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, fixture = self.prepare_plan(root)
            claude_final = root / "claude-final.json"
            write_json(claude_final, synthesis())
            claude_summary = root / "claude-summary.json"
            write_json(claude_summary, {
                "status": "succeeded", "return_code": 0, "safe_mode": True, "strict_mcp_config": True,
                "tools": "", "tool_use_count": 0, "mcp_tool_use_count": 0, "terminal_event_count": 1,
                "descendant_cleanup_verified": True, "containment": "job-object", "target_cli_version": "fake-claude 1.0",
                "session_id": "session-1", "observed_session_ids": ["session-1"], "parse_warnings": [],
                "process_leak_details": [], "parent_run_id": "codex-run-1", "run_depth": 1, "max_depth": 1,
                "prompt_sha256": sha256(fixture["claude_prompt"]), "total_cost_usd": 0.01,
                "requested_model": "claude-sonnet-5",
                "model_usage": {"claude-sonnet-5": {"costUSD": 0.01}},
                "init_capabilities": {"tools": [], "mcp_servers": [], "plugins": [], "skills": [], "slash_commands": []},
                "run_id": "claude-run-1",
            })
            closure = root / "closure.json"
            result = self.run_script(
                "close", "--plan", str(plan), "--claude-summary", str(claude_summary),
                "--claude-final", str(claude_final), "--claude-before", str(fixture["packet_before"]),
                "--claude-after", str(fixture["packet_after"]), "--out", str(closure),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(closure.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "closed")
            self.assertEqual(value["edges"][1]["synthesis_status"], "synthesis-complete")

    def test_close_rejects_wrong_parent_or_unknown_synthesis_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, fixture = self.prepare_plan(root)
            value = synthesis()
            value["override"] = "bad"
            claude_final = root / "claude-final.json"
            write_json(claude_final, value)
            claude_summary = root / "claude-summary.json"
            write_json(claude_summary, {
                "status": "succeeded", "return_code": 0, "safe_mode": True, "strict_mcp_config": True,
                "tools": "", "tool_use_count": 0, "mcp_tool_use_count": 0, "terminal_event_count": 1,
                "descendant_cleanup_verified": True, "containment": "job-object", "target_cli_version": "fake-claude 1.0",
                "session_id": "session-1", "observed_session_ids": ["session-1"], "parse_warnings": [],
                "process_leak_details": [], "parent_run_id": "wrong-parent", "run_depth": 1, "max_depth": 1,
                "prompt_sha256": sha256(fixture["claude_prompt"]), "total_cost_usd": 0.01,
                "requested_model": "claude-sonnet-5",
                "model_usage": {"claude-sonnet-5": {"costUSD": 0.01}},
                "init_capabilities": {"tools": [], "mcp_servers": [], "plugins": [], "skills": [], "slash_commands": []},
                "run_id": "claude-run-1",
            })
            result = self.run_script(
                "close", "--plan", str(plan), "--claude-summary", str(claude_summary),
                "--claude-final", str(claude_final), "--claude-before", str(fixture["packet_before"]),
                "--claude-after", str(fixture["packet_after"]), "--out", str(root / "closure.json"),
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / "closure.json").exists())

    def test_close_rejects_requested_model_missing_from_actual_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, fixture = self.prepare_plan(root)
            claude_final = root / "claude-final.json"
            write_json(claude_final, synthesis())
            claude_summary = root / "claude-summary.json"
            write_json(claude_summary, {
                "status": "succeeded", "return_code": 0, "safe_mode": True, "strict_mcp_config": True,
                "tools": "", "tool_use_count": 0, "mcp_tool_use_count": 0, "terminal_event_count": 1,
                "descendant_cleanup_verified": True, "containment": "job-object", "target_cli_version": "fake-claude 1.0",
                "session_id": "session-1", "observed_session_ids": ["session-1"], "parse_warnings": [],
                "process_leak_details": [], "parent_run_id": "codex-run-1", "run_depth": 1, "max_depth": 1,
                "prompt_sha256": sha256(fixture["claude_prompt"]), "total_cost_usd": 0.01,
                "requested_model": "claude-sonnet-5",
                "model_usage": {"claude-haiku-4-5-20251001": {"costUSD": 0.01}},
                "init_capabilities": {"tools": [], "mcp_servers": [], "plugins": [], "skills": [], "slash_commands": []},
                "run_id": "claude-run-1",
            })
            result = self.run_script(
                "close", "--plan", str(plan), "--claude-summary", str(claude_summary),
                "--claude-final", str(claude_final), "--claude-before", str(fixture["packet_before"]),
                "--claude-after", str(fixture["packet_after"]), "--out", str(root / "closure.json"),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("actual model usage", result.stderr)
            self.assertFalse((root / "closure.json").exists())


if __name__ == "__main__":
    unittest.main()
