from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
SCRIPT = SCRIPTS / "synthetic_probe_case.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli_version import probe_cli_version, version_probe_env  # noqa: E402
from synthetic_probe_case import command_sha256, sha256_file, synthetic_view_png  # noqa: E402


class SyntheticProbeCaseTest(unittest.TestCase):
    def run_case(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

    def prepare(self, root: Path, probe: str) -> dict:
        case_root = root / probe
        version = probe_cli_version(Path(sys.executable), root, version_probe_env())
        result = self.run_case(
            "prepare",
            "--case-root", str(case_root),
            "--probe", probe,
            "--codex-bin", sys.executable,
            "--expected-cli-version", version,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((case_root / "proposal-plan.json").read_text(encoding="utf-8"))

    def target_command(self, plan: dict) -> list[str]:
        command = [plan["executable"]["path"], "exec", "--json", "--sandbox", plan["policy"]["sandbox"]]
        if plan["request"]["model"]:
            command.extend(["--model", plan["request"]["model"]])
        if plan["request"]["effort"]:
            command.extend(["-c", f'model_reasoning_effort="{plan["request"]["effort"]}"'])
        command.append("<prompt redacted>")
        return command

    def base_summary(self, plan: dict, *, dry_run: bool) -> dict:
        root = Path(plan["paths"]["dry_run_receipts" if dry_run else "receipts"])
        return {
            "schema_version": "0.14",
            "run_id": f"{'dry' if dry_run else 'live'}-{plan['proposal_id']}",
            "parent_run_id": None,
            "run_depth": 0,
            "max_depth": 1,
            "origin_agent": "cairnspan.parent",
            "target_agent": "codex",
            "target_workspace": plan["paths"]["workspace"],
            "cwd": plan["paths"]["workspace"],
            "command": self.target_command(plan),
            "launcher_command_sha256": plan["dry_run_command_sha256" if dry_run else "execute_command_sha256"],
            "codex_bin_resolved": plan["executable"]["path"],
            "target_cli_version": plan["executable"]["version"],
            "expected_cli_version": plan["executable"]["version"],
            "dry_run": dry_run,
            "status": "dry_run" if dry_run else "succeeded",
            "sandbox": plan["policy"]["sandbox"],
            "requested_model": plan["request"]["model"],
            "requested_effort": plan["request"]["effort"],
            "requested_image_capability": plan["policy"]["required_image_capability"],
            "prompt_file": plan["paths"]["prompt"],
            "prompt_sha256": plan["request"]["prompt_sha256"],
            "out_dir": str(root),
            "events_log": str(root / "events.jsonl"),
            "transcript_log": str(root / "transcript.log"),
            "final_message": str(root / "final.md"),
            "summary_file": str(root / "cairnspan-summary.json"),
            "timeout_seconds": plan["policy"]["timeout_seconds"],
            "max_output_bytes": plan["policy"]["max_output_bytes"],
            "return_code": None if dry_run else 0,
            "thread_id": None if dry_run else f"thread-{plan['proposal_id']}",
            "observed_thread_ids": [] if dry_run else [f"thread-{plan['proposal_id']}"],
            "parse_warnings": [],
            "terminal_event_count": 0 if dry_run else 1,
            "tool_names": [],
            "tool_use_count": 0,
            "mcp_tool_use_count": 0,
            "codex_image_tools": "not_checked",
            "containment": "not-run" if dry_run else "job-object",
            "descendant_cleanup_verified": False if dry_run else True,
            "strict_isolation": plan["policy"]["strict_isolation"],
        }

    def write_evidence(self, plan: dict, *, observe_tool: bool = True) -> None:
        dry_root = Path(plan["paths"]["dry_run_receipts"])
        dry_root.mkdir()
        (dry_root / "cairnspan-summary.json").write_text(
            json.dumps(self.base_summary(plan, dry_run=True), indent=2),
            encoding="utf-8",
        )

        live_root = Path(plan["paths"]["receipts"])
        live_root.mkdir()
        summary = self.base_summary(plan, dry_run=False)
        thread_id = summary["thread_id"]
        final = plan["request"]["expected_final"]
        events: list[dict] = [{"type": "thread.started", "thread_id": thread_id}]
        probe = plan["probe_name"]
        if probe == "image-generation":
            output = Path(plan["paths"]["workspace"]) / Path(plan["request"]["expected_output"])
            output.parent.mkdir()
            output.write_bytes(synthetic_view_png())
            final = "synthetic image created\nimagegen-ok"
            if observe_tool:
                events.append({"type": "image_generation", "result": str(output)})
                summary["tool_names"] = ["image_generation"]
                summary["tool_use_count"] = 1
                summary["codex_image_tools"] = "ok(image-generation)"
        elif probe == "image-view" and observe_tool:
            events.append({"type": "view_image", "path": plan["request"]["input_artifact"]["path"]})
            summary["tool_names"] = ["view_image"]
            summary["tool_use_count"] = 1
            summary["codex_image_tools"] = "ok(image-view)"
        events.extend([
            {"item": {"type": "agent_message", "text": final}},
            {"type": "turn.completed"},
        ])
        (live_root / "events.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
        (live_root / "transcript.log").write_text("synthetic fake-target evidence\n", encoding="utf-8")
        (live_root / "final.md").write_text(final, encoding="utf-8")
        (live_root / "cairnspan-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def close(self, plan: dict, approval: str = "owner-test-approval") -> subprocess.CompletedProcess[str]:
        return self.run_case(
            "close",
            "--case-root", plan["paths"]["case_root"],
            "--approval-reference", approval,
            "--approved-plan-sha256", sha256_file(Path(plan["paths"]["case_root"]) / "proposal-plan.json"),
        )

    def verify(self, plan: dict) -> subprocess.CompletedProcess[str]:
        return self.run_case("verify", "--case-root", plan["paths"]["case_root"])

    def test_prepares_three_separate_unapproved_proposals_without_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = {probe: self.prepare(root, probe) for probe in (
                "codex-effort", "image-generation", "image-view"
            )}

            self.assertEqual(len({plan["proposal_id"] for plan in plans.values()}), 3)
            for probe, plan in plans.items():
                self.assertEqual(plan["schema_version"], "0.2")
                self.assertEqual(plan["probe_name"], probe)
                self.assertEqual(plan["approval_state"], "not-granted")
                self.assertEqual(plan["policy"]["provider_launches_prepared"], 0)
                self.assertEqual(plan["policy"]["retry_budget"], 0)
                self.assertFalse(Path(plan["paths"]["dry_run_receipts"]).exists())
                self.assertFalse(Path(plan["paths"]["receipts"]).exists())
                self.assertNotEqual(plan["paths"]["dry_run_receipts"], plan["paths"]["receipts"])
                self.assertEqual(command_sha256(plan["dry_run_command"]), plan["dry_run_command_sha256"])
                self.assertEqual(command_sha256(plan["execute_command"]), plan["execute_command_sha256"])
                self.assertEqual(plan["dry_run_command"][-1], "--dry-run")
                self.assertEqual(plan["execute_command"][-1], "--execute")

    def test_codex_effort_proposal_freezes_reviewed_typed_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            command = plan["execute_command"]

            self.assertEqual(plan["request"]["model"], "gpt-5.6-sol")
            self.assertEqual(plan["request"]["effort"], "xhigh")
            self.assertEqual(plan["request"]["expected_final"], "cairnspan-effort-ok")
            self.assertIn("--strict-isolation", command)
            self.assertIn("--require-no-tool-use", command)
            self.assertEqual(command.count("--model"), 1)
            self.assertEqual(command.count("--effort"), 1)
            self.assertEqual(plan["policy"]["provider_honoring_claim"], "not-established-by-request-receipt")

    def test_image_proposals_freeze_required_capability_and_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generation = self.prepare(root, "image-generation")
            viewing = self.prepare(root, "image-view")

            self.assertEqual(generation["policy"]["required_image_capability"], "image-generation")
            self.assertEqual(generation["policy"]["sandbox"], "workspace-write")
            self.assertEqual(generation["request"]["expected_output"], ".cairnspan-imagegen/probe-image.png")
            self.assertEqual(viewing["policy"]["required_image_capability"], "image-view")
            self.assertEqual(viewing["policy"]["sandbox"], "read-only")
            image = Path(viewing["request"]["input_artifact"]["path"])
            self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(viewing["request"]["input_artifact"]["bytes"], 0)

    def test_closes_all_three_probe_types_with_independent_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for probe in ("codex-effort", "image-generation", "image-view"):
                with self.subTest(probe=probe):
                    plan = self.prepare(root, probe)
                    self.write_evidence(plan)
                    result = self.close(plan)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    closure = json.loads(Path(plan["paths"]["closure"]).read_text(encoding="utf-8"))
                    self.assertEqual(closure["status"], "closed")
                    self.assertEqual(closure["proposal_id"], plan["proposal_id"])
                    self.assertEqual(closure["approval_reference"], "owner-test-approval")
                    verified = self.verify(plan)
                    self.assertEqual(verified.returncode, 0, verified.stderr)
                    self.assertEqual(json.loads(verified.stdout)["status"], "verified")
                    if probe == "codex-effort":
                        self.assertEqual(closure["result"]["native_cli_acceptance"], "passed")
                        self.assertEqual(closure["result"]["provider_honoring"], "unknown")
                    elif probe == "image-generation":
                        self.assertEqual(closure["result"]["capability"], "ok(image-generation)")
                        self.assertIn("artifact", closure["result"])
                    else:
                        self.assertEqual(closure["result"]["capability"], "ok(image-view)")

    def test_close_rejects_launcher_command_digest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            self.write_evidence(plan)
            summary_path = Path(plan["paths"]["receipts"]) / "cairnspan-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["launcher_command_sha256"] = "0" * 64
            summary_path.write_text(json.dumps(summary), encoding="utf-8")

            result = self.close(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("command digest", result.stderr)
            self.assertFalse(Path(plan["paths"]["closure"]).exists())

    def test_close_rejects_no_edit_workspace_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "image-view")
            self.write_evidence(plan)
            (Path(plan["paths"]["workspace"]) / "unexpected.txt").write_text("unexpected", encoding="utf-8")

            result = self.close(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("changed the workspace", result.stderr)

    def test_close_rejects_unobserved_required_image_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "image-view")
            self.write_evidence(plan, observe_tool=False)

            result = self.close(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("required image capability", result.stderr)

    def test_close_rejects_extra_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            self.write_evidence(plan)
            (Path(plan["paths"]["receipts"]) / "extra.txt").write_text("extra", encoding="utf-8")

            result = self.close(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("missing or unexpected", result.stderr)

    def test_close_rejects_invalid_approval_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            self.write_evidence(plan)

            result = self.close(plan, "owner approval with spaces")

            self.assertEqual(result.returncode, 2)
            self.assertIn("approval-reference", result.stderr)

    def test_close_rejects_approval_for_a_different_plan_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            self.write_evidence(plan)
            result = self.run_case(
                "close", "--case-root", plan["paths"]["case_root"],
                "--approval-reference", "owner-test-approval",
                "--approved-plan-sha256", "0" * 64,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("approved-plan-sha256", result.stderr)

    def test_close_rejects_unexpected_case_root_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            self.write_evidence(plan)
            (Path(plan["paths"]["case_root"]) / "unexpected.txt").write_text("unexpected", encoding="utf-8")

            result = self.close(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("unexpected entries", result.stderr)

    def test_verify_rejects_receipt_drift_after_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            self.write_evidence(plan)
            self.assertEqual(self.close(plan).returncode, 0)
            (Path(plan["paths"]["receipts"]) / "final.md").write_text("changed", encoding="utf-8")

            result = self.verify(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("final artifact", result.stderr)

    def test_verify_rejects_closure_claim_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex-effort")
            self.write_evidence(plan)
            self.assertEqual(self.close(plan).returncode, 0)
            closure_path = Path(plan["paths"]["closure"])
            closure = json.loads(closure_path.read_text(encoding="utf-8"))
            closure["result"]["provider_honoring"] = "passed"
            closure_path.write_text(json.dumps(closure), encoding="utf-8")

            result = self.verify(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("result", result.stderr)

    def test_verify_rejects_workspace_drift_after_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "image-view")
            self.write_evidence(plan)
            self.assertEqual(self.close(plan).returncode, 0)
            (Path(plan["paths"]["workspace"]) / "late.txt").write_text("late", encoding="utf-8")

            result = self.verify(plan)

            self.assertEqual(result.returncode, 2)
            self.assertIn("changed the workspace", result.stderr)

    def test_existing_case_root_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_root = root / "existing"
            case_root.mkdir()
            sentinel = case_root / "owner.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            version = probe_cli_version(Path(sys.executable), root, version_probe_env())

            result = self.run_case(
                "prepare", "--case-root", str(case_root), "--probe", "codex-effort",
                "--codex-bin", sys.executable, "--expected-cli-version", version,
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
            self.assertEqual({path.name for path in case_root.iterdir()}, {"owner.txt"})

    def test_version_mismatch_stops_before_case_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_root = root / "mismatch"

            result = self.run_case(
                "prepare", "--case-root", str(case_root), "--probe", "codex-effort",
                "--codex-bin", sys.executable, "--expected-cli-version", "not-the-real-version",
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(case_root.exists())


if __name__ == "__main__":
    unittest.main()
