from __future__ import annotations

import hashlib
import json
import os
import runpy
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "skills" / "cairnspan" / "scripts" / "start_claude_session.py"


class ClaudeLauncherTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows Job Object tracking")
    def test_job_object_ignores_recycled_historical_pids(self) -> None:
        namespace = runpy.run_path(str(LAUNCHER))
        active = namespace["windows_tracked_processes_active"]
        tracked_ids = namespace["windows_tracked_process_ids"]
        replacements = {
            "windows_job_active_processes": lambda _job: 0,
            "windows_job_process_ids": lambda _job: [],
            "windows_pid_alive": lambda _pid: True,
        }
        with mock.patch.dict(active.__globals__, replacements):
            self.assertFalse(active(object(), {12345}))
            self.assertEqual(tracked_ids(object(), {12345}), set())

    def run_launcher(
        self, *args: str, check: bool = False, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(LAUNCHER), *args]
        if os.name == "nt" and "--allow-shell-wrapper" not in args:
            for index, value in enumerate(args[:-1]):
                if value == "--claude-bin" and Path(args[index + 1]).suffix.lower() in {".cmd", ".bat", ".ps1"}:
                    command.append("--allow-shell-wrapper")
                    break
        return subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=check,
            env=env,
        )

    def make_fake_claude(self, temp_dir: Path, mode: str = "success_json") -> Path:
        script = temp_dir / "fake_claude.py"
        script.write_text(
            textwrap.dedent(
                f"""
                import json
                import os
                import subprocess
                import sys
                import time
                import warnings

                warnings.simplefilter("ignore", ResourceWarning)
                sys.stdout.reconfigure(encoding="utf-8")
                if "--version" in sys.argv:
                    print("fake-claude 1.0")
                    raise SystemExit(0)
                mode = {mode!r}
                if mode == "timeout":
                    time.sleep(5)
                    raise SystemExit(0)
                if mode == "descendant_timeout":
                    marker = sys.argv[-1]
                    child_code = f"import time; from pathlib import Path; time.sleep(2); Path({{marker!r}}).write_text('survived', encoding='utf-8')"
                    subprocess.Popen([sys.executable, "-c", child_code])
                    time.sleep(10)
                    raise SystemExit(0)
                if mode == "descendant_output_limit":
                    marker = sys.argv[-1]
                    child_code = f"import time; from pathlib import Path; time.sleep(2); Path({{marker!r}}).write_text('survived', encoding='utf-8')"
                    subprocess.Popen([sys.executable, "-c", child_code])
                    sys.stdout.write("x" * 200000)
                    sys.stdout.flush()
                    time.sleep(10)
                    raise SystemExit(0)
                if mode == "descendant_after_exit":
                    marker = sys.argv[-1]
                    child_code = f"import time; from pathlib import Path; time.sleep(30); Path({{marker!r}}).write_text('survived', encoding='utf-8')"
                    subprocess.Popen([sys.executable, "-c", child_code])
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "must-not-pass", "session_id": "session-descendant"}}))
                    raise SystemExit(0)
                if mode == "descendant_graceful_after_exit":
                    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "graceful-ok", "session_id": "session-graceful"}}))
                    raise SystemExit(0)
                if mode == "auth_fail":
                    print("Authentication failed: api_key=secret-value", file=sys.stderr)
                    raise SystemExit(42)
                if mode == "network_fail":
                    print("API Error: Unable to connect to API (ConnectionRefused)", file=sys.stderr)
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": True, "api_error_status": "ConnectionRefused", "result": "API Error: Unable to connect to API (ConnectionRefused)", "session_id": "session-network"}}))
                    raise SystemExit(0)
                if mode == "large_output":
                    print("x" * 200000)
                    raise SystemExit(0)
                if mode == "large_output_no_newline":
                    sys.stdout.write("x" * 200000)
                    sys.stdout.flush()
                    raise SystemExit(0)
                if mode == "empty_success":
                    raise SystemExit(0)
                if mode == "invalid_json":
                    print("not-json")
                    raise SystemExit(0)
                if mode == "invalid_utf8_output":
                    sys.stdout.buffer.write(b'{{"type":"result","subtype":"success","is_error":false,"session_id":"session-bytes"}}' + bytes([10, 255]))
                    sys.stdout.buffer.flush()
                    raise SystemExit(0)
                if mode == "damaged_after_completion":
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "must-not-pass", "session_id": "session-damaged"}}))
                    print("{{")
                    raise SystemExit(0)
                if mode == "contradictory_result":
                    print(json.dumps({{"type": "result", "subtype": "error", "is_error": False, "result": "must-not-pass", "session_id": "session-error"}}))
                    raise SystemExit(0)
                if mode == "unicode":
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "café 東京", "session_id": "session-unicode"}}, ensure_ascii=False))
                    raise SystemExit(0)
                if mode == "env_probe":
                    api_keys_present = any(name in os.environ for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"))
                    run_context_present = bool(os.environ.get("CAIRNSPAN_RUN_ID"))
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": f"env={{api_keys_present}};context={{run_context_present}}", "session_id": "session-env"}}))
                    raise SystemExit(0)
                if mode == "stdin_eof":
                    sys.stdin.read()
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "stdin-eof-ok", "session_id": "session-stdin"}}))
                    raise SystemExit(0)
                if mode == "stream":
                    print(json.dumps({{"type": "system", "session_id": "session-stream"}}))
                    print(json.dumps({{"type": "assistant", "message": {{"role": "assistant", "content": [{{"type": "text", "text": "stream-ok"}}]}}}}))
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "usage": {{"input_tokens": 3, "output_tokens": 4}}, "total_cost_usd": 0.01, "session_id": "session-stream"}}))
                    raise SystemExit(0)
                if mode == "stream_capabilities":
                    print(json.dumps({{"type": "system", "subtype": "init", "session_id": "session-capabilities", "tools": [], "mcp_servers": [], "plugins": [{{"name": "example-plugin", "path": "/private/path"}}], "skills": ["example-skill"], "agents": ["general-purpose"], "slash_commands": ["example-skill"]}}))
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "capabilities-ok", "session_id": "session-capabilities"}}))
                    raise SystemExit(0)
                if mode == "stream_tool_violation":
                    print(json.dumps({{"type": "system", "subtype": "init", "session_id": "session-tool-policy", "tools": ["Read"], "mcp_servers": []}}))
                    print(json.dumps({{"type": "assistant", "message": {{"role": "assistant", "content": [{{"type": "tool_use", "name": "Read", "input": {{}}}}]}}}}))
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "must-not-pass", "session_id": "session-tool-policy"}}))
                    raise SystemExit(0)
                if mode == "conflicting_session_ids":
                    print(json.dumps({{"type": "system", "subtype": "init", "session_id": "session-one", "tools": [], "mcp_servers": []}}))
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "must-not-pass", "session_id": "session-two"}}))
                    raise SystemExit(0)
                if mode == "duplicate_terminal":
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "must-not-pass", "session_id": "session-terminal"}}))
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "must-not-pass", "session_id": "session-terminal"}}))
                    raise SystemExit(0)
                if mode == "over_cost":
                    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "must-not-pass", "session_id": "session-cost", "total_cost_usd": 0.06}}))
                    raise SystemExit(0)
                print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "basic-ok", "session_id": "session-basic", "usage": {{"input_tokens": 1, "output_tokens": 2}}, "modelUsage": {{"model": {{"costUSD": 0.001}}}}, "total_cost_usd": 0.001}}))
                raise SystemExit(0)
                """
            ),
            encoding="utf-8",
        )
        if os.name == "nt":
            wrapper = temp_dir / "fake_claude.cmd"
            wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
        else:
            wrapper = temp_dir / "fake_claude"
            wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
        return wrapper

    def make_python_exec_fake(self, workspace: Path, mode: str) -> str:
        script = workspace / "exec"
        script.write_text(
            textwrap.dedent(
                f"""
                import sys
                import time

                mode = {mode!r}
                if mode == "timeout":
                    time.sleep(5)
                    raise SystemExit(0)
                raise SystemExit(1)
                """
            ),
            encoding="utf-8",
        )
        return sys.executable

    def read_summary(self, out_dir: Path) -> dict:
        return json.loads((out_dir / "cairnspan-summary.json").read_text(encoding="utf-8"))

    def read_stderr_summary(self, result: subprocess.CompletedProcess[str]) -> dict:
        return json.loads(result.stderr)

    def assert_path_within(self, path: str | Path, root: Path) -> None:
        try:
            Path(path).resolve().relative_to(root.resolve())
        except ValueError:
            self.fail(f"{path} does not resolve inside {root}")

    def assert_path_not_within(self, path: str | Path, root: Path) -> None:
        try:
            Path(path).resolve().relative_to(root.resolve())
        except ValueError:
            return
        self.fail(f"{path} unexpectedly resolves inside {root}")

    def make_dir_symlink_or_skip(self, target: Path, link: Path) -> None:
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            if os.name != "nt":
                self.skipTest(f"directory symlink unavailable: {exc}")
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(f"directory symlink/junction unavailable: {exc}; {result.stderr}")

    def test_dry_run_prompt_file_redacts_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            prompt_file = temp_dir / "prompt.txt"
            prompt_file.write_text("secret Claude prompt", encoding="utf-8")
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            launcher_args = (
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt-file",
                str(prompt_file),
                "--claude-bin",
                str(fake_claude),
                "--model",
                "claude-sonnet-5",
                "--effort",
                "xhigh",
                "--dry-run",
            )
            result = self.run_launcher(*launcher_args)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "dry_run")
            self.assertIn("<prompt redacted>", summary["command"])
            self.assertNotIn("secret Claude prompt", json.dumps(summary))
            self.assertEqual(summary["tools"], "")
            self.assertEqual(summary["permission_mode"], "dontAsk")
            self.assertTrue(summary["strict_mcp_config"])
            self.assertTrue(summary["safe_mode"])
            self.assertEqual(summary["schema_version"], "0.12")
            self.assertEqual(summary["requested_model"], "claude-sonnet-5")
            self.assertEqual(summary["requested_effort"], "xhigh")
            self.assertIn("claude-sonnet-5", summary["command"])
            self.assertEqual(summary["command"].count("--effort"), 1)
            self.assertEqual(summary["command"].count("xhigh"), 1)
            self.assertLess(summary["command"].index("--model"), summary["command"].index("--effort"))
            self.assertIn("--strict-mcp-config", summary["command"])
            self.assertIn("--safe-mode", summary["command"])
            self.assertIn("--disable-slash-commands", summary["command"])
            effective_args = list(launcher_args)
            if os.name == "nt" and Path(fake_claude).suffix.lower() in {".cmd", ".bat", ".ps1"}:
                effective_args.append("--allow-shell-wrapper")
            expected_launcher = [sys.executable, str(LAUNCHER.resolve()), *effective_args]
            expected_digest = hashlib.sha256(
                json.dumps(expected_launcher, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            self.assertEqual(summary["launcher_command_sha256"], expected_digest)
            self.assertEqual(summary["timeout_seconds"], 900)
            self.assertIn("--setting-sources", summary["command"])
            self.assertIn("--no-chrome", summary["command"])

    def test_prompt_file_preserves_crlf_bytes_in_hash_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            prompt_file = temp_dir / "prompt-crlf.txt"
            raw_prompt = b"alpha\r\nbeta\r\n"
            prompt_file.write_bytes(raw_prompt)
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace),
                "--out-dir", str(out_dir),
                "--prompt-file", str(prompt_file),
                "--claude-bin", str(fake_claude),
                "--dry-run",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["prompt_bytes"], len(raw_prompt))
            self.assertEqual(summary["prompt_sha256"], hashlib.sha256(raw_prompt).hexdigest())

    def test_effort_rejects_unknown_empty_and_case_variant_values_before_run(self) -> None:
        for effort in ("turbo", "", "XHIGH"):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                fake_claude = self.make_fake_claude(temp_dir)

                result = self.run_launcher(
                    "--cwd", str(workspace), "--prompt", "ok", "--claude-bin", str(fake_claude),
                    f"--effort={effort}", "--execute",
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("invalid choice", result.stderr)

    def test_config_error_receipt_preserves_requested_model_and_effort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--model", "claude-sonnet-5",
                "--effort", "high", "--run-depth", "1",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "config_error")
            self.assertEqual(summary["requested_model"], "claude-sonnet-5")
            self.assertEqual(summary["requested_effort"], "high")
            self.assertIsNone(summary["prompt_file"])
            self.assertIsNone(summary["prompt_sha256"])
            self.assertIsNone(summary["prompt_bytes"])

    def test_config_error_after_prompt_file_read_preserves_prompt_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            prompt_file = temp_dir / "prompt.txt"
            prompt_bytes = b"proof"
            prompt_file.write_bytes(prompt_bytes)
            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir),
                "--prompt-file", str(prompt_file), "--max-prompt-bytes", "4",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertIn("exceeding --max-prompt-bytes=4", summary["error"])
            self.assertEqual(summary["prompt_file"], str(prompt_file.resolve()))
            self.assertEqual(summary["prompt_sha256"], hashlib.sha256(prompt_bytes).hexdigest())
            self.assertEqual(summary["prompt_bytes"], len(prompt_bytes))

    def test_all_effort_values_and_omission_have_one_deterministic_mapping(self) -> None:
        for effort in (None, "low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                out_dir = workspace / "out"
                fake_claude = self.make_fake_claude(temp_dir)
                args = [
                    "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                    "--claude-bin", str(fake_claude), "--model", "claude-fable-5[1m]",
                ]
                if effort is not None:
                    args.extend(["--effort", effort])

                result = self.run_launcher(*args)

                self.assertEqual(result.returncode, 0, result.stderr)
                summary = self.read_summary(out_dir)
                self.assertEqual(summary["requested_model"], "claude-fable-5[1m]")
                self.assertEqual(summary["requested_effort"], effort)
                expected_count = 0 if effort is None else 1
                self.assertEqual(summary["command"].count("--effort"), expected_count)
                if effort is not None:
                    index = summary["command"].index("--effort")
                    self.assertEqual(summary["command"][index + 1], effort)

    def test_fake_success_and_failure_receipts_preserve_model_and_effort(self) -> None:
        for mode, expected_status in (("success_json", "succeeded"), ("auth_fail", "failed")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                out_dir = workspace / "out"
                fake_claude = self.make_fake_claude(temp_dir, mode)

                self.run_launcher(
                    "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                    "--claude-bin", str(fake_claude), "--model", "claude-fable-5[1m]",
                    "--effort", "xhigh", "--execute",
                )

                summary = self.read_summary(out_dir)
                self.assertEqual(summary["status"], expected_status)
                self.assertEqual(summary["requested_model"], "claude-fable-5[1m]")
                self.assertEqual(summary["requested_effort"], "xhigh")

    def test_stream_receipt_records_advertised_capabilities_without_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, "stream_capabilities")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["init_capabilities"]["plugins"], ["example-plugin"])
            self.assertEqual(summary["init_capabilities"]["skills"], ["example-skill"])
            self.assertNotIn("/private/path", json.dumps(summary))
            self.assertIn("customization metadata", " ".join(summary["policy_observations"]))

    def test_empty_tool_policy_fails_closed_on_advertised_or_used_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, "stream_tool_violation")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["error_kind"], "policy")
            self.assertEqual(summary["tool_names"], ["Read"])
            self.assertEqual(summary["tool_use_count"], 1)

    def test_execute_parses_json_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--output-format",
                "json",
                "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["target_cli_version"], "fake-claude 1.0")
            self.assertEqual(summary["session_id"], "session-basic")
            self.assertTrue(summary["descendant_cleanup_verified"])
            self.assertEqual(summary["usage"]["output_tokens"], 2)
            self.assertEqual(summary["total_cost_usd"], 0.001)
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "basic-ok")

    def test_expected_cli_version_mismatch_fails_before_target_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(root)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--expected-cli-version", "fake-claude 2.0",
                "--model", "claude-fable-5[1m]", "--effort", "xhigh", "--execute",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "version_probe")
            self.assertEqual(summary["target_cli_version"], "fake-claude 1.0")
            self.assertEqual(summary["requested_model"], "claude-fable-5[1m]")
            self.assertEqual(summary["requested_effort"], "xhigh")
            self.assertFalse((out_dir / "events.jsonl").exists())

    def test_execute_parses_stream_json_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="stream")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["session_id"], "session-stream")
            self.assertEqual(summary["usage"]["output_tokens"], 4)
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "stream-ok")

    def test_zero_exit_without_result_is_protocol_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="empty_success")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["error_kind"], "protocol")

    def test_invalid_json_with_zero_exit_is_protocol_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="invalid_json")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "protocol")
            self.assertIn("invalid JSON", " ".join(summary["parse_warnings"]))

    def test_invalid_utf8_target_output_is_protocol_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="invalid_utf8_output")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 65)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "protocol")

    def test_damaged_json_after_result_is_protocol_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="damaged_after_completion")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "protocol")

    def test_contradictory_result_cannot_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="contradictory_result")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "api")

    def test_unicode_output_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="unicode")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "café 東京")

    def test_windows_command_line_limit_fails_before_launch(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows command-line limit test")
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)
            prompt_file = temp_dir / "long-prompt.txt"
            prompt_file.write_text("x" * 40_000, encoding="utf-8")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt-file", str(prompt_file),
                "--max-prompt-bytes", "50000", "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("Windows command line", self.read_summary(out_dir)["error"])

    def test_provider_api_key_environment_is_scrubbed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="env_probe")
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = "test-openai-key"
            env["ANTHROPIC_API_KEY"] = "test-anthropic-key"
            env["ANTHROPIC_BASE_URL"] = "https://ambient.invalid"
            env["CLAUDE_CODE_OAUTH_TOKEN"] = "test-claude-oauth-token"

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute", env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "env=False;context=True")
            self.assertTrue(
                {
                    "ANTHROPIC_API_KEY",
                    "ANTHROPIC_BASE_URL",
                    "CLAUDE_CODE_OAUTH_TOKEN",
                    "OPENAI_API_KEY",
                }.issubset(summary["scrubbed_env"])
            )

    def test_oversized_prompt_fails_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "12345",
                "--max-prompt-bytes", "4", "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "config")

    def test_nul_prompt_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            prompt_file = temp_dir / "prompt.txt"
            prompt_file.write_text("before\x00after", encoding="utf-8")
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt-file", str(prompt_file),
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("NUL", self.read_summary(out_dir)["error"])

    def test_invalid_utf8_prompt_file_is_config_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            prompt_file = temp_dir / "prompt.txt"
            prompt_file.write_bytes(b"\xff\xfe")
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt-file", str(prompt_file),
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "config")

    def test_invalid_budget_is_rejected_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--max-budget-usd", "NaN", "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("finite positive decimal", self.read_summary(out_dir)["error"])

    def test_executable_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            executable_dir = temp_dir / "not-an-executable"
            executable_dir.mkdir()

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(executable_dir),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("not a file", self.read_summary(out_dir)["error"])

    def test_workspace_path_executable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            executable = workspace / ("claude.cmd" if os.name == "nt" else "claude")
            executable.write_text("@exit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n", encoding="utf-8")
            if os.name != "nt":
                executable.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(workspace) + os.pathsep + env.get("PATH", "")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", "claude", env=env,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("inside --cwd", self.read_summary(out_dir)["error"])

    def test_api_error_json_is_failed_even_with_zero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="network_fail")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["error_kind"], "api")

    def test_nonzero_exit_is_classified_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="auth_fail")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--execute",
            )

            self.assertEqual(result.returncode, 42)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["error_kind"], "auth")
            self.assertIn("api_key=<redacted>", summary["transcript_excerpt"])

    def test_timeout_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="timeout")

            started = time.monotonic()
            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                fake_claude,
                "--timeout-seconds",
                "1",
                "--execute",
            )

            self.assertLess(time.monotonic() - started, 20)
            self.assertEqual(result.returncode, 124)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "timeout")
            self.assertEqual(summary["status"], "failed")
            if os.name == "nt":
                self.assertEqual(summary["containment"], "job-object")
                self.assertTrue(summary["descendant_cleanup_verified"])
            time.sleep(0.5)

    def test_timeout_terminates_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            marker = temp_dir / "descendant-survived.txt"
            fake_claude = self.make_fake_claude(temp_dir, mode="descendant_timeout")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", str(marker),
                "--claude-bin", str(fake_claude), "--timeout-seconds", "1", "--execute",
            )

            self.assertEqual(result.returncode, 124)
            time.sleep(2.5)
            self.assertFalse(marker.exists(), "a descendant survived launcher timeout termination")

    def test_output_limit_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="large_output")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--max-output-bytes",
                "32",
                "--execute",
            )

            self.assertEqual(result.returncode, 125)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "output_limit")
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["max_output_bytes"], 32)
            if os.name == "nt":
                self.assertEqual(summary["containment"], "job-object")
                self.assertTrue(summary["descendant_cleanup_verified"])

    def test_output_limit_handles_a_large_line_without_newline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="large_output_no_newline")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--max-output-bytes", "1024", "--execute",
            )

            self.assertEqual(result.returncode, 125)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "output_limit")

    def test_output_limit_terminates_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            marker = temp_dir / "descendant-survived.txt"
            fake_claude = self.make_fake_claude(temp_dir, mode="descendant_output_limit")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", str(marker),
                "--claude-bin", str(fake_claude), "--max-output-bytes", "1024", "--execute",
            )

            self.assertEqual(result.returncode, 125)
            time.sleep(2.5)
            self.assertFalse(marker.exists(), "a descendant survived output-limit termination")

    def test_child_stdin_is_closed_even_when_parent_stdin_is_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, mode="stdin_eof")

            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(LAUNCHER),
                    "--cwd",
                    str(workspace),
                    "--out-dir",
                    str(out_dir),
                    "--prompt",
                    "ok",
                    "--claude-bin",
                    str(fake_claude),
                    "--allow-shell-wrapper",
                    "--timeout-seconds",
                    "5",
                    "--execute",
                ],
                cwd=str(ROOT),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=15)
                self.fail("launcher did not close child stdin while parent stdin remained open")

            stdout, stderr = proc.communicate(timeout=1)
            self.assertEqual(proc.returncode, 0, stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["session_id"], "session-stdin")
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "stdin-eof-ok")
            self.assertIn('"status": "succeeded"', stdout)

    def test_unsafe_flags_require_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--permission-mode",
                "bypassPermissions",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_broad_claude_tools_require_unsafe_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--tools",
                "all",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_mixed_broad_claude_tools_require_unsafe_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--tools",
                "*,Read",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_raw_claude_args_require_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--claude-arg=--verbose",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_raw_claude_args_require_unsafe_reason_even_when_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--claude-arg=--verbose",
                "--allow-raw-claude-arg",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_mcp_config_and_unsafe_reason_are_redacted_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)
            secret = "supersecretvalue123456"
            mcp_config = json.dumps({"mcpServers": {"probe": {"env": {"API_KEY": secret}}}})

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--mcp-config", mcp_config,
                "--allow-mcp-config", "--allow-unsafe", "--unsafe-reason", f"api_key={secret}",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            serialized = json.dumps(self.read_summary(out_dir))
            self.assertNotIn(secret, serialized)
            self.assertIn("<sensitive-arg redacted>", serialized)

    def test_raw_claude_arg_cannot_override_permission_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--claude-arg=--permission-mode=bypassPermissions",
                "--allow-raw-claude-arg", "--allow-unsafe", "--unsafe-reason", "negative test",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("launcher-controlled", self.read_summary(out_dir)["error"])

    def test_raw_claude_args_cannot_override_protocol_or_isolation(self) -> None:
        for raw_arg in (
            "--bare", "--tools=*", "--mcp-config={}", "--output-format=json",
            "--model=other", "--effort=max", "--dangerously-skip-permissions",
        ):
            with self.subTest(raw_arg=raw_arg), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                out_dir = workspace / "out"
                fake_claude = self.make_fake_claude(temp_dir)

                result = self.run_launcher(
                    "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                    "--claude-bin", str(fake_claude), f"--claude-arg={raw_arg}",
                    "--allow-raw-claude-arg", "--allow-unsafe", "--unsafe-reason", "negative test",
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("launcher-controlled", self.read_summary(out_dir)["error"])

    def test_allow_configured_mcp_requires_unsafe_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--allow-configured-mcp",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_explicit_mcp_config_requires_two_unsafe_acknowledgements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--mcp-config", '{"mcpServers":{}}',
                "--allow-mcp-config",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("--allow-unsafe", self.read_summary(out_dir)["error"])

    def test_allow_customizations_requires_unsafe_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--allow-customizations",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("--allow-unsafe", self.read_summary(out_dir)["error"])

    def test_depth_metadata_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--parent-run-id",
                "parent-001",
                "--run-depth",
                "1",
                "--max-depth",
                "2",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["parent_run_id"], "parent-001")
            self.assertEqual(summary["run_depth"], 1)
            self.assertEqual(summary["max_depth"], 2)

    def test_run_depth_requires_parent_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--run-depth",
                "1",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("--parent-run-id", summary["error"])

    def test_parent_run_id_requires_nonzero_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--parent-run-id",
                "parent-001",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("--run-depth", summary["error"])

    def test_run_depth_exceeding_max_depth_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--parent-run-id",
                "parent-001",
                "--run-depth",
                "2",
                "--max-depth",
                "1",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("exceeds --max-depth", summary["error"])

    def test_outside_out_dir_requires_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = temp_dir / "out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(out_dir.exists())
            summary = self.read_stderr_summary(result)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("--allow-outside-workspace-out-dir", summary["error"])

    def test_config_error_fallback_avoids_cairnspan_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            outside = temp_dir / "outside-artifacts"
            outside.mkdir()
            self.make_dir_symlink_or_skip(outside, workspace / ".cairnspan")
            out_dir = temp_dir / "outside-out"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_stderr_summary(result)
            self.assertEqual(summary["error_kind"], "config")
            self.assert_path_within(summary["out_dir"], workspace)
            self.assert_path_not_within(summary["out_dir"], outside)
            self.assertEqual(list(outside.iterdir()), [])

    def test_out_dir_cannot_target_git_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            (workspace / ".git" / "hooks").mkdir(parents=True)
            out_dir = workspace / ".git" / "hooks" / "cairnspan"
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(out_dir.exists())
            self.assertIn("control directory", self.read_stderr_summary(result)["error"])

    def test_nonempty_out_dir_requires_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            out_dir.mkdir()
            (out_dir / "previous.txt").write_text("old receipt", encoding="utf-8")
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse((out_dir / "cairnspan-summary.json").exists())
            summary = self.read_stderr_summary(result)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("--overwrite-out-dir", summary["error"])

    def test_out_dir_existing_file_rejected_even_with_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            out_dir.write_text("old receipt", encoding="utf-8")
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--overwrite-out-dir",
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(out_dir.read_text(encoding="utf-8"), "old receipt")
            summary = self.read_stderr_summary(result)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("not a directory", summary["error"])

    def test_overwrite_out_dir_allows_nonempty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            out_dir.mkdir()
            (out_dir / "previous.txt").write_text("old receipt", encoding="utf-8")
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--overwrite-out-dir",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "dry_run")
            self.assertTrue((out_dir / "previous.txt").exists())

    def test_overwrite_breaks_existing_receipt_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            out_dir.mkdir()
            outside = temp_dir / "outside.txt"
            outside.write_text("must-not-change", encoding="utf-8")
            os.link(outside, out_dir / "events.jsonl")
            fake_claude = self.make_fake_claude(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--overwrite-out-dir", "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "must-not-change")
            self.assertNotEqual((out_dir / "events.jsonl").read_text(encoding="utf-8"), "must-not-change")

    def test_default_run_ids_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            fake_claude = self.make_fake_claude(temp_dir)

            first = self.run_launcher(
                "--cwd",
                str(workspace),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--dry-run",
            )
            second = self.run_launcher(
                "--cwd",
                str(workspace),
                "--prompt",
                "ok",
                "--claude-bin",
                str(fake_claude),
                "--dry-run",
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            first_summary = json.loads(first.stdout)
            second_summary = json.loads(second.stdout)
            self.assertNotEqual(first_summary["out_dir"], second_summary["out_dir"])


    def test_conflicting_session_ids_fail_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, "conflicting_session_ids")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "protocol")
            self.assertEqual(summary["observed_session_ids"], ["session-one", "session-two"])

    def test_duplicate_terminal_events_fail_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, "duplicate_terminal")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["terminal_event_count"], 2)
            self.assertEqual(summary["error_kind"], "protocol")

    def test_reported_cost_above_edge_budget_fails_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, "over_cost")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--max-budget-usd", "0.05", "--execute",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "policy")

    def test_normal_target_exit_with_surviving_child_fails_and_kills_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            marker = temp_dir / "survivor.txt"
            fake_claude = self.make_fake_claude(temp_dir, "descendant_after_exit")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", str(marker),
                "--claude-bin", str(fake_claude), "--execute",
            )
            time.sleep(1)

            self.assertEqual(result.returncode, 125)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "process_leak")
            if os.name == "nt":
                self.assertEqual(summary["containment"], "job-object")
                self.assertTrue(summary["descendant_cleanup_verified"])
            self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "nt", "Windows Job Object grace behavior")
    def test_normal_target_exit_allows_short_lived_internal_child_to_finish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_claude = self.make_fake_claude(temp_dir, "descendant_graceful_after_exit")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["process_leak_details"], [])
            self.assertTrue(summary["descendant_cleanup_verified"])


    def test_write_tools_require_receipts_outside_target_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            fake_claude = self.make_fake_claude(root)
            inside = workspace / "receipts"
            rejected = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(inside), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--tools", "Read,Write",
                "--permission-mode", "acceptEdits", "--dry-run",
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("outside --cwd", self.read_summary(inside)["error"])

            outside = root / "receipts"
            accepted = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(outside), "--prompt", "ok",
                "--claude-bin", str(fake_claude), "--tools", "Read,Write",
                "--permission-mode", "acceptEdits", "--allow-outside-workspace-out-dir", "--dry-run",
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

    @unittest.skipUnless(
        sys.platform == "win32",
        "Replacement detection compares (st_dev, st_ino); NTFS does not "
        "immediately reuse a deleted file's file ID, but Linux filesystems can "
        "reassign the freed inode number to the replacement file, making the "
        "swap indistinguishable, so this check is Windows-only file-metadata "
        "semantics",
    )
    def test_capture_identity_detects_path_replacement(self) -> None:
        namespace = runpy.run_path(str(LAUNCHER))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.tmp"
            with path.open("x", encoding="utf-8") as handle:
                identity = namespace["capture_identity"](handle)
            path.unlink()
            path.write_text("replacement", encoding="utf-8")
            self.assertFalse(namespace["capture_path_matches"](path, identity))

    @unittest.skipUnless(os.name == "nt", "Windows fail-closed Job Object behavior")
    def test_job_attachment_failure_prevents_target_resume(self) -> None:
        namespace = runpy.run_path(str(LAUNCHER))
        fake_proc = type("FakeProc", (), {"pid": 1234})()
        stopped: list[object] = []
        replacements = {
            "create_windows_kill_job": lambda _proc: None,
            "stop_process": lambda proc, _job: stopped.append(proc),
        }
        with mock.patch.object(subprocess, "Popen", return_value=fake_proc), mock.patch.dict(
            namespace["run_process"].__globals__, replacements
        ):
            with self.assertRaises(namespace["ContainmentUnavailable"]):
                namespace["run_process"](["fake"], Path.cwd(), 1, 1, None, None, {})
        self.assertEqual(stopped, [fake_proc])


if __name__ == "__main__":
    unittest.main()
