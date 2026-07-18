from __future__ import annotations

import json
import base64
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "skills" / "cairnspan" / "scripts" / "scan_artifacts.py"


class ArtifactScannerTest(unittest.TestCase):
    def run_scanner(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCANNER), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_clean_redacted_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "cairnspan-summary.json").write_text(
                json.dumps(
                    {
                        "command": ["codex", "exec", "--json", "<prompt redacted>"],
                        "prompt_sha256": "0" * 64,
                        "out_dir": "<redacted-run-dir>",
                        "status": "succeeded",
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_scanner(str(fixture_dir))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("artifact-scan-clean", result.stdout)

    def test_canary_secret_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "transcript.log").write_text(
                "leaked CAIRNSPAN_CANARY_SECRET_DO_NOT_PUBLISH value",
                encoding="utf-8",
            )

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["findings"][0]["kind"], "canary_secret")
            self.assertEqual(payload["findings"][0]["sample"], "<secret>")

    def test_local_user_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "events.jsonl").write_text(
                '{"path":"C:\\\\Users\\\\exampleuser\\\\Documents\\\\Private Repo\\\\file.txt"}\n',
                encoding="utf-8",
            )

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["findings"][0]["kind"], "windows_user_path")
            self.assertEqual(payload["findings"][0]["sample"], "<local-path>")

    def test_bearer_token_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "transcript.log").write_text(
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
                encoding="utf-8",
            )

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            kinds = {finding["kind"] for finding in payload["findings"]}
            self.assertIn("bearer_token", kinds)

    def test_binary_file_with_canary_is_not_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00CAIRNSPAN_CANARY_SECRET")

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("canary_secret", {finding["kind"] for finding in payload["findings"]})

    def test_base64_encoded_canary_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            encoded = base64.b64encode(b"CAIRNSPAN_CANARY_SECRET_ENCODED").decode("ascii")
            (fixture_dir / "payload.json").write_text(json.dumps({"data": encoded}), encoding="utf-8")

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertIn("canary_secret", {finding["kind"] for finding in payload["findings"]})

    def test_percent_encoded_local_path_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "payload.txt").write_text(
                "C%3A%5CUsers%5Cprivate-user%5CDocuments%5Csecret.txt", encoding="utf-8"
            )

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertIn("windows_user_path", {finding["kind"] for finding in payload["findings"]})

    def test_line_split_canary_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "payload.txt").write_text(
                "CAIRNSPAN_\nCANARY_SECRET_SPLIT", encoding="utf-8"
            )

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertIn("canary_secret", {finding["kind"] for finding in payload["findings"]})

    def test_compressed_container_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "evidence.gz").write_bytes(b"\x1f\x8b" + b"opaque")

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["findings"][0]["kind"], "compressed_artifact")

    def test_oversized_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "large.log").write_bytes(b"x" * (5 * 1024 * 1024 + 1))

            result = self.run_scanner(str(fixture_dir), "--format", "json")

            self.assertEqual(result.returncode, 1, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["findings"][0]["kind"], "oversized_artifact")

    def test_missing_path_is_config_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"

            result = self.run_scanner(str(missing))

            self.assertEqual(result.returncode, 2)
            self.assertIn("artifact-scan-config-error", result.stderr)


if __name__ == "__main__":
    unittest.main()
