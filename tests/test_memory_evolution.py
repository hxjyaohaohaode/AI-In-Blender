import json
import math
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

from ai_modeling_assistant.core.memory import MemoryStore, RevisionConflict, tokens
from ai_modeling_assistant.core.context import compression_source, COMPRESSION_SYSTEM, build_context
from ai_modeling_assistant.core.context import compression_request
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

    def test_failure_evidence_survives_repair_and_idempotent_recording(self):
        self.db.record_episode("p", "r", "uv", "ceramic cup", "failed", {"error": "missing UV"})
        for _ in range(2):
            self.db.record_episode(
                "p", "r", "uv", "ceramic cup", "succeeded", {"fingerprint": "ok"}, attempts=2
            )
        episode = self.db.recall_episodes("p", "cup")[0]
        self.assertEqual([e["outcome"] for e in episode["history"]], ["failed", "succeeded"])
        self.assertEqual(episode["history"][0]["evidence"]["error"], "missing UV")
        with self.assertRaises(RevisionConflict):
            self.db.record_episode("p", "r", "uv", "ceramic cup", "failed", {}, attempts=1)
        self.db.forget_project("p")
        self.assertEqual(self.db.episode_history(episode["id"]), [])

    def test_forgetting_invalidates_inflight_summary_without_resurrecting_it(self):
        item = self.propose()
        epoch = self.db.memory_epoch()
        self.db.forget(item["id"], 1)
        with self.assertRaises(RevisionConflict):
            self.db.save_summary(
                self.thread, [self.turn], {"constraints": ["meters"]}, expected_epoch=epoch
            )
        self.assertIsNone(self.db.summary(self.thread))

    def test_expert_memory_never_silently_drops_a_pinned_constraint(self):
        item = self.propose(importance=1)
        self.db.review(item["id"], 1, action="verify")
        with self.assertRaisesRegex(ValueError, "Pinned constraints"):
            self.db.retrieve("p", self.thread, "unrelated", budget=1, require_pinned=True)
        self.assertEqual(
            self.db.retrieve("p", self.thread, "unrelated", require_pinned=True)[0]["id"],
            item["id"],
        )

    def test_schema_two_upgrade_retains_episode_and_creates_one_history_event(self):
        self.db.record_episode("p", "r", "uv", "ceramic", "failed", {"error": "UV"})
        self.db.db.execute("DROP TABLE episode_events")
        self.db.db.execute("DROP TABLE memory_state")
        self.db.db.execute("PRAGMA user_version=2")
        path = Path(self.tmp.name) / "memory.db"
        self.db.close()
        self.db = MemoryStore(path)
        self.assertEqual(self.db.db.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(len(self.db.recall_episodes("p", "ceramic")[0]["history"]), 1)
        with MemoryStore(path) as again:
            self.assertEqual(len(again.recall_episodes("p", "ceramic")[0]["history"]), 1)

    def test_long_conversation_compacts_oldest_prefix_and_keeps_latest_intent(self):
        with self.db.transaction():
            self.db.db.executemany(
                "INSERT INTO turns(thread_id,role,content,created,state,metadata) VALUES(?,?,?,?,?,?)",
                [
                    (self.thread, "user", "Preserve exact dimensions. " * 20, i, "complete", "{}")
                    for i in range(10010)
                ],
            )
        self.db.append(self.thread, "user", "LATEST INTENT: edit the base only")
        source = compression_source(self.db, self.thread, 2000)
        self.assertEqual(source["source_ids"][0], self.turn)
        self.db.save_summary(self.thread, source["source_ids"], {"goals": ["meters"]})
        context = build_context(self.db, "p", self.thread, budget=2000)
        self.assertEqual(context["raw_turns"], 10012)
        self.assertEqual(context["messages"][-1]["content"], "LATEST INTENT: edit the base only")
        self.assertGreater(context["omitted_turns"], 9900)

    def test_compaction_coverage_does_not_fill_the_model_request(self):
        source = {
            "source_ids": list(range(100000)),
            "memory_epoch": 1,
            "previous": {"goals": [{"text": "Keep metric units", "sources": [1]}]},
            "turns": [{"id": 100000, "role": "user", "text": "Make it blue"}],
        }
        request = compression_request(source)
        self.assertEqual(request["source_ids"], [1, 100000])
        self.assertLess(tokens(json.dumps(request)), 200)

    def test_project_export_retains_full_memory_and_episode_histories(self):
        item = self.propose()
        self.db.review(item["id"], 1, action="verify")
        for attempt in range(1, 26):
            self.db.record_episode(
                "p", "r", "uv", "ceramic", "failed", {"error": str(attempt)}, attempts=attempt
            )
        exported = self.db.export_project("p")
        self.assertEqual(len(exported["episodes"][0]["history"]), 25)
        self.assertEqual(len(exported["memories"][0]["versions"]), 2)

    def test_structured_credential_redaction_preserves_valid_json(self):
        evidence = {
            "error": "api_key=abcdefghijk",
            "nested": {"password": "abcd"},
            "context": "keep this",
        }
        self.db.record_episode("p", "r", "model", "asset", "failed", evidence)
        result = self.db.recall_episodes("p", "asset")[0]["evidence"]
        self.assertEqual(result["context"], "keep this")
        self.assertNotIn("abcd", json.dumps(result))
        self.db.save_summary(self.thread, [self.turn], evidence)
        self.assertEqual(json.loads(self.db.summary(self.thread)["body"])["context"], "keep this")


if __name__ == "__main__":
    unittest.main()
