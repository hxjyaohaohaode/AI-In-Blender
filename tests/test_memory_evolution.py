import json
import math
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

from ai_modeling_assistant.core.memory import MemoryStore, RevisionConflict, tokens
from ai_modeling_assistant.core.context import compression_source, COMPRESSION_SYSTEM, build_context
from ai_modeling_assistant.core.budget import ensure_budget
from ai_modeling_assistant.core.config import ProviderConfig


class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = MemoryStore(Path(self.tmp.name) / "memory.db")
        self.db.project("p")
        self.thread = self.db.new_thread("p")
        self.turn = self.db.append(self.thread, "user", "单位使用米，颜色用蓝色。")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def propose(self, scope="project", value="单位使用米", **kwargs):
        return self.db.propose(
            "p",
            self.thread,
            scope=scope,
            key="units",
            kind="constraint",
            value=value,
            sources=[{"turn_id": self.turn, "quote": "单位使用米"}],
            **kwargs,
        )

    def test_more_specific_scope_beats_personal_default(self):
        personal = self.propose(scope="user", value="feet")
        project = self.propose(value="meters")
        for item in (personal, project):
            self.db.review(item["id"], 1, action="verify")
        found = self.db.retrieve("p", self.thread, "units")
        self.assertEqual([m["value"] for m in found], ["meters"])
        self.assertIn("scope precedence", found[0]["retrieval_reason"])

    def test_forgotten_fact_cannot_be_relearned_by_repeated_extraction(self):
        item = self.propose()
        self.db.save_summary(self.thread, [self.turn], {"constraints": ["单位使用米"]})
        self.db.forget(item["id"], 1)
        self.assertIsNone(self.db.summary(self.thread))
        with self.assertRaisesRegex(ValueError, "suppressed"):
            self.propose()
        self.assertEqual(self.db.versions(item["id"]), [])

    def test_new_evidence_merges_with_revision_without_auto_verification(self):
        old = self.propose()
        self.turn = self.db.append(self.thread, "user", "请继续保持单位使用米")
        new = self.propose()
        self.assertEqual(new["id"], old["id"])
        self.assertEqual(new["revision"], 2)
        self.assertEqual(len(new["sources"]), 2)
        self.assertEqual(new["status"], "candidate")
        with self.assertRaises(RevisionConflict):
            self.db.review(new["id"], 1, action="verify")

    def test_unrelated_historical_observation_does_not_pollute_every_prompt(self):
        self.db.observe(
            "p", "observed:vehicle", "Automobile wheel structure passed", {"fingerprint": "a"}
        )
        self.assertEqual(self.db.retrieve("p", self.thread, "海底珊瑚"), [])

    def test_expired_candidate_gets_fresh_lifecycle(self):
        old = self.propose(scope="session")
        self.db.db.execute("UPDATE memories SET expires=0 WHERE id=?", (old["id"],))
        new = self.propose(scope="session")
        self.assertNotEqual(new["id"], old["id"])
        self.assertEqual(new["status"], "candidate")

    def test_nonfinite_confidence_and_failed_evidence_are_rejected(self):
        for importance in (math.nan, math.inf, True):
            with self.assertRaises(ValueError):
                self.propose(importance=importance)
        self.turn = self.db.append(self.thread, "user", "单位使用米", state="failed")
        with self.assertRaises(ValueError):
            self.propose()

    def test_episodes_remember_failure_then_resolution_without_cross_project_leak(self):
        self.db.record_episode(
            "p", "run", "material", "blue ceramic mug", "failed", {"error": "missing UV"}
        )
        self.db.record_episode(
            "p",
            "run",
            "material",
            "blue ceramic mug",
            "succeeded",
            {"fingerprint": "b"},
            attempts=2,
        )
        self.assertEqual(self.db.recall_episodes("p", "ceramic")[0]["attempts"], 2)
        self.db.project("other")
        self.assertEqual(self.db.recall_episodes("other", "ceramic"), [])
        self.db.forget_project("p")
        self.assertEqual(self.db.recall_episodes("p", "ceramic"), [])

    def test_summary_cannot_skip_a_turn_or_regress(self):
        second = self.db.append(self.thread, "assistant", "noted")
        with self.assertRaises(ValueError):
            self.db.save_summary(self.thread, [second], {"goals": []})
        self.db.save_summary(self.thread, [self.turn, second], {"goals": []})
        with self.assertRaises(RevisionConflict):
            self.db.save_summary(self.thread, [self.turn], {"goals": []})

    def test_competing_summary_writers_cannot_both_commit_the_same_coverage(self):
        ready, first_read, second_done = Barrier(2), Event(), Event()
        path = Path(self.tmp.name) / "memory.db"

        def writer(first):
            with MemoryStore(path) as db:
                ready.wait(timeout=5)
                if first:
                    original = db.summary

                    def snapshot(thread):
                        result = original(thread)
                        first_read.set()
                        # Without the transaction, the second writer can commit
                        # after this read and both would silently insert a row.
                        second_done.wait(timeout=0.3)
                        return result

                    db.summary = snapshot
                else:
                    first_read.wait(timeout=5)
                try:
                    db.save_summary(self.thread, [self.turn], {"goals": ["meters"]})
                    return "saved"
                except RevisionConflict:
                    return "stale"
                finally:
                    if not first:
                        second_done.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(writer, True)
            second = pool.submit(writer, False)
            self.assertCountEqual(
                [first.result(timeout=10), second.result(timeout=10)], ["saved", "stale"]
            )
        self.assertEqual(self.db.db.execute("SELECT COUNT(*) FROM summaries").fetchone()[0], 1)

    def test_compressor_budget_includes_json_system_and_preserves_full_source(self):
        for i in range(15):
            self.db.append(
                self.thread, "user" if i % 2 == 0 else "assistant", "精确尺寸约束" * 300 + str(i)
            )
        source = compression_source(self.db, self.thread, 2000)
        self.assertIsNotNone(source)
        self.assertLessEqual(
            tokens(json.dumps(source, ensure_ascii=False)) + tokens(COMPRESSION_SYSTEM) + 64, 2000
        )
        originals = {t["id"]: t["content"] for t in self.db.turns(self.thread)}
        for turn in source["turns"]:
            self.assertEqual(turn["text"], originals[turn["id"]])
        self.assertEqual(source["source_ids"], [self.turn])

    def test_latest_intent_is_complete_and_omissions_explicit(self):
        for i in range(20):
            self.db.append(self.thread, "user", "detail " * 300 + str(i))
        self.db.append(self.thread, "user", "只改底座，不改变柱体")
        context = build_context(self.db, "p", self.thread, budget=1800)
        self.assertGreater(context["omitted_turns"], 0)
        self.assertEqual(context["messages"][-1]["content"], "只改底座，不改变柱体")
        ensure_budget(
            ProviderConfig(model="fixture", max_tokens=128),
            context["messages"],
            context["system"],
            requested=1800,
        )

    def test_budget_applies_after_images_and_output_reservation(self):
        config = ProviderConfig(model="fixture", max_tokens=1024, options={"context_window": 4096})
        with self.assertRaisesRegex(ValueError, "budget"):
            ensure_budget(
                config,
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "edit"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64,AA=="},
                            },
                        ],
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
