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
LAUNCHER = ROOT / "skills" / "cairnspan" / "scripts" / "start_codex_session.py"


class LauncherTest(unittest.TestCase):
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
                if value == "--codex-bin" and Path(args[index + 1]).suffix.lower() in {".cmd", ".bat", ".ps1"}:
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

    def make_fake_codex(self, temp_dir: Path, mode: str = "success") -> Path:
        script = temp_dir / "fake_codex.py"
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
                    print("fake-codex 1.0")
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
                    child_code = f"import time; from pathlib import Path; time.sleep(5); Path({{marker!r}}).write_text('survived', encoding='utf-8')"
                    subprocess.Popen([sys.executable, "-c", child_code])
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-descendant"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "must-not-pass"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "allowlisted_cmd_after_exit":
                    subprocess.Popen(
                        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/q", "/c", "for /L %i in (1,0,2) do @rem"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-internal-cmd"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "internal-cmd-ok"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "auth_fail":
                    print("Authentication failed: api_key=secret-value", file=sys.stderr)
                    raise SystemExit(42)
                if mode == "network_fail":
                    print("failed to connect to websocket: IO error: An attempt was made to access a socket in a way forbidden by its access permissions. (os error 10013), url: wss://api.openai.com/v1/responses", file=sys.stderr)
                    raise SystemExit(1)
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
                    sys.stdout.buffer.write(b'{{"type":"thread.started","thread_id":"thread-bytes"}}' + bytes([10, 255]))
                    sys.stdout.buffer.flush()
                    raise SystemExit(0)
                if mode == "damaged_after_completion":
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-damaged"}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "must-not-pass"}}}}))
                    print("{{")
                    raise SystemExit(0)
                if mode == "turn_failed_zero":
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-failed"}}))
                    print(json.dumps({{"type": "turn.failed"}}))
                    raise SystemExit(0)
                if mode == "unicode":
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-unicode"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "café 東京"}}}}, ensure_ascii=False))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "env_probe":
                    api_keys_present = any(name in os.environ for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"))
                    run_context_present = bool(os.environ.get("CAIRNSPAN_RUN_ID"))
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-env"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": f"env={{api_keys_present}};context={{run_context_present}}"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "stdin_eof":
                    sys.stdin.read()
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-stdin"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "stdin-eof-ok"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "image_prompt_boundary":
                    stdin_text = sys.stdin.read()
                    separator_ok = "--" in sys.argv and sys.argv.index("--") == len(sys.argv) - 2
                    image_ok = "--image" in sys.argv and sys.argv[-1] == "attachment-prompt"
                    result = f"boundary={{separator_ok and image_ok and stdin_text == ''}}"
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-image-boundary"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": result}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "image_tool_missing":
                    result = "Unable to save the image: the built-in image tool failed because its code-mode host is missing"
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-image-missing"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": result}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "image_generation_success":
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-image-success"}}))
                    print(json.dumps({{"type": "image_generation", "result": "synthetic.png"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "image-generated"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "alt_events":
                    print(json.dumps({{"type": "thread.started", "id": "thread-alt"}}))
                    print(json.dumps({{"type": "message", "role": "assistant", "content": [{{"type": "text", "text": "alt-ok"}}]}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "tool_use":
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-tool"}}))
                    print(json.dumps({{"type": "item.completed", "item": {{"type": "command_execution", "command": "whoami"}}}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "must-not-pass"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "conflicting_thread_ids":
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-one"}}))
                    print(json.dumps({{"type": "turn.started", "thread_id": "thread-two"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "must-not-pass"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                if mode == "duplicate_terminal":
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-terminal"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "must-not-pass"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                print(json.dumps({{"thread_id": "thread-basic", "type": "turn.started"}}))
                print(json.dumps({{"item": {{"type": "agent_message", "text": "basic-ok"}}}}))
                print(json.dumps({{"type": "turn.completed", "usage": {{"input_tokens": 1, "output_tokens": 2}}}}))
                raise SystemExit(0)
                """
            ),
            encoding="utf-8",
        )
        if os.name == "nt":
            wrapper = temp_dir / "fake_codex.cmd"
            wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
        else:
            wrapper = temp_dir / "fake_codex"
            wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
        return wrapper

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

    def make_file_symlink_or_skip(self, target: Path, link: Path) -> None:
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"file symlink unavailable: {exc}")

    def make_python_exec_fake(self, workspace: Path, mode: str) -> str:
        script = workspace / "exec"
        script.write_text(
            textwrap.dedent(
                f"""
                import sys
                import time
                import json

                mode = {mode!r}
                if mode == "timeout":
                    time.sleep(5)
                    raise SystemExit(0)
                if mode == "stdin_eof":
                    sys.stdin.read()
                    print(json.dumps({{"type": "thread.started", "thread_id": "thread-stdin"}}))
                    print(json.dumps({{"item": {{"type": "agent_message", "text": "stdin-eof-ok"}}}}))
                    print(json.dumps({{"type": "turn.completed"}}))
                    raise SystemExit(0)
                raise SystemExit(1)
                """
            ),
            encoding="utf-8",
        )
        return sys.executable

    def test_dry_run_prompt_file_redacts_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            prompt_file = temp_dir / "prompt.txt"
            prompt_file.write_text("secret prompt text", encoding="utf-8")
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            launcher_args = (
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt-file",
                str(prompt_file),
                "--codex-bin",
                str(fake_codex),
                "--model",
                "gpt-5.6-sol",
                "--effort",
                "xhigh",
                "--dry-run",
            )
            result = self.run_launcher(*launcher_args)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "dry_run")
            self.assertIn("<prompt redacted>", summary["command"])
            self.assertNotIn("secret prompt text", json.dumps(summary))
            self.assertEqual(summary["prompt_file"], str(prompt_file.resolve()))
            self.assertEqual(summary["schema_version"], "0.14")
            self.assertEqual(summary["requested_model"], "gpt-5.6-sol")
            self.assertEqual(summary["requested_effort"], "xhigh")
            self.assertEqual(summary["command"].count("--model"), 1)
            self.assertEqual(summary["command"].count('model_reasoning_effort="xhigh"'), 1)
            effective_args = list(launcher_args)
            if os.name == "nt" and Path(fake_codex).suffix.lower() in {".cmd", ".bat", ".ps1"}:
                effective_args.append("--allow-shell-wrapper")
            expected_launcher = [sys.executable, str(LAUNCHER.resolve()), *effective_args]
            expected_digest = hashlib.sha256(
                json.dumps(expected_launcher, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            self.assertEqual(summary["launcher_command_sha256"], expected_digest)

    def test_prompt_file_preserves_crlf_bytes_in_hash_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            prompt_file = temp_dir / "prompt-crlf.txt"
            raw_prompt = b"alpha\r\nbeta\r\n"
            prompt_file.write_bytes(raw_prompt)
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace),
                "--out-dir", str(out_dir),
                "--prompt-file", str(prompt_file),
                "--codex-bin", str(fake_codex),
                "--dry-run",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["prompt_bytes"], len(raw_prompt))
            self.assertEqual(summary["prompt_sha256"], hashlib.sha256(raw_prompt).hexdigest())
            self.assertEqual(summary["timeout_seconds"], 900)

    def test_effort_rejects_unknown_empty_and_case_variant_values_before_run(self) -> None:
        for effort in ("turbo", "", "XHIGH"):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                fake_codex = self.make_fake_codex(temp_dir)

                result = self.run_launcher(
                    "--cwd", str(workspace), "--prompt", "ok", "--codex-bin", str(fake_codex),
                    f"--effort={effort}", "--execute",
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("invalid choice", result.stderr)

    def test_config_error_receipt_preserves_requested_model_and_effort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            missing = temp_dir / "missing"
            out_dir = temp_dir / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(missing), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--allow-outside-workspace-out-dir",
                "--model", "gpt-5.6-sol", "--effort", "high",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "config_error")
            self.assertEqual(summary["requested_model"], "gpt-5.6-sol")
            self.assertEqual(summary["requested_effort"], "high")

    def test_all_effort_values_and_omission_have_one_deterministic_mapping(self) -> None:
        for effort in (None, "low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                out_dir = workspace / "out"
                fake_codex = self.make_fake_codex(temp_dir)
                args = [
                    "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                    "--codex-bin", str(fake_codex), "--model", "gpt-5.6-sol",
                ]
                if effort is not None:
                    args.extend(["--effort", effort])

                result = self.run_launcher(*args)

                self.assertEqual(result.returncode, 0, result.stderr)
                summary = self.read_summary(out_dir)
                self.assertEqual(summary["requested_model"], "gpt-5.6-sol")
                self.assertEqual(summary["requested_effort"], effort)
                mappings = [
                    value for value in summary["command"]
                    if value.startswith("model_reasoning_effort=")
                ]
                expected = [] if effort is None else [f'model_reasoning_effort="{effort}"']
                self.assertEqual(mappings, expected)

    def test_fake_success_and_failure_receipts_preserve_model_and_effort(self) -> None:
        for mode, expected_status in (("success", "succeeded"), ("auth_fail", "failed")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                out_dir = workspace / "out"
                fake_codex = self.make_fake_codex(temp_dir, mode)

                self.run_launcher(
                    "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                    "--codex-bin", str(fake_codex), "--model", "gpt-5.6-sol",
                    "--effort", "xhigh", "--execute",
                )

                summary = self.read_summary(out_dir)
                self.assertEqual(summary["status"], expected_status)
                self.assertEqual(summary["requested_model"], "gpt-5.6-sol")
                self.assertEqual(summary["requested_effort"], "xhigh")

    def test_strict_isolation_does_not_duplicate_typed_effort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--effort", "max", "--strict-isolation",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            command = self.read_summary(out_dir)["command"]
            self.assertEqual(command.count('model_reasoning_effort="max"'), 1)

    def test_typed_effort_cannot_be_combined_with_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--effort", "high", "--profile", "other",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("launcher-owned", self.read_summary(out_dir)["error"])

    def test_missing_cwd_fails_without_creating_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            missing = temp_dir / "missing"
            out_dir = temp_dir / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(missing),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--allow-outside-workspace-out-dir",
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(missing.exists())
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "config_error")
            self.assertEqual(summary["error_kind"], "config")

    def test_execute_parses_basic_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["target_cli_version"], "fake-codex 1.0")
            self.assertEqual(summary["thread_id"], "thread-basic")
            self.assertTrue(summary["descendant_cleanup_verified"])
            self.assertEqual(summary["usage"]["output_tokens"], 2)
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "basic-ok")

    def test_expected_cli_version_mismatch_fails_before_target_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(root)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--expected-cli-version", "fake-codex 2.0",
                "--model", "gpt-5.6-sol", "--effort", "xhigh", "--execute",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "version_probe")
            self.assertEqual(summary["target_cli_version"], "fake-codex 1.0")
            self.assertEqual(summary["requested_model"], "gpt-5.6-sol")
            self.assertEqual(summary["requested_effort"], "xhigh")
            self.assertFalse((out_dir / "events.jsonl").exists())

    def test_execute_parses_alternate_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="alt_events")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["thread_id"], "thread-alt")
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "alt-ok")

    def test_zero_exit_without_completion_is_protocol_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="empty_success")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
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
            fake_codex = self.make_fake_codex(temp_dir, mode="invalid_json")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
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
            fake_codex = self.make_fake_codex(temp_dir, mode="invalid_utf8_output")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
            )

            self.assertEqual(result.returncode, 65)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "protocol")

    def test_damaged_json_after_completion_is_protocol_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="damaged_after_completion")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "protocol")

    def test_turn_failed_event_cannot_succeed_with_zero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="turn_failed_zero")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "target_failed")

    def test_unicode_output_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="unicode")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
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
            fake_codex = self.make_fake_codex(temp_dir)
            prompt_file = temp_dir / "long-prompt.txt"
            prompt_file.write_text("x" * 40_000, encoding="utf-8")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt-file", str(prompt_file),
                "--max-prompt-bytes", "50000", "--codex-bin", str(fake_codex), "--execute",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("Windows command line", self.read_summary(out_dir)["error"])

    def test_provider_api_key_environment_is_scrubbed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="env_probe")
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = "test-openai-key"
            env["ANTHROPIC_API_KEY"] = "test-anthropic-key"
            env["CLAUDE_CODE_OAUTH_TOKEN"] = "test-claude-oauth-token"

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute", env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "env=False;context=True")
            self.assertEqual(
                summary["scrubbed_env"],
                ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY"],
            )

    def test_oversized_prompt_fails_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "12345",
                "--max-prompt-bytes", "4", "--codex-bin", str(fake_codex), "--execute",
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt-file", str(prompt_file),
                "--codex-bin", str(fake_codex), "--execute",
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt-file", str(prompt_file),
                "--codex-bin", str(fake_codex), "--execute",
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.read_summary(out_dir)["error_kind"], "config")

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
                "--codex-bin", str(executable_dir),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("not a file", self.read_summary(out_dir)["error"])

    def test_workspace_path_executable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            executable = workspace / ("codex.cmd" if os.name == "nt" else "codex")
            executable.write_text("@exit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n", encoding="utf-8")
            if os.name != "nt":
                executable.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(workspace) + os.pathsep + env.get("PATH", "")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", "codex", env=env,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("inside --cwd", self.read_summary(out_dir)["error"])

    def test_nonzero_exit_is_classified_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="auth_fail")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_python_exec_fake(workspace, mode="timeout")

            started = time.monotonic()
            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                fake_codex,
                "--timeout-seconds",
                "1",
                "--execute",
            )

            self.assertLess(time.monotonic() - started, 10)
            self.assertEqual(result.returncode, 124)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "timeout")
            self.assertEqual(summary["status"], "failed")
            if os.name == "nt":
                self.assertEqual(summary["containment"], "job-object")
                self.assertTrue(summary["descendant_cleanup_verified"])

    def test_timeout_terminates_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            marker = temp_dir / "descendant-survived.txt"
            fake_codex = self.make_fake_codex(temp_dir, mode="descendant_timeout")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", str(marker),
                "--codex-bin", str(fake_codex), "--timeout-seconds", "1", "--execute",
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
            fake_codex = self.make_fake_codex(temp_dir, mode="large_output")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir, mode="large_output_no_newline")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--max-output-bytes", "1024", "--execute",
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
            fake_codex = self.make_fake_codex(temp_dir, mode="descendant_output_limit")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", str(marker),
                "--codex-bin", str(fake_codex), "--max-output-bytes", "1024", "--execute",
            )

            self.assertEqual(result.returncode, 125)
            time.sleep(2.5)
            self.assertFalse(marker.exists(), "a descendant survived output-limit termination")

    def test_network_socket_failure_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, mode="network_fail")

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "network")
            self.assertEqual(summary["status"], "failed")

    def test_child_stdin_is_closed_even_when_parent_stdin_is_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_python_exec_fake(workspace, mode="stdin_eof")

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
                    "--codex-bin",
                    str(fake_codex),
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
            self.assertEqual(summary["thread_id"], "thread-stdin")
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "stdin-eof-ok")
            self.assertIn('"status": "succeeded"', stdout)

    def test_unsafe_flags_require_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--sandbox",
                "danger-full-access",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_raw_codex_args_require_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--codex-arg=--search",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("--allow-raw-codex-arg", summary["error"])

    def test_raw_codex_args_require_unsafe_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--codex-arg=--search",
                "--allow-raw-codex-arg",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")

    def test_raw_codex_args_and_unsafe_reason_are_redacted_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)
            secret = "supersecretvalue123456"

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), f"--codex-arg=api_key={secret}",
                "--allow-raw-codex-arg", "--allow-unsafe", "--unsafe-reason", f"api_key={secret}",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            serialized = json.dumps(self.read_summary(out_dir))
            self.assertNotIn(secret, serialized)
            self.assertIn("<raw-arg redacted>", serialized)

    def test_raw_codex_arg_cannot_override_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--codex-arg=--sandbox=danger-full-access",
                "--allow-raw-codex-arg", "--allow-unsafe", "--unsafe-reason", "negative test",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("launcher-controlled", self.read_summary(out_dir)["error"])

    def test_raw_codex_args_cannot_override_protocol_or_isolation(self) -> None:
        for raw_arg in (
            "--json", "--config=model=other", "--enable=shell_tool",
            "--dangerously-bypass-approvals-and-sandbox", "--model=other", "--profile=other",
            "-sworkspace-write", "-ck=v", "-Cother", "-mother", "-pother",
        ):
            with self.subTest(raw_arg=raw_arg), tempfile.TemporaryDirectory() as tmp:
                temp_dir = Path(tmp)
                workspace = temp_dir / "workspace"
                workspace.mkdir()
                out_dir = workspace / "out"
                fake_codex = self.make_fake_codex(temp_dir)

                result = self.run_launcher(
                    "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                    "--codex-bin", str(fake_codex), f"--codex-arg={raw_arg}",
                    "--allow-raw-codex-arg", "--allow-unsafe", "--unsafe-reason", "negative test",
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("launcher-controlled", self.read_summary(out_dir)["error"])

    def test_depth_metadata_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_stderr_summary(result)
            self.assertEqual(summary["error_kind"], "config")
            self.assert_path_within(summary["out_dir"], workspace)
            self.assert_path_not_within(summary["out_dir"], outside)
            self.assertEqual(list(outside.iterdir()), [])

    def test_nonempty_out_dir_requires_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            out_dir.mkdir()
            (out_dir / "previous.txt").write_text("old receipt", encoding="utf-8")
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
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
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--overwrite-out-dir", "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "must-not-change")
            self.assertNotEqual((out_dir / "events.jsonl").read_text(encoding="utf-8"), "must-not-change")

    def test_out_dir_cannot_target_git_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            (workspace / ".git" / "hooks").mkdir(parents=True)
            out_dir = workspace / ".git" / "hooks" / "cairnspan"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(out_dir.exists())
            self.assertIn("control directory", self.read_stderr_summary(result)["error"])

    def test_workspace_relative_image_is_resolved_inside_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            image = workspace / "probe.png"
            image.write_bytes(b"probe image bytes")
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--image",
                "probe.png",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertIn(str(image.resolve()), summary["command"])

    def test_image_attachment_delivers_positional_prompt_with_closed_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            image = workspace / "probe.png"
            image.write_bytes(b"probe image bytes")
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, "image_prompt_boundary")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir),
                "--prompt", "attachment-prompt", "--codex-bin", str(fake_codex),
                "--image", "probe.png", "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual((out_dir / "final.md").read_text(encoding="utf-8"), "boundary=True")
            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["command"][-2], "--")

    def test_image_tool_host_failure_is_not_accepted_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, "image_tool_missing")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "generate",
                "--codex-bin", str(fake_codex), "--require-image-capability", "image-generation", "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["error_kind"], "image_tool_unavailable")
            self.assertEqual(summary["codex_image_tools"], "missing(code_mode_host)")

    def test_required_image_generation_must_be_observed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, "image_generation_success")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "generate",
                "--codex-bin", str(fake_codex), "--require-image-capability", "image-generation", "--execute",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["codex_image_tools"], "ok(image-generation)")
            self.assertIn("image_generation", summary["tool_names"])

    def test_strict_isolation_allows_validated_input_image_without_enabling_image_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            image = workspace / "probe.png"
            image.write_bytes(b"probe image bytes")
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--image", "probe.png",
                "--strict-isolation", "--require-no-tool-use", "--dry-run",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertIn(str(image.resolve()), summary["command"])
            self.assertIn("image_generation", summary["disabled_features"])
            self.assertTrue(summary["strict_isolation"])
            self.assertEqual(summary["command"][-2], "--")

    def test_missing_image_fails_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--image",
                str(workspace / "missing.png"),
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("Image file does not exist", summary["error"])

    def test_outside_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            outside_image = temp_dir / "outside.png"
            outside_image.write_bytes(b"outside image bytes")
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--image",
                str(outside_image),
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("inside --cwd", summary["error"])

    def test_image_parent_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            outside_image = temp_dir / "outside.png"
            outside_image.write_bytes(b"outside image bytes")
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--image",
                str(Path("..") / "outside.png"),
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("inside --cwd", summary["error"])

    def test_image_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            image_dir = workspace / "image-dir"
            image_dir.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--image",
                str(image_dir),
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("not a file", summary["error"])

    def test_image_symlink_to_outside_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            outside_image = temp_dir / "outside.png"
            outside_image.write_bytes(b"outside image bytes")
            linked_image = workspace / "linked.png"
            self.make_file_symlink_or_skip(outside_image, linked_image)
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir)

            result = self.run_launcher(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_dir),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--image",
                "linked.png",
            )

            self.assertEqual(result.returncode, 2)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "config")
            self.assertIn("inside --cwd", summary["error"])

    def test_default_run_ids_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            fake_codex = self.make_fake_codex(temp_dir)

            first = self.run_launcher(
                "--cwd",
                str(workspace),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--dry-run",
            )
            second = self.run_launcher(
                "--cwd",
                str(workspace),
                "--prompt",
                "ok",
                "--codex-bin",
                str(fake_codex),
                "--dry-run",
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            first_summary = json.loads(first.stdout)
            second_summary = json.loads(second.stdout)
            self.assertNotEqual(first_summary["out_dir"], second_summary["out_dir"])


    def test_strict_isolation_disables_discovered_mcp_and_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            codex_home = temp_dir / "codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                '[mcp_servers.alpha]\ncommand = "fake"\n', encoding="utf-8"
            )
            fake_codex = self.make_fake_codex(temp_dir)
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--strict-isolation", "--dry-run", env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertTrue(summary["strict_isolation"])
            self.assertEqual(summary["ignored_mcp_servers"], ["alpha"])
            rendered = " ".join(summary["command"])
            self.assertIn("--ignore-user-config", summary["command"])
            self.assertIn("--ignore-rules", summary["command"])
            self.assertIn("--ephemeral", summary["command"])
            self.assertIn("--strict-config", summary["command"])
            self.assertIn("plugins", summary["disabled_features"])
            self.assertIn("shell_tool", summary["disabled_features"])
            self.assertIn("shell_snapshot", summary["disabled_features"])
            self.assertIn("apps._default.enabled=false", rendered)
            self.assertNotIn('mcp_servers."alpha".enabled=false', rendered)

    def test_required_no_tool_use_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, "tool_use")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--require-no-tool-use", "--execute",
            )

            self.assertIn(result.returncode, (1, 125))
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "policy")
            self.assertGreater(summary["tool_use_count"], 0)

    def test_conflicting_thread_ids_fail_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, "conflicting_thread_ids")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "protocol")
            self.assertEqual(summary["observed_thread_ids"], ["thread-one", "thread-two"])

    def test_duplicate_terminal_events_fail_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, "duplicate_terminal")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--execute",
            )

            self.assertEqual(result.returncode, 1)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["terminal_event_count"], 2)
            self.assertEqual(summary["error_kind"], "protocol")

    @unittest.skipUnless(
        sys.platform == "win32",
        "Killing a descendant that survives normal target exit relies on "
        "Windows Job Object kill-on-close containment; POSIX process-group "
        "cleanup cannot guarantee termination of an escaped descendant, so the "
        "surviving child outlives the launcher off Windows",
    )
    def test_normal_target_exit_with_surviving_child_fails_and_kills_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            marker = temp_dir / "survivor.txt"
            fake_codex = self.make_fake_codex(temp_dir, "descendant_after_exit")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", str(marker),
                "--codex-bin", str(fake_codex), "--execute",
            )
            time.sleep(6)

            self.assertEqual(result.returncode, 125)
            summary = self.read_summary(out_dir)
            self.assertEqual(summary["error_kind"], "process_leak")
            if os.name == "nt":
                self.assertEqual(summary["containment"], "job-object")
                self.assertTrue(summary["descendant_cleanup_verified"])
            self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "nt", "Codex internal cmd.exe cleanup is Windows-specific")
    def test_strict_no_tool_run_rejects_internal_cmd_descendant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_dir = workspace / "out"
            fake_codex = self.make_fake_codex(temp_dir, "allowlisted_cmd_after_exit")

            result = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(out_dir), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--strict-isolation", "--require-no-tool-use", "--execute",
            )

            self.assertEqual(result.returncode, 125, result.stderr)
            summary = self.read_summary(out_dir)
            self.assertTrue(summary["descendant_cleanup_verified"])
            self.assertEqual(summary["containment"], "job-object")
            self.assertEqual({item["name"].lower() for item in summary["process_leak_details"]}, {"cmd.exe"})
            self.assertEqual(summary["tool_use_count"], 0)
            self.assertEqual(summary["error_kind"], "process_leak")


    def test_workspace_write_requires_receipts_outside_target_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            fake_codex = self.make_fake_codex(root)
            inside = workspace / "receipts"
            rejected = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(inside), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--sandbox", "workspace-write", "--dry-run",
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("outside --cwd", self.read_summary(inside)["error"])

            outside = root / "receipts"
            accepted = self.run_launcher(
                "--cwd", str(workspace), "--out-dir", str(outside), "--prompt", "ok",
                "--codex-bin", str(fake_codex), "--sandbox", "workspace-write",
                "--allow-outside-workspace-out-dir", "--dry-run",
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
