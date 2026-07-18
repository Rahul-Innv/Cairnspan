from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import synthetic_image_pilot as pilot  # noqa: E402
from cli_version import probe_cli_version, version_probe_env  # noqa: E402
from synthetic_probe_case import sha256_file  # noqa: E402


class SyntheticImagePilotTest(unittest.TestCase):
    def capability_verifier(self, root: Path):
        path = str(root)
        version = probe_cli_version(Path(sys.executable), root.parent, version_probe_env())
        executable = {
            "path": str(Path(sys.executable).resolve()),
            "sha256": sha256_file(Path(sys.executable).resolve()),
            "version": version,
        }
        if "generation-cap" in path:
            probe = "image-generation"
        elif "view-cap" in path:
            probe = "image-view"
        else:
            probe = "image-generation"
        return {
            "schema_version": "0.2",
            "status": "verified",
            "proposal_id": f"proposal-{probe}",
            "probe_name": probe,
            "closure_sha256": f"closure-{probe}",
            "case_root": path,
            "plan_sha256": f"plan-{probe}",
            "executable": executable,
            "result": {"capability": f"ok({probe})"},
        }

    def prepare_args(self, root: Path, **overrides) -> argparse.Namespace:
        values = {
            "batch_root": root / "batch",
            "image_generation_case_root": root / "generation-cap",
            "image_view_case_root": root / "view-cap",
            "daily_ledger": root / "daily-ledger.json",
            "max_batch_seconds": 1800,
            "max_batch_output_bytes": 3_145_728,
            "max_disk_bytes": 30_000_000,
            "daily_item_ceiling": 3,
            "retention_hours": 168,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def prepare(self, root: Path, **overrides) -> dict:
        with patch.object(pilot, "verify_closed_case", side_effect=self.capability_verifier):
            return pilot.prepare_batch(self.prepare_args(root, **overrides))

    def execute(self, plan: dict, executor):
        args = argparse.Namespace(
            batch_root=Path(plan["paths"]["batch_root"]),
            approval_reference="owner-pilot-test",
            approved_plan_sha256=sha256_file(Path(plan["paths"]["batch_root"]) / "batch-plan.json"),
        )
        with patch.object(pilot, "verify_closed_case", side_effect=self.capability_verifier):
            return pilot.execute_batch(args, item_executor=executor)

    def success_executor(self, calls: list[str]):
        def execute(item: dict, plan: dict, approval: str) -> dict:
            calls.append(item["item_id"])
            return {
                "item_id": item["item_id"],
                "item_index": item["item_index"],
                "proposal_id": item["proposal_id"],
                "receipt_output_bytes": 100,
                "target_elapsed_seconds": 1.0,
                "closure_sha256": f"closure-{item['item_id']}",
                "artifact": {"sha256": f"artifact-{item['item_id']}"},
            }
        return execute

    def batch_verifier(self, plan: dict):
        item_by_root = {str(Path(item["case_root"]).resolve()): item for item in plan["items"]}

        def verify(root: Path):
            resolved = str(root.resolve())
            if resolved in item_by_root:
                item = item_by_root[resolved]
                return {
                    "schema_version": "0.2",
                    "status": "verified",
                    "proposal_id": item["proposal_id"],
                    "probe_name": "image-generation",
                    "closure_sha256": f"closure-{item['item_id']}",
                    "case_root": resolved,
                    "executable": plan["executable"],
                    "result": {
                        "capability": "ok(image-generation)",
                        "artifact": {"sha256": f"artifact-{item['item_id']}"},
                    },
                }
            return self.capability_verifier(root)
        return verify

    def test_prepare_freezes_exact_three_item_order_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)

            self.assertEqual(plan["schema_version"], "0.1")
            self.assertEqual(plan["approval_state"], "not-granted")
            self.assertEqual(plan["policy"]["item_count"], 3)
            self.assertEqual(plan["policy"]["concurrency"], 1)
            self.assertEqual(plan["policy"]["automatic_retries"], 0)
            self.assertFalse(Path(plan["paths"]["daily_ledger"]).exists())
            self.assertEqual(
                [item["item_id"] for item in plan["items"]],
                ["paper-boat", "geometric-sunrise", "green-leaf"],
            )
            for item in plan["items"]:
                item_plan = json.loads((Path(item["case_root"]) / "proposal-plan.json").read_text(encoding="utf-8"))
                self.assertEqual(item_plan["proposal_context"]["batch_id"], plan["batch_id"])
                self.assertEqual(item_plan["policy"]["automatic_retries"] if "automatic_retries" in item_plan["policy"] else 0, 0)
                self.assertFalse(Path(item_plan["paths"]["dry_run_receipts"]).exists())
                self.assertFalse(Path(item_plan["paths"]["receipts"]).exists())

    def test_prepare_refuses_without_verified_capability_closures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.prepare_args(root)

            with self.assertRaisesRegex(pilot.PilotError, "capability closure did not verify"):
                pilot.prepare_batch(args)

            self.assertFalse(args.batch_root.exists())

    def test_execute_closes_three_items_in_declared_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            calls: list[str] = []

            result = self.execute(plan, self.success_executor(calls))

            self.assertEqual(result["status"], "closed")
            self.assertEqual(calls, ["paper-boat", "geometric-sunrise", "green-leaf"])
            self.assertEqual(result["attempted_item_ids"], calls)
            self.assertEqual(result["completed_item_ids"], calls)
            self.assertEqual(result["automatic_retries"], 0)
            self.assertEqual(result["product_integration"], "not-run")

    def test_verify_accepts_exact_success_state_and_item_closures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            self.execute(plan, self.success_executor([]))

            with patch.object(pilot, "verify_closed_case", side_effect=self.batch_verifier(plan)):
                verified = pilot.verify_batch(Path(plan["paths"]["batch_root"]))

            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["terminal_status"], "closed")
            self.assertEqual(len(verified["verified_item_closures"]), 3)

    def test_verify_rejects_result_order_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            self.execute(plan, self.success_executor([]))
            result_path = Path(plan["paths"]["result"])
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["completed_item_ids"] = list(reversed(result["completed_item_ids"]))
            result_path.write_text(json.dumps(result), encoding="utf-8")

            with patch.object(pilot, "verify_closed_case", side_effect=self.batch_verifier(plan)):
                with self.assertRaisesRegex(pilot.PilotError, "declared prefix"):
                    pilot.verify_batch(Path(plan["paths"]["batch_root"]))

    def test_execute_stops_before_later_item_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            calls: list[str] = []

            def executor(item: dict, batch: dict, approval: str) -> dict:
                calls.append(item["item_id"])
                if item["item_index"] == 2:
                    raise pilot.PilotError("synthetic rate limit")
                return self.success_executor([])(item, batch, approval)

            result = self.execute(plan, executor)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(calls, ["paper-boat", "geometric-sunrise"])
            self.assertEqual(result["attempted_item_ids"], calls)
            self.assertEqual(result["completed_item_ids"], ["paper-boat"])
            self.assertEqual(result["failed_item_id"], "geometric-sunrise")
            third_plan = json.loads((Path(plan["items"][2]["case_root"]) / "proposal-plan.json").read_text(encoding="utf-8"))
            self.assertFalse(Path(third_plan["paths"]["dry_run_receipts"]).exists())
            self.assertFalse(Path(third_plan["paths"]["receipts"]).exists())

    def test_execute_stops_before_next_item_after_aggregate_output_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            calls: list[str] = []

            def executor(item: dict, batch: dict, approval: str) -> dict:
                outcome = self.success_executor(calls)(item, batch, approval)
                outcome["receipt_output_bytes"] = batch["policy"]["max_batch_output_bytes"] + 1
                return outcome

            result = self.execute(plan, executor)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(calls, ["paper-boat"])
            self.assertIn("output ceiling", result["failure"])
            self.assertIsNone(result["failed_item_id"])
            with patch.object(pilot, "verify_closed_case", side_effect=self.batch_verifier(plan)):
                verified = pilot.verify_batch(Path(plan["paths"]["batch_root"]))
            self.assertEqual(verified["terminal_status"], "failed")

    def test_daily_ledger_ceiling_stops_before_extra_provider_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            day = datetime.now(timezone.utc).date().isoformat()
            ledger_path = Path(plan["paths"]["daily_ledger"])
            ledger_path.write_text(json.dumps({
                "schema_version": "0.1",
                "events": [
                    {"utc_day": day, "batch_id": "other", "item_id": "one"},
                    {"utc_day": day, "batch_id": "other", "item_id": "two"},
                ],
            }), encoding="utf-8")
            calls: list[str] = []

            result = self.execute(plan, self.success_executor(calls))

            self.assertEqual(result["status"], "failed")
            self.assertEqual(calls, ["paper-boat"])
            self.assertIn("daily provider-use ceiling", result["failure"])
            self.assertIsNone(result["failed_item_id"])
            with patch.object(pilot, "verify_closed_case", side_effect=self.batch_verifier(plan)):
                verified = pilot.verify_batch(Path(plan["paths"]["batch_root"]))
            self.assertEqual(verified["terminal_status"], "failed")

    def test_execution_refuses_resume_or_second_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            self.execute(plan, self.success_executor([]))
            args = argparse.Namespace(
                batch_root=Path(plan["paths"]["batch_root"]),
                approval_reference="owner-pilot-test",
                approved_plan_sha256=sha256_file(Path(plan["paths"]["batch_root"]) / "batch-plan.json"),
            )

            with patch.object(pilot, "verify_closed_case", side_effect=self.capability_verifier):
                with self.assertRaisesRegex(pilot.PilotError, "cannot resume"):
                    pilot.execute_batch(args, item_executor=self.success_executor([]))

    def test_execution_rejects_approval_for_different_batch_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            args = argparse.Namespace(
                batch_root=Path(plan["paths"]["batch_root"]),
                approval_reference="owner-pilot-test",
                approved_plan_sha256="0" * 64,
            )

            with patch.object(pilot, "verify_closed_case", side_effect=self.capability_verifier):
                with self.assertRaisesRegex(pilot.PilotError, "approved-plan-sha256"):
                    pilot.execute_batch(args, item_executor=self.success_executor([]))

    def test_execution_rejects_unexpected_batch_root_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)
            (Path(plan["paths"]["batch_root"]) / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            args = argparse.Namespace(
                batch_root=Path(plan["paths"]["batch_root"]),
                approval_reference="owner-pilot-test",
                approved_plan_sha256=sha256_file(Path(plan["paths"]["batch_root"]) / "batch-plan.json"),
            )

            with patch.object(pilot, "verify_closed_case", side_effect=self.capability_verifier):
                with self.assertRaisesRegex(pilot.PilotError, "unexpected entries"):
                    pilot.execute_batch(args, item_executor=self.success_executor([]))

    def test_verify_failed_batch_rejects_later_item_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.prepare(root)

            def fail_first(item: dict, batch: dict, approval: str) -> dict:
                raise pilot.PilotError("synthetic auth failure")

            result = self.execute(plan, fail_first)
            self.assertEqual(result["status"], "failed")
            later_plan_path = Path(plan["items"][1]["case_root"]) / "proposal-plan.json"
            later_plan = json.loads(later_plan_path.read_text(encoding="utf-8"))
            Path(later_plan["paths"]["dry_run_receipts"]).mkdir()

            with patch.object(pilot, "verify_closed_case", side_effect=self.capability_verifier):
                with self.assertRaisesRegex(pilot.PilotError, "later batch item ran"):
                    pilot.verify_batch(Path(plan["paths"]["batch_root"]))


if __name__ == "__main__":
    unittest.main()
