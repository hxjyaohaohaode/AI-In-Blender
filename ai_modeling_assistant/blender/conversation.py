"""Persistent dialogue, automatic summarization and source-checked memory proposals."""

import json
import os
from pathlib import Path
import uuid
import bpy
from ..core.memory import MemoryStore, tokens
from ..core.context import (
    build_context,
    compression_source,
    validate_summary,
    extractive_summary,
    apply_proposals,
    COMPRESSION_SYSTEM,
    EXTRACTION_SYSTEM,
)
from ..core.process import ProcessJob
from ..core.responses import extract_json
from ..core.budget import ensure_budget
from .state import provider_for, _cost_tracker
from .scene import SceneContextGenerator

_jobs = {}
_ui_cache = {}


def database_path():
    override = os.environ.get("AI_IN_BLENDER_MEMORY_DB")
    return (
        Path(override)
        if override
        else Path(bpy.utils.user_resource("DATAFILES", path="AIInBlender", create=True))
        / "platform.sqlite3"
    )


def store():
    return MemoryStore(database_path())


def identity(scene, db):
    props = scene.ama_props
    if not props.project_id:
        props.project_id = (
            next(
                (
                    s.ama_props.project_id
                    for s in bpy.data.scenes
                    if s != scene and s.ama_props.project_id
                ),
                "",
            )
            or uuid.uuid4().hex
        )
    db.project(props.project_id, Path(bpy.data.filepath).stem or scene.name)
    try:
        db.thread(props.thread_id, props.project_id)
    except ValueError:
        props.thread_id = db.new_thread(props.project_id)
    return props.project_id, props.thread_id


def refresh(scene):
    with store() as db:
        project_id, thread_id = identity(scene, db)
        turns = db.turns(thread_id)
        scene.ama_props.chat_preview = "\n\n".join(
            f"{t['role']}: {t['content'][:800]}" for t in turns[-4:]
        )
        memories = db.visible(project_id, thread_id)
        candidates = sum(m["status"] in {"candidate", "conflict"} for m in memories)
        confirmed = sum(m["status"] == "verified" for m in memories)
        scene.ama_props.memory_status = (
            f"{confirmed} confirmed · {candidates} need review · {len(turns)} stored turns"
        )
        _ui_cache[scene.as_pointer()] = {
            "memories": memories,
            "threads": db.threads(project_id),
            "projects": db.projects(),
        }
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def busy(scene):
    return scene.as_pointer() in _jobs


class Dialogue:
    def __init__(self, scene, text, *, job_factory=ProcessJob):
        self.scene, self.job_factory = scene, job_factory
        self.job = None
        self.stage = ""
        self.source = None
        self.compression_rounds = 0
        self.config = provider_for("chat", "conversation", scene)
        self.budget = self.config.input_budget(scene.ama_props.context_budget)
        if self.config.protocol != "chat":
            raise ValueError("Persistent dialogue requires a Chat Completions provider")
        self.folder = database_path().parent / "dialogue"
        self.folder.mkdir(parents=True, exist_ok=True)
        with store() as db:
            self.project_id, self.thread_id = identity(scene, db)
            from .inputs import items

            self.inputs = {
                "attachments": items(scene),
                "region": json.loads(scene.ama_props.region_json or "[]"),
            }
            self.user_turn = db.append(self.thread_id, "user", text, metadata=self.inputs)
            if scene.ama_props.semantic_compression:
                self.source = compression_source(db, self.thread_id, self.budget)
        if self.source:
            self.submit(
                "compress",
                COMPRESSION_SYSTEM,
                [{"role": "user", "content": json.dumps(self.source, ensure_ascii=False)}],
            )
        else:
            self.respond()

    def submit(self, stage, system, messages):
        accounting = ensure_budget(self.config, messages, system, requested=self.budget)
        if stage == "compress":
            self.compression_rounds += 1
        with store() as db:
            db.event(
                self.project_id,
                "dialogue_dispatch",
                dict(accounting, stage=stage, turn=self.user_turn),
            )
        self.stage = stage
        self.scene.ama_props.chat_status = {
            "compress": "Compressing context with source references…",
            "respond": "Thinking with conversation and verified memory…",
            "extract": "Preparing source-backed memory candidates…",
        }[stage]
        self.job = self.job_factory(
            {
                "action": "chat",
                "config": self.config.payload(),
                "messages": messages,
                "system_prompt": system,
                "capability": "chat",
                "prompt": system,
                "output_dir": str(self.folder),
            }
        )

    def respond(self):
        with store() as db:
            context = build_context(
                db,
                self.project_id,
                self.thread_id,
                budget=self.budget,
                scene=SceneContextGenerator.generate(),
                use_memory=self.scene.ama_props.memory_retrieval,
                include_user=self.scene.ama_props.personal_memory,
            )
            db.event(
                self.project_id,
                "context_built",
                {k: v for k, v in context.items() if k not in {"system", "messages"}},
            )
        from .inputs import attach_to_messages

        attach_to_messages(self.scene, context["messages"], self.config, snapshot=self.inputs)
        self.submit("respond", context["system"], context["messages"])

    def tick(self):
        result = self.job.poll()
        if result is None:
            return True
        self.job = None
        if not result.get("error"):
            _cost_tracker.record(
                result.get("prompt_tokens", 0),
                result.get("completion_tokens", 0),
                result.get("cost"),
            )
        if self.stage == "compress":
            with store() as db:
                try:
                    if result.get("error"):
                        raise ValueError(result["error"])
                    body = validate_summary(
                        extract_json(result.get("content", "")), self.source["source_ids"]
                    )
                    mode = "semantic"
                except ValueError:
                    body, mode = extractive_summary(self.source), "extractive"
                db.save_summary(self.thread_id, self.source["source_ids"], body, mode=mode)
                db.event(
                    self.project_id,
                    "context_compressed",
                    {"mode": mode, "through_id": max(self.source["source_ids"])},
                )
            # Catch up incrementally after long conversations without an unbounded
            # maintenance loop or dropping the oldest unsummarized giant turn.
            with store() as db:
                self.source = (
                    compression_source(db, self.thread_id, self.budget)
                    if self.compression_rounds < 3
                    else None
                )
            if self.source:
                self.submit(
                    "compress",
                    COMPRESSION_SYSTEM,
                    [{"role": "user", "content": json.dumps(self.source, ensure_ascii=False)}],
                )
            else:
                self.respond()
            return True
        if result.get("error"):
            raise ValueError(result["error"])
        if self.stage == "respond":
            content = result.get("content", "").strip()
            if not content:
                raise ValueError("Model returned no dialogue text")
            with store() as db:
                db.append(
                    self.thread_id, "assistant", content, metadata={"model": self.config.model}
                )
            refresh(self.scene)
            if self.scene.ama_props.memory_enabled:
                with store() as db:
                    source = {
                        "user_turns": [
                            t
                            for t in db.turns(self.thread_id, after=self.user_turn - 1)
                            if t["role"] == "user"
                        ],
                        "existing_memories": [
                            {k: m[k] for k in ("key", "value", "scope", "status", "revision")}
                            for m in db.visible(self.project_id, self.thread_id)[:40]
                        ],
                    }
                # Metadata retains local provenance, but the extraction model needs only user text.
                source["user_turns"] = [
                    {k: t[k] for k in ("id", "role", "content")} for t in source["user_turns"]
                ]
                while (
                    source["existing_memories"]
                    and tokens(json.dumps(source, ensure_ascii=False)) + tokens(EXTRACTION_SYSTEM)
                    > self.budget
                ):
                    source["existing_memories"].pop()
                if (
                    tokens(json.dumps(source, ensure_ascii=False)) + tokens(EXTRACTION_SYSTEM)
                    > self.budget
                ):
                    self.scene.ama_props.chat_status = (
                        "Reply saved; memory extraction skipped to respect the input budget"
                    )
                    return False
                self.submit(
                    "extract",
                    EXTRACTION_SYSTEM,
                    [{"role": "user", "content": json.dumps(source, ensure_ascii=False)}],
                )
                return True
        elif self.stage == "extract":
            with store() as db:
                result = apply_proposals(
                    db,
                    self.project_id,
                    self.thread_id,
                    extract_json(result.get("content", "")),
                    allow_user=self.scene.ama_props.personal_memory,
                )
                db.event(self.project_id, "memory_proposals", result)
        self.scene.ama_props.chat_status = "Reply saved · memory candidates need your review"
        refresh(self.scene)
        return False

    def cancel(self):
        if self.job:
            self.job.cancel()
            self.job = None
        self.scene.ama_props.chat_status = "Cancelled locally; stored conversation is preserved"


def _tick():
    for key, dialogue in list(_jobs.items()):
        try:
            if dialogue.scene != bpy.context.scene:
                dialogue.cancel()
                _jobs.pop(key, None)
                continue
            again = dialogue.tick()
        except Exception as exc:
            if dialogue.job:
                dialogue.job.cancel()
            dialogue.scene.ama_props.chat_status = (
                "Memory maintenance failed; reply preserved: "
                if dialogue.stage == "extract"
                else "Conversation stopped: "
            ) + str(exc)[:350]
            again = False
        if not again:
            _jobs.pop(key, None)
    return 0.2 if _jobs else None


def send(scene, text=None, *, job_factory=ProcessJob):
    if busy(scene):
        raise ValueError("Wait for this conversation or cancel it")
    text = text or scene.ama_props.chat_input
    if not text.strip():
        raise ValueError("Write a message")
    dialogue = Dialogue(scene, text, job_factory=job_factory)
    _jobs[scene.as_pointer()] = dialogue
    scene.ama_props.chat_input = ""
    refresh(scene)
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.1)
    return dialogue


def cancel(scene):
    job = _jobs.pop(scene.as_pointer(), None)
    if job:
        job.cancel()


def shutdown():
    for dialogue in list(_jobs.values()):
        dialogue.cancel()
    _jobs.clear()
    _ui_cache.clear()
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
