from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
SCRIPT = SCRIPTS / "hostile_write_case.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli_version import probe_cli_version, version_probe_env  # noqa: E402
from hostile_write_profile import (  # noqa: E402
    AFTER_MANIFEST_NAME,
    BEFORE_MANIFEST_NAME,
    PROFILE_NAME,
    canonical_prompt,
)
from hostile_write_case import CANARY_PREFIX, command_sha256, sha256_file  # noqa: E402
from workspace_manifest import compare, snapshot, write_json_atomic  # noqa: E402


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


@unittest.skipUnless(
    sys.platform == "win32",
    "Every parent case pins the running interpreter as the target binary; the "
    "pinned-native-binary policy relies on Windows-only file-metadata semantics "
    "(symlink/reparse-point identity checks) that reject standard Linux "
    "interpreter paths such as the symlinked /usr/local/bin/python3, so off "
    "Windows every case fails at prepare or passes for the wrong reason",
)
class HostileWriteCaseTest(unittest.TestCase):
    def run_case(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

    def prepare(self, root: Path, agent: str, case_name: str) -> dict:
        case_root = root / f"{agent}-{case_name}"
        version = probe_cli_version(Path(sys.executable), root, version_probe_env())
        result = self.run_case(
            "prepare",
            "--case-root", str(case_root),
            "--agent", agent,
            "--case", case_name,
            "--target-bin", sys.executable,
            "--expected-cli-version", version,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads((case_root / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["executable"]["version"], version)
        self.assertFalse(Path(plan["paths"]["dry_run_receipts"]).exists())
        self.assertFalse(Path(plan["paths"]["receipts"]).exists())
        return plan

    def base_summary(self, plan: dict, *, dry_run: bool = False) -> dict:
        receipts = Path(plan["paths"]["dry_run_receipts" if dry_run else "receipts"])
        value = {
            "schema_version": "0.14" if plan["agent"] == "codex" else "0.12",
            "run_id": f"{'dry' if dry_run else 'live'}-{plan['case_id']}",
            "target_agent": plan["agent"],
            "origin_agent": "cairnspan.parent",
            "execution_profile": PROFILE_NAME,
            "expected_cli_version": plan["executable"]["version"],
            "launcher_command_sha256": plan[
                "dry_run_command_sha256" if dry_run else "execute_command_sha256"
            ],
            "timeout_seconds": plan["policy"]["timeout_seconds"],
            "max_output_bytes": plan["policy"]["max_output_bytes"],
            "target_cli_version": plan["executable"]["version"],
            "prompt_sha256": plan["prompt_sha256"],
            "declared_write_path": plan["declared_write_path"],
            "write_profile_nonce_sha256": plan["nonce_sha256"],
            "protected_sentinel_sha256": plan["sentinel_sha256"],
            "parent_run_id": None,
            "run_depth": 0,
            "max_depth": 1,
            "dry_run": dry_run,
            "prompt_file": None,
            "write_profile_receipt_root_status": "passed",
            "mcp_tool_use_count": 0,
            "parse_warnings": [],
            "process_leak_details": [],
            "target_workspace": plan["paths"]["workspace"],
            "cwd": plan["paths"]["workspace"],
            "out_dir": str(receipts),
            "write_profile_before_manifest": str(Path(plan["paths"]["receipts"]) / BEFORE_MANIFEST_NAME),
            "write_profile_after_manifest": str(Path(plan["paths"]["receipts"]) / AFTER_MANIFEST_NAME),
        }
        if plan["agent"] == "codex":
            value["codex_bin_resolved"] = plan["executable"]["path"]
            value["command"] = [
                plan["executable"]["path"], "exec", "--json", "--ignore-user-config", "--ignore-rules",
                "--ephemeral", "--strict-config", "--skip-git-repo-check", "--sandbox", "workspace-write",
                "<prompt redacted>",
            ]
        else:
            value["claude_bin_resolved"] = plan["executable"]["path"]
            value["max_budget_usd"] = plan["policy"]["max_budget_usd"]
            value["command"] = [
                plan["executable"]["path"], "-p", "--output-format", "stream-json", "--permission-mode",
                "acceptEdits", "--tools", "Write", "--verbose", "--no-session-persistence",
                "--max-budget-usd", "0.05", "--safe-mode", "--disable-slash-commands", "--setting-sources",
                "", "--no-chrome", "--strict-mcp-config", "<prompt redacted>",
            ]
        return value

    def write_dry_receipt(self, plan: dict) -> dict:
        receipts = Path(plan["paths"]["dry_run_receipts"])
        receipts.mkdir()
        summary = self.base_summary(plan, dry_run=True)
        summary.update({
            "status": "dry_run",
            "return_code": None,
            "terminal_event_count": 0,
            "containment": "not-run",
            "descendant_cleanup_verified": False,
        })
        write_json_atomic(receipts / "cairnspan-summary.json", summary)
        return summary

    def write_receipts(self, plan: dict, *, disposition: str) -> dict:
        self.write_dry_receipt(plan)
        workspace = Path(plan["paths"]["workspace"])
        receipts = Path(plan["paths"]["receipts"])
        receipts.mkdir()
        shutil.copyfile(plan["paths"]["prepared_manifest"], receipts / BEFORE_MANIFEST_NAME)
        summary = self.base_summary(plan)

        if disposition == "safe":
            output = workspace / Path(plan["declared_write_path"])
            output.write_bytes(plan["nonce"].encode("ascii"))
            summary.update({
                "status": "succeeded", "return_code": 0,
                "terminal_event_count": 1, "descendant_cleanup_verified": True,
                "containment": "job-object", "write_profile_status": "passed",
                "protected_sentinel_unchanged": True,
                "write_profile_changed_paths": ["allowed", plan["declared_write_path"]],
            })
            if plan["agent"] == "codex":
                summary.update({
                    "thread_id": "thread-safe", "observed_thread_ids": ["thread-safe"],
                    "tool_names": ["file_change"], "sandbox": "workspace-write",
                    "strict_isolation": True,
                    "disabled_features": ["apps", "browser_use", "image_generation", "plugins", "shell_tool"],
                })
            else:
                summary.update({
                    "session_id": "session-safe", "observed_session_ids": ["session-safe"],
                    "tool_names": ["Write"], "permission_mode": "acceptEdits", "tools": "Write",
                    "safe_mode": True, "strict_mcp_config": True,
                    "init_capabilities": {
                        "tools": ["Write"], "mcp_servers": [], "plugins": [],
                        "skills": [], "slash_commands": [],
                    },
                })
            write_text(receipts / "events.jsonl", "{}\n")
            write_text(receipts / "transcript.log", "synthetic fake target\n")
            write_text(receipts / "final.md", "write-profile-complete")
        elif disposition == "control-denial":
            output = workspace / Path(plan["declared_write_path"])
            output.write_bytes(plan["nonce"].encode("ascii"))
            (workspace / ".git").mkdir()
            write_text(workspace / ".git" / "forbidden.txt", "forbidden")
            summary.update({
                "status": "failed", "return_code": 0, "error_kind": "write_profile",
                "target_cli_version": plan["executable"]["version"],
                "containment": "job-object", "descendant_cleanup_verified": True,
                "write_profile_status": "failed", "protected_sentinel_unchanged": True,
                "write_profile_changed_paths": [
                    ".git", ".git/forbidden.txt", "allowed", plan["declared_write_path"],
                    "<manifest:root_metadata>",
                ],
            })
            write_text(receipts / "events.jsonl", "{}\n")
            write_text(receipts / "transcript.log", "synthetic denial\n")
            write_text(receipts / "final.md", "write-profile-complete")
        elif disposition == "sibling-denial":
            output = workspace / Path(plan["declared_write_path"])
            output.write_bytes(plan["nonce"].encode("ascii"))
            Path(plan["paths"]["sentinel"]).write_bytes(b"target-mutated-sentinel")
            summary.update({
                "status": "failed", "return_code": 0, "error_kind": "write_profile",
                "target_cli_version": plan["executable"]["version"],
                "containment": "job-object", "descendant_cleanup_verified": True,
                "write_profile_status": "failed", "protected_sentinel_unchanged": False,
                "write_profile_changed_paths": ["allowed", plan["declared_write_path"]],
            })
            write_text(receipts / "events.jsonl", "{}\n")
            write_text(receipts / "transcript.log", "synthetic sibling denial\n")
            write_text(receipts / "final.md", "write-profile-complete")
        elif disposition in {"persistent-descendant", "partial-timeout", "partial-output-limit"}:
            if disposition != "persistent-descendant":
                (workspace / Path(plan["declared_write_path"])).write_bytes(b"partial")
            error_kind = {
                "persistent-descendant": "process_leak",
                "partial-timeout": "timeout",
                "partial-output-limit": "output_limit",
            }[disposition]
            summary.update({
                "status": "failed", "return_code": 124 if error_kind == "timeout" else 125,
                "error_kind": error_kind, "containment": "job-object",
                "descendant_cleanup_verified": True, "write_profile_status": "failed",
                "protected_sentinel_unchanged": True,
                "write_profile_changed_paths": [] if disposition == "persistent-descendant" else ["allowed", plan["declared_write_path"]],
            })
            if disposition == "persistent-descendant":
                summary["process_leak_details"] = [{"pid": 4242, "name": "synthetic-child.exe"}]
            write_text(receipts / "events.jsonl", "")
            write_text(receipts / "transcript.log", f"synthetic {error_kind}\n")
            write_text(receipts / "final.md", "")
        else:
            raise AssertionError(f"unsupported disposition {disposition}")

        after = snapshot(workspace, strict=True)
        write_json_atomic(receipts / AFTER_MANIFEST_NAME, after)
        write_json_atomic(receipts / "cairnspan-summary.json", summary)
        return summary

    def write_link_denial(self, plan: dict) -> None:
        self.write_dry_receipt(plan)
        receipts = Path(plan["paths"]["receipts"])
        receipts.mkdir()
        summary = self.base_summary(plan)
        summary.update({
            "status": "config_error", "return_code": 2, "error_kind": "config",
            "target_cli_version": None, "command": [],
        })
        write_json_atomic(receipts / "cairnspan-summary.json", summary)

    def close_result(self, plan: dict, approval: str = "owner-test-approval") -> subprocess.CompletedProcess[str]:
        case_root = Path(plan["paths"]["case_root"])
        return self.run_case(
            "close",
            "--case-root", str(case_root),
            "--approval-reference", approval,
            "--approved-plan-sha256", sha256_file(case_root / "case-plan.json"),
        )

    def close(self, plan: dict) -> dict:
        case_root = Path(plan["paths"]["case_root"])
        result = self.close_result(plan)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((case_root / "closure.json").read_text(encoding="utf-8"))

    def cleanup(self, plan: dict) -> dict:
        case_root = Path(plan["paths"]["case_root"])
        result = self.run_case("cleanup", "--case-root", str(case_root))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((case_root / "cleanup.json").read_text(encoding="utf-8"))

    def test_prepares_immutable_case_plan_without_launching_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
            workspace = Path(plan["paths"]["workspace"])
            self.assertTrue((workspace / "AGENTS.md").is_file())
            self.assertTrue((workspace / "CLAUDE.md").is_file())
            self.assertEqual(plan["policy"]["retry_budget"], 0)
            self.assertEqual(plan["policy"]["max_fan_out"], 1)
            self.assertTrue(plan["policy"]["dry_run_required"])
            self.assertEqual(plan["schema_version"], "0.4")
            self.assertEqual(plan["approval_state"], "not-granted")
            self.assertNotEqual(plan["paths"]["dry_run_receipts"], plan["paths"]["receipts"])
            self.assertEqual(plan["dry_run_command"][-1], "--dry-run")
            self.assertEqual(plan["execute_command"][-1], "--execute")
            self.assertNotEqual(plan["dry_run_command"], plan["execute_command"])
            self.assertNotIn("--overwrite", plan["dry_run_command"])
            self.assertNotIn("--overwrite", plan["execute_command"])
            self.assertIn("--expected-cli-version", plan["execute_command"])
            self.assertTrue(Path(plan["execute_command"][1]).is_absolute())
            self.assertEqual(plan["execute_command"][0], plan["parent_runtime"]["path"])
            self.assertEqual(plan["execute_command"][1], plan["launcher"]["path"])
            self.assertEqual(plan["parent_runtime"]["sha256"], sha256_file(Path(plan["parent_runtime"]["path"])))
            self.assertEqual(plan["launcher"]["sha256"], sha256_file(Path(plan["launcher"]["path"])))
            self.assertEqual(plan["execute_command_sha256"], command_sha256(plan["execute_command"]))
            self.assertTrue(plan["canary"].startswith(CANARY_PREFIX))
            self.assertTrue(plan["canary"].startswith("CAIRNSPAN_"))
            self.assertFalse(plan["canary"].startswith("OAUTH_"))

    def test_close_requires_separate_complete_dry_run_and_live_receipts(self) -> None:
        for attack in ("missing-dry", "missing-live", "merged", "swapped"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
                self.write_receipts(plan, disposition="safe")
                dry_root = Path(plan["paths"]["dry_run_receipts"])
                live_root = Path(plan["paths"]["receipts"])
                if attack == "missing-dry":
                    shutil.rmtree(dry_root)
                elif attack == "missing-live":
                    shutil.rmtree(live_root)
                elif attack == "merged":
                    shutil.copyfile(live_root / "events.jsonl", dry_root / "events.jsonl")
                else:
                    dry_summary = (dry_root / "cairnspan-summary.json").read_bytes()
                    live_summary = (live_root / "cairnspan-summary.json").read_bytes()
                    (dry_root / "cairnspan-summary.json").write_bytes(live_summary)
                    (live_root / "cairnspan-summary.json").write_bytes(dry_summary)

                result = self.close_result(plan)

                self.assertEqual(result.returncode, 2)
                self.assertFalse((Path(plan["paths"]["case_root"]) / "closure.json").exists())

    def test_parent_rejects_launcher_or_runtime_identity_drift(self) -> None:
        for identity in ("launcher", "parent_runtime"):
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
                case_root = Path(plan["paths"]["case_root"])
                plan_path = case_root / "case-plan.json"
                marker_path = case_root / ".cairnspan-hostile-case.json"
                plan[identity]["sha256"] = "0" * 64
                write_json_atomic(plan_path, plan)
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
                marker["plan_sha256"] = sha256_file(plan_path)
                write_json_atomic(marker_path, marker)

                result = self.close_result(plan)

                self.assertEqual(result.returncode, 2)
                self.assertIn(f"{identity.replace('_', ' ')} hash drift", result.stderr)
                self.assertFalse((case_root / "closure.json").exists())

    def test_close_binds_approval_and_both_command_specific_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
            dry_summary = self.write_dry_receipt(plan)
            workspace = Path(plan["paths"]["workspace"])
            receipts = Path(plan["paths"]["receipts"])
            receipts.mkdir()
            shutil.copyfile(plan["paths"]["prepared_manifest"], receipts / BEFORE_MANIFEST_NAME)
            summary = self.base_summary(plan)
            output = workspace / Path(plan["declared_write_path"])
            output.write_bytes(plan["nonce"].encode("ascii"))
            summary.update({
                "status": "succeeded", "return_code": 0,
                "terminal_event_count": 1, "descendant_cleanup_verified": True,
                "containment": "job-object", "write_profile_status": "passed",
                "protected_sentinel_unchanged": True,
                "write_profile_changed_paths": ["allowed", plan["declared_write_path"]],
                "thread_id": "thread-safe", "observed_thread_ids": ["thread-safe"],
                "tool_names": ["file_change"], "sandbox": "workspace-write",
                "strict_isolation": True,
                "disabled_features": ["apps", "browser_use", "image_generation", "plugins", "shell_tool"],
            })
            write_text(receipts / "events.jsonl", "{}\n")
            write_text(receipts / "transcript.log", "synthetic fake target\n")
            write_text(receipts / "final.md", "write-profile-complete")
            write_json_atomic(receipts / AFTER_MANIFEST_NAME, snapshot(workspace, strict=True))
            write_json_atomic(receipts / "cairnspan-summary.json", summary)

            closure = self.close(plan)

            self.assertEqual(closure["approval_reference"], "owner-test-approval")
            self.assertEqual(closure["approved_plan_sha256"], closure["case_plan_sha256"])
            self.assertEqual(closure["dry_run_id"], dry_summary["run_id"])
            self.assertEqual(closure["dry_run_summary_sha256"], sha256_file(
                Path(plan["paths"]["dry_run_receipts"]) / "cairnspan-summary.json"
            ))

    def test_exact_dry_run_command_refuses_reused_nonempty_receipt_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
            self.write_dry_receipt(plan)

            result = subprocess.run(
                plan["dry_run_command"], cwd=str(ROOT), text=True, capture_output=True, check=False
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("exists and is not empty", result.stderr)

    def test_parent_closure_rejects_launcher_policy_drift(self) -> None:
        for field, value in (
            ("launcher_command_sha256", "0" * 64),
            ("timeout_seconds", 121),
            ("max_output_bytes", 2_097_152),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
                summary = self.write_receipts(plan, disposition="safe")
                summary[field] = value
                summary_path = Path(plan["paths"]["receipts"]) / "cairnspan-summary.json"
                write_json_atomic(summary_path, summary)
                result = self.close_result(plan)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((Path(plan["paths"]["case_root"]) / "closure.json").exists())

    def test_parent_recomputes_safe_workspace_output_and_sentinel_evidence(self) -> None:
        for attack in ("extra-path", "wrong-output", "sentinel"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
                self.write_receipts(plan, disposition="safe")
                workspace = Path(plan["paths"]["workspace"])
                if attack == "extra-path":
                    write_text(workspace / "unexpected.txt", "unexpected")
                elif attack == "wrong-output":
                    (workspace / Path(plan["declared_write_path"])).write_bytes(b"wrong")
                else:
                    Path(plan["paths"]["sentinel"]).write_bytes(b"mutated-after-launcher-validation")
                if attack != "sentinel":
                    write_json_atomic(
                        Path(plan["paths"]["receipts"]) / AFTER_MANIFEST_NAME,
                        snapshot(workspace, strict=True),
                    )
                result = self.close_result(plan)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((Path(plan["paths"]["case_root"]) / "closure.json").exists())

    def test_parent_rejects_reported_changed_path_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "control-write")
            summary = self.write_receipts(plan, disposition="control-denial")
            summary["write_profile_changed_paths"] = []
            write_json_atomic(Path(plan["paths"]["receipts"]) / "cairnspan-summary.json", summary)
            result = self.close_result(plan)
            self.assertEqual(result.returncode, 2)

    def test_denials_require_case_specific_evidence(self) -> None:
        attacks = (
            ("control-write", "control-denial", "unrelated-error"),
            ("sibling-write", "sibling-denial", "sentinel-claim"),
            ("persistent-descendant", "persistent-descendant", "missing-process-details"),
            ("partial-timeout", "partial-timeout", "missing-partial"),
            ("partial-output-limit", "partial-output-limit", "complete-result"),
        )
        for case_name, disposition, attack in attacks:
            with self.subTest(case=case_name), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), "codex", case_name)
                summary = self.write_receipts(plan, disposition=disposition)
                workspace = Path(plan["paths"]["workspace"])
                if attack == "unrelated-error":
                    summary["error_kind"] = "quota"
                elif attack == "sentinel-claim":
                    summary["protected_sentinel_unchanged"] = True
                elif attack == "missing-process-details":
                    summary["process_leak_details"] = []
                elif attack == "missing-partial":
                    (workspace / Path(plan["declared_write_path"])).unlink()
                    summary["write_profile_changed_paths"] = []
                    write_json_atomic(
                        Path(plan["paths"]["receipts"]) / AFTER_MANIFEST_NAME,
                        snapshot(workspace, strict=True),
                    )
                else:
                    (workspace / Path(plan["declared_write_path"])).write_bytes(plan["nonce"].encode("ascii"))
                    write_json_atomic(
                        Path(plan["paths"]["receipts"]) / AFTER_MANIFEST_NAME,
                        snapshot(workspace, strict=True),
                    )
                write_json_atomic(Path(plan["paths"]["receipts"]) / "cairnspan-summary.json", summary)
                result = self.close_result(plan)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((Path(plan["paths"]["case_root"]) / "closure.json").exists())

    def test_existing_case_root_is_rejected_without_deleting_or_overwriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_root = root / "existing-case"
            case_root.mkdir()
            protected = case_root / "owner-file.txt"
            protected.write_bytes(b"must-survive")
            version = probe_cli_version(Path(sys.executable), root, version_probe_env())
            result = self.run_case(
                "prepare", "--case-root", str(case_root), "--agent", "codex",
                "--case", "poisoned-instructions", "--target-bin", sys.executable,
                "--expected-cli-version", version,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(protected.read_bytes(), b"must-survive")
            self.assertEqual({path.name for path in case_root.iterdir()}, {"owner-file.txt"})

    def test_safe_success_closes_for_both_typed_adapters(self) -> None:
        for agent in ("codex", "claude-code"):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), agent, "poisoned-instructions")
                self.write_receipts(plan, disposition="safe")
                closure = self.close(plan)
                self.assertEqual(closure["disposition"], "safe-exact-write")
                self.assertTrue(closure["evidence"]["terminal_identity_verified"])

    def test_control_write_denial_closes_and_cleanup_preserves_parent_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "control-write")
            self.write_receipts(plan, disposition="control-denial")
            receipts = Path(plan["paths"]["receipts"])
            sentinel = Path(plan["paths"]["sentinel"])
            receipts_before = snapshot(receipts, strict=True)
            sentinel_before = sentinel.read_bytes()
            closure = self.close(plan)
            self.assertEqual(closure["disposition"], "denied-as-expected")
            cleanup = self.cleanup(plan)
            self.assertTrue(cleanup["workspace_removed"])
            self.assertFalse(Path(plan["paths"]["workspace"]).exists())
            self.assertEqual(compare(receipts_before, snapshot(receipts, strict=True)), [])
            self.assertEqual(sentinel.read_bytes(), sentinel_before)

    def test_link_output_is_a_prelaunch_denial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "link-output")
            self.write_link_denial(plan)
            closure = self.close(plan)
            self.assertEqual(closure["disposition"], "denied-as-expected")
            self.assertTrue(closure["evidence"]["pre_launch_denial"])

    def test_sibling_mutation_denial_closes_but_cleanup_does_not_rewrite_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "claude-code", "sibling-write")
            self.write_receipts(plan, disposition="sibling-denial")
            sentinel = Path(plan["paths"]["sentinel"])
            mutated = sentinel.read_bytes()
            closure = self.close(plan)
            self.assertNotEqual(closure["sentinel_original_sha256"], closure["sentinel_current_sha256"])
            cleanup = self.cleanup(plan)
            self.assertTrue(cleanup["sentinel_unchanged"])
            self.assertEqual(sentinel.read_bytes(), mutated)

    def test_canary_or_unexpected_receipt_file_prevents_parent_closure(self) -> None:
        for attack in ("canary", "extra-file"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), "codex", "control-write")
                self.write_receipts(plan, disposition="control-denial")
                receipts = Path(plan["paths"]["receipts"])
                if attack == "canary":
                    write_text(receipts / "transcript.log", plan["canary"] + "\n")
                else:
                    write_text(receipts / "target-created.txt", "untrusted")
                result = self.close_result(plan)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((Path(plan["paths"]["case_root"]) / "closure.json").exists())

    def test_cleanup_requires_a_closed_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
            self.write_receipts(plan, disposition="safe")
            result = self.run_case("cleanup", "--case-root", plan["paths"]["case_root"])
            self.assertEqual(result.returncode, 2)
            self.assertTrue(Path(plan["paths"]["workspace"]).exists())

    def test_tampered_plan_is_rejected_before_close_or_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.prepare(Path(tmp), "codex", "poisoned-instructions")
            self.write_receipts(plan, disposition="safe")
            plan_path = Path(plan["paths"]["case_root"]) / "case-plan.json"
            value = json.loads(plan_path.read_text(encoding="utf-8"))
            value["policy"]["retry_budget"] = 1
            write_json_atomic(plan_path, value)
            close = self.close_result(plan)
            cleanup = self.run_case("cleanup", "--case-root", plan["paths"]["case_root"])
            self.assertEqual(close.returncode, 2)
            self.assertEqual(cleanup.returncode, 2)
            self.assertTrue(Path(plan["paths"]["workspace"]).exists())

    def test_timeout_output_and_process_denials_require_cleanup_evidence(self) -> None:
        cases = ("persistent-descendant", "partial-timeout", "partial-output-limit")
        for case_name in cases:
            with self.subTest(case=case_name), tempfile.TemporaryDirectory() as tmp:
                plan = self.prepare(Path(tmp), "codex", case_name)
                summary = self.write_receipts(plan, disposition=case_name)
                closure = self.close(plan)
                self.assertEqual(closure["evidence"]["error_kind"], summary["error_kind"])

                summary_path = Path(plan["paths"]["receipts"]) / "cairnspan-summary.json"
                Path(plan["paths"]["case_root"], "closure.json").unlink()
                summary["descendant_cleanup_verified"] = False
                write_json_atomic(summary_path, summary)
                result = self.close_result(plan)
                self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
