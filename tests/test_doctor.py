from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "skills" / "cairnspan" / "scripts" / "doctor.py"


class DoctorTest(unittest.TestCase):
    def run_doctor(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(DOCTOR), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

    def make_fake_executable(self, temp_dir: Path, name: str) -> Path:
        if os.name == "nt":
            path = temp_dir / f"{name}.cmd"
            if name == "codex":
                help_block = (
                    'if "%1"=="exec" if "%2"=="--help" (\r\n'
                    "  echo --model MODEL\r\n"
                    "  echo model_reasoning_effort low medium high xhigh max\r\n"
                    "  exit /b 0\r\n"
                    ")\r\n"
                )
            else:
                help_block = (
                    'if "%1"=="--help" (\r\n'
                    "  echo --model MODEL\r\n"
                    "  echo --effort LEVEL\r\n"
                    "  echo   ^(low, medium, high, xhigh, max^)\r\n"
                    "  exit /b 0\r\n"
                    ")\r\n"
                )
            path.write_text(
                "@echo off\r\n"
                f'if "%1"=="--version" echo fake-{name} 1.0\r\n'
                f'if "%1"=="--version" exit /b 0\r\n'
                f"{help_block}"
                "exit /b 0\r\n",
                encoding="utf-8",
            )
        else:
            path = temp_dir / name
            if name == "codex":
                help_block = (
                    'if [ "$1" = "exec" ] && [ "$2" = "--help" ]; then\n'
                    "  echo '--model MODEL'\n"
                    "  echo 'model_reasoning_effort low medium high xhigh max'\n"
                    "  exit 0\n"
                    "fi\n"
                )
            else:
                help_block = (
                    'if [ "$1" = "--help" ]; then\n'
                    "  echo '--model MODEL'\n"
                    "  echo '--effort LEVEL'\n"
                    "  echo '  (low, medium, high, xhigh, max)'\n"
                    "  exit 0\n"
                    "fi\n"
                )
            path.write_text(
                "#!/bin/sh\n"
                f'if [ "$1" = "--version" ]; then echo "fake-{name} 1.0"; exit 0; fi\n'
                f"{help_block}"
                "exit 0\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
        return path

    def make_fake_codex_with_features(self, temp_dir: Path, code_mode_host: bool, image_generation: bool) -> Path:
        if os.name == "nt":
            path = temp_dir / "codex-features.cmd"
            path.write_text(
                "@echo off\r\n"
                "if \"%1\"==\"--version\" (\r\n"
                "  echo fake-cli 1.0\r\n"
                "  exit /b 0\r\n"
                ")\r\n"
                "if \"%1\"==\"features\" (\r\n"
                f"  echo code_mode_host stable {str(code_mode_host).lower()}\r\n"
                f"  echo image_generation stable {str(image_generation).lower()}\r\n"
                "  exit /b 0\r\n"
                ")\r\n"
                "echo usage: fake cli\r\n"
                "exit /b 0\r\n",
                encoding="utf-8",
            )
        else:
            path = temp_dir / "codex-features"
            path.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "--version" ]; then echo "fake-cli 1.0"; exit 0; fi\n'
                'if [ "$1" = "features" ]; then\n'
                f"  echo 'code_mode_host stable {str(code_mode_host).lower()}'\n"
                f"  echo 'image_generation stable {str(image_generation).lower()}'\n"
                "  exit 0\n"
                "fi\n"
                "echo 'usage: fake cli'\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
        return path

    def make_silent_executable(self, temp_dir: Path, name: str) -> Path:
        if os.name == "nt":
            path = temp_dir / f"{name}.cmd"
            path.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
        else:
            path = temp_dir / name
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        return path

    def checks_by_name(self, payload: dict[str, object]) -> dict[str, dict[str, object]]:
        return {check["name"]: check for check in payload["checks"]}  # type: ignore[index]

    def test_doctor_passes_with_fake_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            codex = self.make_fake_executable(temp_dir, "codex")
            claude = self.make_fake_executable(temp_dir, "claude")

            result = self.run_doctor(
                "--cwd",
                str(workspace),
                "--codex-bin",
                str(codex),
                "--claude-bin",
                str(claude),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            checks = self.checks_by_name(payload)
            self.assertEqual(checks["cwd"]["status"], "ok")
            self.assertEqual(checks["codex_bin"]["status"], "ok")
            self.assertEqual(checks["claude_bin"]["status"], "ok")
            self.assertEqual(checks["codex_version"]["status"], "ok")
            self.assertEqual(checks["claude_version"]["status"], "ok")
            self.assertEqual(checks["codex_typed_model"]["status"], "ok")
            self.assertEqual(checks["codex_typed_effort"]["status"], "ok")
            self.assertEqual(checks["claude_typed_model"]["status"], "ok")
            self.assertEqual(checks["claude_typed_effort"]["status"], "ok")

    def test_doctor_reports_unsupported_typed_options_without_overclaiming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            codex = self.make_fake_codex_with_features(temp_dir, True, True)
            claude = self.make_fake_codex_with_features(temp_dir, True, True)

            result = self.run_doctor(
                "--cwd", str(workspace), "--codex-bin", str(codex),
                "--claude-bin", str(claude), "--format", "json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            checks = self.checks_by_name(json.loads(result.stdout))
            self.assertEqual(checks["codex_typed_model"]["detail"], "missing(--model)")
            self.assertEqual(
                checks["codex_typed_effort"]["detail"],
                "missing(model_reasoning_effort)",
            )
            self.assertEqual(checks["claude_typed_model"]["detail"], "missing(--model)")
            self.assertEqual(checks["claude_typed_effort"]["detail"], "missing(--effort)")

    def test_doctor_reports_unavailable_capability_as_runtime_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            missing = temp_dir / "missing-cli"

            result = self.run_doctor(
                "--cwd", str(workspace), "--codex-bin", str(missing),
                "--claude-bin", str(missing), "--format", "json",
            )

            self.assertEqual(result.returncode, 1)
            checks = self.checks_by_name(json.loads(result.stdout))
            for name in (
                "codex_version", "codex_typed_model", "codex_typed_effort",
                "claude_version", "claude_typed_model", "claude_typed_effort",
            ):
                self.assertEqual(checks[name]["detail"], "unknown(runtime_unverified)")

    def test_doctor_reports_silent_runtime_as_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            codex = self.make_silent_executable(temp_dir, "silent-codex")
            claude = self.make_silent_executable(temp_dir, "silent-claude")

            result = self.run_doctor(
                "--cwd", str(workspace), "--codex-bin", str(codex),
                "--claude-bin", str(claude), "--format", "json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            checks = self.checks_by_name(json.loads(result.stdout))
            for name in (
                "codex_version", "codex_typed_model", "codex_typed_effort",
                "claude_version", "claude_typed_model", "claude_typed_effort",
            ):
                self.assertEqual(checks[name]["detail"], "unknown(runtime_unverified)")

    def test_missing_cwd_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            codex = self.make_fake_executable(temp_dir, "codex")
            claude = self.make_fake_executable(temp_dir, "claude")

            result = self.run_doctor(
                "--cwd",
                str(temp_dir / "missing"),
                "--codex-bin",
                str(codex),
                "--claude-bin",
                str(claude),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            checks = self.checks_by_name(payload)
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(checks["cwd"]["status"], "fail")

    def test_outside_out_dir_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            codex = self.make_fake_executable(temp_dir, "codex")
            claude = self.make_fake_executable(temp_dir, "claude")

            result = self.run_doctor(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(temp_dir / "outside-out"),
                "--codex-bin",
                str(codex),
                "--claude-bin",
                str(claude),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            checks = self.checks_by_name(payload)
            self.assertEqual(payload["status"], "warn")
            self.assertEqual(checks["out_dir"]["status"], "warn")

    def test_output_file_path_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            out_file = workspace / "out"
            out_file.write_text("not a directory", encoding="utf-8")
            codex = self.make_fake_executable(temp_dir, "codex")
            claude = self.make_fake_executable(temp_dir, "claude")

            result = self.run_doctor(
                "--cwd",
                str(workspace),
                "--out-dir",
                str(out_file),
                "--codex-bin",
                str(codex),
                "--claude-bin",
                str(claude),
                "--format",
                "json",
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            checks = self.checks_by_name(payload)
            self.assertEqual(checks["out_dir"]["status"], "fail")

    def test_gitignore_check_uses_target_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            codex = self.make_fake_executable(temp_dir, "codex")
            claude = self.make_fake_executable(temp_dir, "claude")

            def gitignore_status() -> str:
                result = self.run_doctor(
                    "--cwd", str(workspace), "--codex-bin", str(codex),
                    "--claude-bin", str(claude), "--format", "json",
                )
                return self.checks_by_name(json.loads(result.stdout))["gitignore"]["status"]

            self.assertEqual(gitignore_status(), "warn")
            (workspace / ".gitignore").write_text(
                ".cairnspan/\n!.cairnspan/\n", encoding="utf-8"
            )
            self.assertEqual(gitignore_status(), "warn")
            (workspace / ".gitignore").write_text(".cairnspan/\n", encoding="utf-8")
            self.assertEqual(gitignore_status(), "ok")

    def test_image_tool_check_reports_disabled_code_mode_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            codex = self.make_fake_codex_with_features(temp_dir, False, True)
            claude = self.make_fake_executable(temp_dir, "claude")

            result = self.run_doctor(
                "--cwd", str(workspace), "--codex-bin", str(codex),
                "--claude-bin", str(claude), "--format", "json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            check = self.checks_by_name(json.loads(result.stdout))["codex_image_tools"]
            self.assertEqual(check["status"], "warn")
            self.assertEqual(check["detail"], "missing(code_mode_host)")

    def test_image_tool_check_does_not_overclaim_enabled_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            workspace = temp_dir / "workspace"
            workspace.mkdir()
            codex = self.make_fake_codex_with_features(temp_dir, True, True)
            claude = self.make_fake_executable(temp_dir, "claude")

            result = self.run_doctor(
                "--cwd", str(workspace), "--codex-bin", str(codex),
                "--claude-bin", str(claude), "--format", "json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            check = self.checks_by_name(json.loads(result.stdout))["codex_image_tools"]
            self.assertEqual(check["status"], "warn")
            self.assertEqual(check["detail"], "unknown(runtime_unverified)")


if __name__ == "__main__":
    unittest.main()
