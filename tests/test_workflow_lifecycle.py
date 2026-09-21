import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_modeling_assistant.core.agents import Workflow
from ai_modeling_assistant.core.artifacts import file_evidence, verify_evidence, atomic_json
from ai_modeling_assistant.core.config import ProviderConfig
from ai_modeling_assistant.core.media import recover


class WorkflowLifecycleTests(unittest.TestCase):
    def workflow(self):
        return Workflow.from_plan(
            "assembly",
            {
                "tasks": [
                    {"id": "left", "expert": "modeler", "prompt": "left"},
                    {"id": "right", "expert": "modeler", "prompt": "right"},
                    {
                        "id": "join",
                        "expert": "material",
                        "prompt": "assemble",
                        "depends_on": ["left", "right"],
                    },
                    {
                        "id": "export",
                        "expert": "exporter",
                        "prompt": "export",
                        "depends_on": ["join"],
                    },
                ]
            },
        )

    def test_unrelated_task_runs_after_sibling_failure(self):
        flow = self.workflow()
        flow.start(flow.get("left"))
        self.assertEqual([t.id for t in flow.ready()], ["right"])
        flow.fail(flow.get("left"), "invalid geometry")
        self.assertEqual([t.id for t in flow.ready()], ["right"])
        flow.start(flow.get("right"))
        flow.succeed(flow.get("right"), {"objects": ["right"]})
        self.assertEqual(flow.get("export").status, "blocked")
        flow.retry()
        self.assertEqual([t.id for t in flow.ready()], ["left"])
        self.assertEqual(flow.get("right").attempts, 1)

    def test_revision_invalidates_only_dependents(self):
        flow = self.workflow()
        while flow.ready():
            task = flow.ready()[0]
            flow.start(task)
            flow.succeed(task, {"asset": "verified"})
        self.assertEqual(flow.invalidate("left", "change dimensions"), {"left", "join", "export"})
        self.assertEqual(flow.get("right").status, "succeeded")
        self.assertEqual(flow.get("export").result, {})

    def test_contract_rejects_contradictions_and_fractional_counts(self):
        for contract in (
            {"bounds_min": [3, 0, 0], "bounds_max": [1, 1, 1]},
            {"max_vertices": 1.2},
            {"min_faces": 5, "max_faces": 2},
            {"anchor_object": "Cube"},
            {"require_rig": "yes"},
        ):
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                Workflow.from_plan(
                    "bad",
                    {
                        "tasks": [
                            {"id": "a", "expert": "modeler", "prompt": "a", "contract": contract}
                        ]
                    },
                )

    def test_recovery_rejects_changed_or_missing_content(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "asset.glb"
            path.write_bytes(b"original")
            evidence = file_evidence(path, root=folder)
            path.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "changed"):
                verify_evidence(evidence, root=folder)
            with self.assertRaisesRegex(ValueError, "no integrity"):
                verify_evidence({"path": str(path)})

    @patch("ai_modeling_assistant.core.media.HTTPClient")
    def test_uncertain_remote_submission_never_replays_post(self, client):
        with tempfile.TemporaryDirectory() as folder:
            atomic_json(
                Path(folder) / "remote-job.json",
                {
                    "protocol": "bridge",
                    "model": "fixture",
                    "capability": "world",
                    "state": "submitting",
                    "job_id": None,
                },
            )
            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                recover(ProviderConfig(protocol="bridge", model="fixture"), folder)
            client.assert_not_called()

    @patch("ai_modeling_assistant.core.media.HTTPClient")
    def test_completed_receipt_recovers_verified_asset_without_network(self, client):
        with tempfile.TemporaryDirectory() as folder:
            asset = Path(folder) / "asset.glb"
            asset.write_bytes(b"fixture")
            atomic_json(
                Path(folder) / "remote-job.json",
                {
                    "protocol": "bridge",
                    "model": "fixture",
                    "capability": "world",
                    "state": "succeeded",
                    "artifacts": [dict(file_evidence(asset), kind="world")],
                },
            )
            result = recover(ProviderConfig(protocol="bridge", model="fixture"), folder)
            self.assertTrue(result["recovered"])
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
