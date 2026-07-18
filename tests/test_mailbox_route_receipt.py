from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
SCRIPT = SCRIPTS / "mailbox_route_receipt.py"
sys.path.insert(0, str(SCRIPTS))

from mailbox import write_request, write_response  # noqa: E402
from workspace_manifest import snapshot  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_manifest(path: Path, root: Path) -> None:
    write_json(path, snapshot(root, strict=True))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MailboxRouteReceiptTest(unittest.TestCase):
    def make_fixture(self, root: Path, *, extra_request_change: bool = False) -> dict[str, Path]:
        shared = root / "shared"
        mailbox_dir = shared / "mailbox"
        (shared / ".git").mkdir(parents=True)
        (shared / ".agents").mkdir()
        (mailbox_dir / "requests").mkdir(parents=True)
        (mailbox_dir / "responses").mkdir()
        before = root / "before.json"
        write_manifest(before, shared)

        request = {
            "id": "req-1", "origin_agent": "codex", "target_agent": "claude-code",
            "created_at": "2026-07-10T00:00:00Z", "prompt": "synthetic public",
            "sandbox": "workspace-write", "status": "pending", "run_depth": 0, "max_depth": 1,
        }
        response = {
            "id": "resp-1", "request_id": "req-1", "origin_agent": "claude-code",
            "target_agent": "codex", "created_at": "2026-07-10T00:01:00Z",
            "status": "succeeded", "final": "route-token-2",
        }
        request_path = write_request(mailbox_dir, request)
        if extra_request_change:
            (shared / "unexpected.txt").write_text("bad", encoding="utf-8")
        after_request = root / "after-request.json"
        write_manifest(after_request, shared)
        response_path = write_response(mailbox_dir, response)
        after_response = root / "after-response.json"
        write_manifest(after_response, shared)
        after_consume = root / "after-consume.json"
        write_manifest(after_consume, shared)

        codex_write_prompt = root / "codex-write.txt"
        claude_prompt = root / "claude.txt"
        codex_consume_prompt = root / "codex-consume.txt"
        codex_write_prompt.write_text("write", encoding="utf-8")
        claude_prompt.write_text("respond", encoding="utf-8")
        codex_consume_prompt.write_text("consume", encoding="utf-8")
        codex_write_final = root / "codex-write-final.md"
        claude_final = root / "claude-final.md"
        codex_consume_final = root / "codex-consume-final.md"
        codex_write_final.write_text("done\nmailbox-request-written\n", encoding="utf-8")
        claude_final.write_text("mailbox-response-written\n", encoding="utf-8")
        codex_consume_final.write_text("mailbox-roundtrip-ok:route-token-2\n", encoding="utf-8")

        common = {
            "status": "succeeded", "return_code": 0, "terminal_event_count": 1,
            "descendant_cleanup_verified": True, "containment": "job-object",
            "target_cli_version": "fake-cli 1.0",
            "parse_warnings": [], "process_leak_details": [],
        }
        codex_write_summary = root / "codex-write-summary.json"
        write_json(codex_write_summary, {
            **common, "target_agent": "codex", "sandbox": "workspace-write", "run_id": "run-write",
            "thread_id": "thread-write", "observed_thread_ids": ["thread-write"],
            "prompt_sha256": sha256(codex_write_prompt),
        })
        claude_summary = root / "claude-summary.json"
        write_json(claude_summary, {
            **common, "target_agent": "claude-code", "run_id": "run-claude",
            "session_id": "session-claude", "observed_session_ids": ["session-claude"],
            "prompt_sha256": sha256(claude_prompt), "permission_mode": "acceptEdits",
            "tools": "Read,Write", "safe_mode": True, "strict_mcp_config": True,
            "mcp_tool_use_count": 0, "requested_model": "claude-sonnet-5",
            "model_usage": {"claude-sonnet-5": {"costUSD": 0.01}}, "total_cost_usd": 0.01,
            "init_capabilities": {
                "tools": ["Read", "Write"], "mcp_servers": [], "plugins": [],
                "skills": [], "slash_commands": [],
            },
        })
        codex_consume_summary = root / "codex-consume-summary.json"
        write_json(codex_consume_summary, {
            **common, "target_agent": "codex", "sandbox": "read-only", "run_id": "run-consume",
            "thread_id": "thread-consume", "observed_thread_ids": ["thread-consume"],
            "prompt_sha256": sha256(codex_consume_prompt),
        })
        return locals()

    def run_close(self, fixture: dict[str, Path], out: Path) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable, str(SCRIPT), "--mailbox-dir", str(fixture["mailbox_dir"]),
            "--request", str(fixture["request_path"]), "--response", str(fixture["response_path"]),
            "--codex-write-summary", str(fixture["codex_write_summary"]),
            "--codex-write-final", str(fixture["codex_write_final"]),
            "--codex-write-prompt", str(fixture["codex_write_prompt"]),
            "--claude-summary", str(fixture["claude_summary"]), "--claude-final", str(fixture["claude_final"]),
            "--claude-prompt", str(fixture["claude_prompt"]),
            "--codex-consume-summary", str(fixture["codex_consume_summary"]),
            "--codex-consume-final", str(fixture["codex_consume_final"]),
            "--codex-consume-prompt", str(fixture["codex_consume_prompt"]),
            "--before-write-manifest", str(fixture["before"]),
            "--after-request-manifest", str(fixture["after_request"]),
            "--after-response-manifest", str(fixture["after_response"]),
            "--after-consume-manifest", str(fixture["after_consume"]),
            "--expected-consume-final", "mailbox-roundtrip-ok:route-token-2", "--out", str(out),
        ]
        return subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, check=False)

    def test_closes_valid_mailbox_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            out = root / "closure.json"

            result = self.run_close(fixture, out)

            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "closed")
            self.assertEqual(value["manifests"]["codex_consume"]["status"], "identical")
            self.assertNotIn("request_prompt", value)
            self.assertNotIn("response_final", value)
            self.assertEqual(len(value["exchange"]["request_prompt_sha256"]), 64)

    def test_rejects_unexpected_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root, extra_request_change=True)
            out = root / "closure.json"

            result = self.run_close(fixture, out)

            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())

    def test_rejects_missing_cleanup_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            summary = json.loads(fixture["codex_consume_summary"].read_text(encoding="utf-8"))
            summary["descendant_cleanup_verified"] = False
            write_json(fixture["codex_consume_summary"], summary)
            out = root / "closure.json"

            result = self.run_close(fixture, out)

            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
