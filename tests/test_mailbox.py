from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
MAILBOX_SCRIPT = ROOT / "skills" / "cairnspan" / "scripts" / "mailbox.py"


def load_mailbox() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cairnspan_mailbox", MAILBOX_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load mailbox module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def publish_request_in_process(mailbox_dir: str, payload: dict[str, object]) -> str:
    mailbox = load_mailbox()
    try:
        mailbox.write_request(Path(mailbox_dir), payload)
        return "published"
    except FileExistsError:
        return "exists"


class MailboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mailbox = load_mailbox()

    def base_request(self) -> dict[str, object]:
        return {
            "id": "req-001",
            "origin_agent": "codex",
            "target_agent": "claude-code",
            "created_at": "2026-07-08T21:00:00Z",
            "prompt_ref": "prompts/request.txt",
            "sandbox": "read-only",
            "status": "pending",
            "run_depth": 0,
            "max_depth": 1,
        }

    def base_response(self) -> dict[str, object]:
        return {
            "id": "resp-001",
            "request_id": "req-001",
            "origin_agent": "claude-code",
            "target_agent": "codex",
            "created_at": "2026-07-08T21:01:00Z",
            "status": "succeeded",
            "result_ref": "responses/resp-001/final.md",
        }

    def run_mailbox(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MAILBOX_SCRIPT), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_request_response_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request_path = self.mailbox.write_request(mailbox_dir, self.base_request())
            response_path = self.mailbox.write_response(mailbox_dir, self.base_response())

            self.assertEqual(request_path.name, "req-001.json")
            self.assertEqual(response_path.name, "resp-001.json")
            self.mailbox.validate_request(json.loads(request_path.read_text(encoding="utf-8")))
            self.mailbox.validate_response(json.loads(response_path.read_text(encoding="utf-8")))

    def test_request_requires_exactly_one_prompt_field(self) -> None:
        request = self.base_request()
        request["prompt"] = "inline"

        with self.assertRaises(self.mailbox.SchemaError):
            self.mailbox.validate_request(request)

        request.pop("prompt")
        request.pop("prompt_ref")
        with self.assertRaises(self.mailbox.SchemaError):
            self.mailbox.validate_request(request)

    def test_bad_id_cannot_escape_mailbox(self) -> None:
        request = self.base_request()
        request["id"] = "../escape"

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.mailbox.SchemaError):
                self.mailbox.write_request(Path(tmp) / ".cairnspan", request)

    def test_windows_unsafe_ids_are_rejected(self) -> None:
        for unsafe_id in ("NUL", "CON.txt", "req:stream"):
            request = self.base_request()
            request["id"] = unsafe_id
            with self.subTest(unsafe_id=unsafe_id), self.assertRaises(self.mailbox.SchemaError):
                self.mailbox.validate_request(request)

    def test_references_cannot_escape(self) -> None:
        for unsafe_ref in ("../secret.txt", "..\\secret.txt", "C:\\secret.txt", "/secret.txt"):
            request = self.base_request()
            request["prompt_ref"] = unsafe_ref
            with self.subTest(unsafe_ref=unsafe_ref), self.assertRaises(self.mailbox.SchemaError):
                self.mailbox.validate_request(request)

    def test_unknown_fields_are_rejected(self) -> None:
        request = self.base_request()
        request["permission_override"] = "danger-full-access"
        with self.assertRaises(self.mailbox.SchemaError):
            self.mailbox.validate_request(request)

    def test_depth_and_parent_must_be_consistent(self) -> None:
        child = self.base_request()
        child["run_depth"] = 1
        with self.assertRaises(self.mailbox.SchemaError):
            self.mailbox.validate_request(child)

        root = self.base_request()
        root["parent_run_id"] = "parent-001"
        with self.assertRaises(self.mailbox.SchemaError):
            self.mailbox.validate_request(root)

    def test_existing_message_is_not_clobbered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request = self.base_request()
            request_path = self.mailbox.write_request(mailbox_dir, request)
            original = request_path.read_bytes()

            with self.assertRaises(FileExistsError):
                self.mailbox.write_request(mailbox_dir, request)

            self.assertEqual(request_path.read_bytes(), original)

    def test_concurrent_writers_publish_exactly_one_message(self) -> None:
        for attempt in range(4):
            with self.subTest(attempt=attempt), tempfile.TemporaryDirectory() as tmp:
                mailbox_dir = Path(tmp) / ".cairnspan"
                request = self.base_request()

                def publish() -> str:
                    try:
                        self.mailbox.write_request(mailbox_dir, request)
                        return "published"
                    except FileExistsError:
                        return "exists"

                with ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(lambda _: publish(), range(8)))

                self.assertEqual(results.count("published"), 1)
                self.assertEqual(results.count("exists"), 7)
                request_path = mailbox_dir / "requests" / "req-001.json"
                self.assertEqual(json.loads(request_path.read_text(encoding="utf-8")), request)
                self.assertEqual(list((mailbox_dir / "requests").glob("*.tmp")), [])

    def test_concurrent_process_writers_publish_exactly_one_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request = self.base_request()
            with ProcessPoolExecutor(max_workers=6) as pool:
                futures = [pool.submit(publish_request_in_process, str(mailbox_dir), request) for _ in range(6)]
                results = [future.result(timeout=30) for future in futures]

            self.assertEqual(results.count("published"), 1)
            self.assertEqual(results.count("exists"), 5)
            request_path = mailbox_dir / "requests" / "req-001.json"
            self.assertEqual(json.loads(request_path.read_text(encoding="utf-8")), request)
            self.assertEqual(list((mailbox_dir / "requests").glob("*.tmp")), [])

    def test_response_status_requirements(self) -> None:
        response = self.base_response()
        response.pop("result_ref")
        with self.assertRaises(self.mailbox.SchemaError):
            self.mailbox.validate_response(response)

        failed = self.base_response()
        failed["status"] = "failed"
        failed.pop("result_ref")
        with self.assertRaises(self.mailbox.SchemaError):
            self.mailbox.validate_response(failed)

        failed["error"] = "target unavailable"
        self.mailbox.validate_response(failed)

    def test_cli_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request_path = self.mailbox.write_request(mailbox_dir, self.base_request())

            result = self.run_mailbox("validate", "request", str(request_path))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("mailbox-request-ok", result.stdout)

    def test_validate_exchange_links_agents_and_one_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request = self.base_request()
            request["prompt"] = "synthetic public request"
            request.pop("prompt_ref")
            response = self.base_response()
            response["final"] = "synthetic public response"
            response.pop("result_ref")
            request_path = self.mailbox.write_request(mailbox_dir, request)
            response_path = self.mailbox.write_response(mailbox_dir, response)

            result = self.mailbox.validate_exchange(mailbox_dir, request_path, response_path)

            self.assertEqual(result["status"], "valid")
            self.assertEqual(result["origin_agent"], "codex")
            self.assertEqual(result["target_agent"], "claude-code")
            self.assertEqual(len(result["request_sha256"]), 64)

    def test_validate_exchange_rejects_wrong_agent_reversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request_path = self.mailbox.write_request(mailbox_dir, self.base_request())
            response = self.base_response()
            response["origin_agent"] = "other-agent"
            response_path = self.mailbox.write_response(mailbox_dir, response)

            with self.assertRaises(self.mailbox.SchemaError):
                self.mailbox.validate_exchange(mailbox_dir, request_path, response_path)

    def test_validate_exchange_rejects_duplicate_terminal_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request = self.base_request()
            request["prompt"] = "synthetic public request"
            request.pop("prompt_ref")
            response = self.base_response()
            response["final"] = "first"
            response.pop("result_ref")
            request_path = self.mailbox.write_request(mailbox_dir, request)
            response_path = self.mailbox.write_response(mailbox_dir, response)
            duplicate = dict(response)
            duplicate["id"] = "resp-002"
            duplicate["final"] = "second"
            self.mailbox.write_response(mailbox_dir, duplicate)

            with self.assertRaises(self.mailbox.SchemaError):
                self.mailbox.validate_exchange(mailbox_dir, request_path, response_path)

    def test_validate_exchange_rejects_missing_result_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request_path = self.mailbox.write_request(mailbox_dir, self.base_request())
            response_path = self.mailbox.write_response(mailbox_dir, self.base_response())

            with self.assertRaises((FileNotFoundError, self.mailbox.SchemaError)):
                self.mailbox.validate_exchange(mailbox_dir, request_path, response_path)

    def test_cli_validate_exchange_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mailbox_dir = Path(tmp) / ".cairnspan"
            request_path = self.mailbox.write_request(mailbox_dir, self.base_request())
            response = self.base_response()
            response["request_id"] = "req-other"
            response_path = self.mailbox.write_response(mailbox_dir, response)

            result = self.run_mailbox(
                "validate-exchange",
                "--mailbox-dir", str(mailbox_dir),
                "--request", str(request_path),
                "--response", str(response_path),
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("mailbox-exchange-invalid", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
