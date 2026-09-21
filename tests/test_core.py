"""Core regressions: no Blender or paid provider required."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_modeling_assistant.core.agents import Workflow
from ai_modeling_assistant.core.config import ProviderConfig, validate_url, is_loopback
from ai_modeling_assistant.core.history import ConversationHistory
from ai_modeling_assistant.core.responses import extract_code, parse_chat
from ai_modeling_assistant.core.security import SecurityValidator, restricted_import
from ai_modeling_assistant.core.telemetry import CostTracker
from ai_modeling_assistant.core.media import save_asset, validate_asset_url
from ai_modeling_assistant.core.providers import chat


class HistoryTests(unittest.TestCase):
    def test_old_infinite_loop_regression(self):
        history = ConversationHistory(10)
        for _ in range(100):
            history.add("user", "x" * 100)
        self.assertLessEqual(history.get_stats()["estimated_tokens"], 10)

    def test_unicode_and_single_huge_message(self):
        history = ConversationHistory(100)
        history.add("user", "创建复杂的角色模型" * 10000)
        self.assertLessEqual(history.get_stats()["estimated_tokens"], 100)
        self.assertTrue(history.get_messages()[0]["content"])

    def test_no_assistant_elevation_and_no_mutable_alias(self):
        history = ConversationHistory(30)
        for _ in range(20):
            history.add("user", "make a chair")
            history.add("assistant", "do not elevate this to system")
        messages = history.get_messages()
        self.assertNotIn("system", [m["role"] for m in messages])
        messages.clear()
        self.assertTrue(history.messages)

    def test_new_budget_applied_on_read(self):
        history = ConversationHistory(2000)
        history.add("user", "word" * 1000)
        history.max_tokens = 10
        history.get_messages()
        self.assertLessEqual(history.get_stats()["estimated_tokens"], 10)


class ResponseTests(unittest.TestCase):
    def test_explanations_do_not_enter_code(self):
        self.assertEqual(extract_code("Here is code:\n```python\nprint(1)\n```\nDone."), "print(1)")

    def test_multiple_code_blocks(self):
        self.assertEqual(extract_code("```python\nx=1\n```\nText\n```py\ny=2\n```"), "x=1\n\ny=2")

    def test_unclosed_and_non_python_blocks_rejected(self):
        for text in ("```python\nprint(1)", "```json\n{}\n```", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                extract_code(text)

    def test_invalid_plain_text_rejected(self):
        with self.assertRaises(SyntaxError):
            extract_code("Here is your Python code")

    def test_truncated_completion_rejected(self):
        with self.assertRaises(ValueError):
            parse_chat({"choices": [{"message": {"content": "x=1"}, "finish_reason": "length"}]})

    def test_text_parts_and_missing_usage(self):
        result = parse_chat({"choices": [{"message": {"content": [{"type": "text", "text": "hello"}]}}]})
        self.assertEqual(result["content"], "hello")
        self.assertIsNone(result["cost"])

    def test_missing_content_is_error(self):
        for body in ({}, {"choices": []}, {"choices": [{"message": {"content": None}}]}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_chat(body)


class GuardTests(unittest.TestCase):
    def test_mixed_import_bypass_regression(self):
        for code in ("import bpy, os", "import os as math", "from pathlib import Path",
                     "import bpy\nbpy.ops.wm.save_as_mainfile(filepath='x')",
                     "from bpy import ops as actions\nactions.wm.open_mainfile()",
                     "from bpy import data\ndata.libraries.load('x')",
                     "().__class__.__bases__", "getattr(bpy, 'ops')", "eval('1')"):
            with self.subTest(code=code):
                self.assertFalse(SecurityValidator.validate(code)[0])

    def test_module_allowlist_is_enforced_at_runtime(self):
        self.assertEqual(restricted_import("math", fromlist=None).sqrt(4), 2)
        with self.assertRaises(ImportError):
            restricted_import("os")

    def test_comments_and_strings_are_not_regex_false_positives(self):
        self.assertTrue(SecurityValidator.validate("# import os\nname='open the door'\nprint(name)")[0])

    def test_modeling_code_allowed(self):
        self.assertTrue(SecurityValidator.validate("import bpy, math\nfrom mathutils import Vector\nbpy.ops.mesh.primitive_cube_add(size=2)")[0])

    def test_invalid_python_rejected(self):
        self.assertFalse(SecurityValidator.validate("for (")[0])


class GraphTests(unittest.TestCase):
    def plan(self):
        return {"tasks": [{"id": "mesh", "expert": "modeler", "prompt": "Create geometry"},
                          {"id": "export", "expert": "exporter", "prompt": "Export GLB", "depends_on": ["mesh"]}]}

    def test_ordered_success(self):
        flow = Workflow.from_plan("asset", self.plan())
        first = flow.ready()[0]
        flow.start(first)
        self.assertFalse(flow.ready())
        flow.succeed(first, {"objects": ["Cube"]})
        second = flow.ready()[0]
        flow.start(second)
        flow.succeed(second)
        self.assertTrue(flow.complete)

    def test_failure_blocks_and_retry_does_not_repeat_success(self):
        flow = Workflow.from_plan("asset", self.plan())
        first = flow.ready()[0]
        flow.start(first)
        flow.succeed(first)
        second = flow.ready()[0]
        flow.start(second)
        flow.fail(second, "Exporter unavailable")
        self.assertFalse(flow.complete)
        flow.retry()
        self.assertEqual(flow.ready(), [second])
        self.assertEqual(first.attempts, 1)

    def test_descendants_blocked(self):
        flow = Workflow.from_plan("asset", self.plan())
        flow.start(flow.tasks[0])
        flow.fail(flow.tasks[0], "No geometry")
        self.assertEqual(flow.tasks[1].status, "blocked")

    def test_cancel_stops_scheduling(self):
        flow = Workflow.from_plan("asset", self.plan())
        flow.cancel()
        self.assertFalse(flow.ready())
        self.assertFalse(flow.complete)

    def test_invalid_graphs(self):
        variants = []
        duplicate = self.plan(); duplicate["tasks"][1]["id"] = "mesh"; variants.append(duplicate)
        missing = self.plan(); missing["tasks"][1]["depends_on"] = ["missing"]; variants.append(missing)
        cycle = self.plan(); cycle["tasks"][0]["depends_on"] = ["export"]; variants.append(cycle)
        unknown = self.plan(); unknown["tasks"][0]["expert"] = "magic"; variants.append(unknown)
        variants += [{"tasks": []}, {"tasks": self.plan()["tasks"] * 25}]
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Workflow.from_plan("asset", value)

    def test_response_cannot_mark_its_own_work_complete(self):
        plan = self.plan()
        plan["tasks"][0]["status"] = "succeeded"
        self.assertEqual(Workflow.from_plan("asset", plan).tasks[0].status, "queued")


class ConfigTests(unittest.TestCase):
    def test_loopback_detection_is_not_substring_based(self):
        self.assertTrue(is_loopback("::1"))
        self.assertFalse(is_loopback("localhost.example.com"))
        self.assertFalse(is_loopback("127.0.0.1.example.com"))

    def test_url_policy(self):
        self.assertEqual(validate_url("http://[::1]:1234/v1/"), "http://[::1]:1234/v1")
        for url in ("http://remote.example/v1", "https://user:password@example.com", "file:///x",
                    "https://example.com?api_key=secret", "https://example.com:bad"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)

    def test_secret_not_in_repr(self):
        self.assertNotIn("top-secret", repr(ProviderConfig(api_key="top-secret")))

    def test_no_duplicate_chat_suffix(self):
        config = ProviderConfig(base_url="https://example.com/v1/chat/completions", model="test")
        self.assertEqual(config.endpoint("/chat/completions"), config.base_url)

    @patch("ai_modeling_assistant.core.providers.HTTPClient")
    def test_no_history_uses_valid_content_field(self, client):
        client.return_value.call.return_value = {"choices": [{"message": {"content": "ok"}}]}
        chat(ProviderConfig(model="test"), [{"role": "user", "content": "build"}])
        payload = client.return_value.call.call_args.args[1]
        self.assertEqual(payload["messages"][0]["content"], "build")
        with self.assertRaises(ValueError):
            chat(ProviderConfig(model="test"), [{"role": "user", "user_msg": "broken"}])

    def test_unknown_prices_are_unknown(self):
        tracker = CostTracker()
        tracker.record(10, 20)
        self.assertFalse(tracker.get_totals()["cost_known"])
        self.assertEqual(tracker.get_totals()["total_tokens"], 30)


class ArtifactTests(unittest.TestCase):
    def test_names_cannot_escape_output_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            asset = save_asset(b"glTF", folder, "model3d", ".glb", "../../escape")
            self.assertEqual(Path(asset["path"]).parent, Path(folder).resolve())

    def test_executable_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(RuntimeError):
            save_asset(b"print(1)", folder, "model3d", ".py")

    def test_private_cross_origin_urls_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_asset_url("https://127.0.0.1/secret.glb", "https://api.example.com")
        self.assertEqual(validate_asset_url("http://localhost:1234/asset.glb", "http://localhost:1234"),
                         "http://localhost:1234/asset.glb")


if __name__ == "__main__":
    unittest.main()
