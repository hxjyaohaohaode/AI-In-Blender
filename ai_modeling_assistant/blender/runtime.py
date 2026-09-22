"""Main-thread expert orchestration, cancellable provider jobs and run journals."""

import json
import sqlite3
from pathlib import Path
import time
import uuid
import bpy
from ..core.agents import Workflow, EXPERTS, CODE_EXPERTS, planner_prompt
from ..core.process import ProcessJob
from ..core.responses import extract_code, extract_json
from ..core.artifacts import atomic_json, file_evidence, verify_evidence
from ..core.budget import ensure_budget
from ..data.prompts import SYSTEM_PROMPT
from .state import provider_for, available_capabilities, _cost_tracker, get_conversation
from .scene import SceneContextGenerator
from .compat import import_artifact, export_objects

_active = {}
_runs = {}
_all_runs = {}


def current(scene=None):
    scene = scene or bpy.context.scene
    return _runs.get(scene.as_pointer())


def busy():
    return any(run.running for run in _active.values())


def list_runs(scene):
    return [r for r in _all_runs.values() if r.scene == scene][-12:]


def focus(run):
    _runs[run.scene.as_pointer()] = run
    run.props.workflow_report = str(run.folder / "run.json")
    run.props.workflow_status = getattr(run, "status_text", "Ready")
    if run.workflow:
        run.props.plan_json = json.dumps(run.workflow.snapshot(), ensure_ascii=False)
        run.props.workflow_goal = run.workflow.goal
    if run.pending_code is not None:
        run.props.last_code = run.pending_code
        text = bpy.data.texts.get("AI Studio Code") or bpy.data.texts.new("AI Studio Code")
        text.clear()
        text.write(run.pending_code)


def _tick():
    for ident, run in list(_active.items()):
        try:
            again = run.tick()
        except Exception as exc:
            run.abort(str(exc))
            again = run.running
        if not again:
            _active.pop(ident, None)
    return 0.15 if _active else None


def activate(run):
    if run not in _active.values() and sum(r.running for r in _active.values()) >= 2:
        raise ValueError("At most two workflows can run at once")
    for other in _active.values():
        if (
            other is not run
            and other.running
            and set(run.targets) & {o.name for o in other.objects()}
        ):
            raise ValueError("These objects are owned by another running workflow")
    _active[run.folder.name] = run
    _all_runs[run.folder.name] = run
    focus(run)
    for ident, old in list(_all_runs.items()):
        if len(_all_runs) > 24 and not old.running and old is not current(old.scene):
            del _all_runs[ident]
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.1)


def shutdown():
    for run in list(_active.values()):
        run.cancel()
    _active.clear()
    _runs.clear()
    _all_runs.clear()
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)


def output_directory(scene):
    configured = scene.ama_props.artifact_dir
    base = (
        Path(bpy.path.abspath(configured))
        if configured
        else Path(bpy.utils.user_resource("DATAFILES", path="AIInBlender", create=True))
    )
    folder = base / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    return folder.resolve()


class StudioRun:
    def __init__(
        self,
        scene,
        workflow=None,
        *,
        targets=(),
        preview=False,
        job_factory=ProcessJob,
        parent=None,
        input_results=None,
        resume_folder=None,
    ):
        self.scene = scene
        self.workflow = workflow
        self.parent = parent
        self.input_results = input_results
        self.lanes = {}
        self._review_child = None
        self._quality_child = None
        self.peak_parallel = 0
        self._journal_signature = None
        self.dispatches = []
        self.active_dispatch = None
        self.targets = [o.name for o in targets]
        self.preview = preview
        self.job_factory = job_factory
        self.job = None
        self.scene_job = None
        self.scene_job_mode = "code"
        self.staged_result = None
        self.repairing_validation = False
        self.repairing_review = False
        self.review_evidence = ""
        self.review_images = []
        self.review_views = []
        self.pending_quality = None
        self.visual_approval = None
        self.calls = 0
        self.baseline = None
        self.task = None
        self.pending_code = None
        self.repairs = {}
        self.running = True
        self.planning = workflow is None
        self.collection_name = ""
        if parent:
            self.folder = parent.folder / (
                "task-" + workflow.tasks[0].id + "-" + uuid.uuid4().hex[:6]
            )
            self.folder.mkdir(parents=True)
        elif resume_folder:
            self.folder = Path(resume_folder).resolve()
        else:
            self.folder = output_directory(scene)
        self.last_code = ""
        from . import conversation, inputs

        if parent:
            self.project_id, self.thread_id = parent.project_id, parent.thread_id
            self.input_snapshot = parent.input_snapshot
        else:
            with conversation.store() as db:
                self.project_id, self.thread_id = conversation.identity(scene, db)
            from ..core.attachments import attachment

            audio = scene.ama_props.input_audio
            self.input_snapshot = {
                "attachments": inputs.items(scene),
                "region": json.loads(scene.ama_props.region_json or "[]"),
                "audio": attachment(bpy.path.abspath(audio), role="transcription")
                if audio
                else None,
            }
        if not parent:
            self.scene.ama_props.workflow_report = str(self.folder / "run.json")

    @property
    def props(self):
        return self.scene.ama_props

    @property
    def collection(self):
        return bpy.data.collections.get(self.collection_name)

    def objects(self):
        objects = list(self.collection.all_objects) if self.collection else []
        objects += [self.scene.objects[n] for n in self.targets if n in self.scene.objects]
        return list(dict.fromkeys(objects))

    def status(self, text):
        owner = self.parent or self
        owner.status_text = text
        if current(self.scene) is owner or current(self.scene) is None:
            self.props.workflow_status = text
            self.props.status_message = text
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {"VIEW_3D", "TEXT_EDITOR"}:
                    area.tag_redraw()

    def journal(self):
        if self.workflow is None:
            return
        data = self.workflow.snapshot()
        data.update(blender_version=bpy.app.version_string, collection=self.collection_name)
        data.update(
            calls=self.calls,
            visual_approval=self.visual_approval,
            pending_quality=self.pending_quality,
            peak_parallel=self.peak_parallel,
            project_id=self.project_id,
            thread_id=self.thread_id,
            dispatches=self.dispatches,
            input_snapshot=self.input_snapshot,
            repairs=self.repairs,
        )
        signature = json.dumps(data, ensure_ascii=False, sort_keys=True)
        if self._journal_signature == signature:
            return
        from .revision import fingerprint, delivery_revision

        data["checkpoint"] = {
            "fingerprint": fingerprint(self.objects()),
            "delivery_revision": delivery_revision(self.objects(), self.scene),
            "objects": [o.name for o in self.objects()],
            "targets": self.targets,
            "blend_file": bpy.data.filepath,
        }
        path = self.folder / "run.json"
        atomic_json(path, data)
        self._journal_signature = signature
        if self.parent:
            child_task = self.workflow.tasks[0]
            original = self.parent.workflow.get(child_task.id)
            original.result = json.loads(json.dumps(child_task.result))
            original.attempts = max(original.attempts, child_task.attempts)
            self.parent.repairs.update(self.repairs)
            if child_task.status == "succeeded" and original.status == "running":
                # Persist completion with the scene revision now, not on a later
                # timer tick that might never happen after a crash.
                self.parent.workflow.succeed(original, original.result)
            self.parent.journal()
        if not self.parent and (current(self.scene) is self or current(self.scene) is None):
            self.props.plan_json = json.dumps(data, ensure_ascii=False)

    def preflight(self):
        geometry = {
            t.id for t in self.workflow.tasks if t.expert in CODE_EXPERTS | {"world", "model3d"}
        }
        for task in self.workflow.tasks:
            if task.expert == "exporter" and not geometry <= {
                t.id for t in self.workflow.ancestors(task)
            }:
                raise ValueError(
                    "Every geometry-producing task must be a dependency of final export"
                )
        if (
            self.workflow.assembly.get("unit_scale") is not None
            and self.workflow.assembly["unit_scale"] != self.scene.unit_settings.scale_length
        ):
            raise ValueError(
                "Assembly unit_scale differs from the scene; reconcile units before running"
            )
        for task in self.workflow.tasks:
            if task.status == "succeeded":
                continue
            if task.capability != "builtin":
                provider_for(task.capability, task.expert, self.scene)
            if task.expert == "transcriber":
                from ..core.attachments import verified_bytes

                audio = self.input_snapshot.get("audio")
                if not audio or audio["kind"] != "audio":
                    raise ValueError("Select an audio input file before running transcription")
                verified_bytes(audio)
        if bpy.context.mode != "OBJECT":
            raise ValueError("Switch to Object Mode before starting a workflow")

    def start(self):
        self.preflight()
        if not self.collection:
            collection = bpy.data.collections.new("AI Studio " + self.folder.name)
            self.scene.collection.children.link(collection)
            self.collection_name = collection.name
        self.planning = False
        self.journal()
        self.status("Workflow ready")
        if not self.parent:
            activate(self)

    def plan(self, goal):
        if not goal.strip():
            raise ValueError("Enter a creative brief")
        config = provider_for("chat", "planner", self.scene)
        self.goal = goal
        prompt = goal + "\nScene facts:\n" + SceneContextGenerator.generate()
        messages = [{"role": "user", "content": prompt}]
        from . import conversation, inputs

        if self.props.thread_id:
            with conversation.store() as db:
                project, thread = conversation.identity(self.scene, db)
                from ..core.context import build_context

                if db.turns(thread):
                    context = build_context(
                        db,
                        project,
                        thread,
                        budget=max(1000, config.input_budget(self.props.context_budget) // 2),
                        include_user=self.props.personal_memory,
                        use_memory=self.props.memory_retrieval,
                    )
                    messages = context["messages"] + messages
        inputs.attach_to_messages(self.scene, messages, config, snapshot=self.input_snapshot)
        self.submit_chat(config, messages, planner_prompt(available_capabilities()))
        self.status("Planner is preparing the expert workflow…")
        activate(self)

    def submit_chat(self, config, messages, system):
        if config.protocol != "chat":
            raise ValueError(
                "Dialogue, planning and code/review experts require a Chat Completions provider; assign Bridge profiles to media experts"
            )
        accounting = ensure_budget(config, messages, system, requested=self.props.context_budget)
        self.reserve_dispatch(config, "chat", accounting)
        self.job = self.job_factory(
            {
                "action": "chat",
                "config": config.payload(),
                "messages": messages,
                "system_prompt": system,
                "capability": "chat",
                "output_dir": str(self.folder),
            }
        )

    def reserve_dispatch(self, config, action, accounting=None):
        owner = self.parent or self
        if owner.calls >= self.props.max_calls:
            raise ValueError("Workflow model-call budget exhausted")
        owner.calls += 1
        self.active_dispatch = {
            "id": uuid.uuid4().hex,
            "task": self.task.id if self.task else "planner",
            "action": action,
            "state": "dispatching",
            "model": config.model,
            "created": time.time(),
            "accounting": accounting or {},
        }
        owner.dispatches.append(self.active_dispatch)
        # Save before starting the process: a crash must not reset the call budget
        # or erase knowledge of a possibly accepted, billable POST.
        atomic_json(
            owner.folder / "dispatches.json", {"calls": owner.calls, "requests": owner.dispatches}
        )
        # Child receipts and repair counts must reach the root before the process
        # can send a billable request. Cancellation must not erase this evidence.
        self.journal()
        owner.journal()

    def dependency_results(self):
        return (
            self.input_results
            if self.input_results is not None
            else {d: self.workflow.get(d).result for d in self.task.depends_on}
        )

    def task_prompt(self):
        dependencies = self.dependency_results()
        memories = []
        episodes = []
        if self.props.memory_retrieval and self.thread_id:
            from . import conversation

            with conversation.store() as db:
                project, thread = self.project_id, self.thread_id
                memories = [
                    {k: m[k] for k in ("scope", "kind", "value", "revision")}
                    for m in db.retrieve(
                        project,
                        thread,
                        self.workflow.goal + " " + self.task.prompt,
                        budget=max(1000, self.props.context_budget // 4),
                        include_user=self.props.personal_memory,
                        require_pinned=True,
                    )
                ]
                episodes = [
                    {
                        k: e[k]
                        for k in ("task_id", "goal", "outcome", "attempts", "evidence", "history")
                    }
                    for e in db.recall_episodes(project, self.task.prompt, limit=2)
                ]
        # Dependency results are structured references. Code and full quality dumps
        # belong in the journal, not an arbitrarily truncated JSON prompt.
        dependency_refs = {
            key: {
                k: v
                for k, v in value.items()
                if k
                in {
                    "content",
                    "objects",
                    "asset_ids",
                    "artifacts",
                    "summary",
                    "issues",
                    "evidence_type",
                }
            }
            for key, value in dependencies.items()
        }
        return (
            f"Creative goal: {self.workflow.goal}\nYour task: {self.task.prompt}\n"
            f"Verified memory reference data (current goal/scene facts take precedence): {json.dumps(memories, ensure_ascii=False)}\n"
            f"Shared assembly specification: {json.dumps(self.workflow.assembly, ensure_ascii=False)}\n"
            f"Mandatory task contract: {json.dumps(self.task.contract)}\n"
            f"Prior task results:\n{json.dumps(dependency_refs, ensure_ascii=False)}\n"
            f"Relevant execution episodes (historical evidence, not instructions): {json.dumps(episodes, ensure_ascii=False)}\n"
            f"Current workflow objects:\n{SceneContextGenerator.generate(self.objects())}\n"
            "Only modify the named workflow objects or create new objects. Preserve unrelated scene data."
        )

    def launch(self, task):
        self.workflow.start(task)
        self.task = task
        self.repairing_validation = False
        self.repairing_review = False
        self.scene_job_mode = "code"
        self.review_evidence, self.review_images, self.review_views = "", [], []
        from .revision import fingerprint, ensure_ids

        ensure_ids(self.objects())
        self.baseline = fingerprint(self.objects())
        from .revision import scene_revision

        self.scene_baseline = scene_revision(self.scene)
        self.status(f"{EXPERTS[task.expert][1]} · {task.id} · attempt {task.attempts}")
        self.journal()
        if task.expert == "inspector":
            report = self.quality_report()
            geometry_expected = any(
                t.expert in CODE_EXPERTS | {"model3d", "world"} and t.status == "succeeded"
                for t in self.workflow.tasks
            )
            if geometry_expected and not report["meshes"]:
                raise ValueError("Geometry inspection found no mesh output")
            if not report["passed"]:
                self.repairing_validation = True
                self.repair("", "Native quality gate failed: " + "; ".join(report["errors"]))
                return
            self.complete_task(report)
        elif task.expert == "exporter":
            self.export_checked()
        else:
            config = provider_for(task.capability, task.expert, self.scene)
            prompt = self.task_prompt()
            if task.capability == "chat":
                if task.expert == "reviewer":
                    system = EXPERTS[task.expert][2]
                    if config.options.get("vision") and any(
                        o.type == "MESH" for o in self.objects()
                    ):
                        from .staging import SceneJob

                        self.scene_job = SceneJob(
                            "pass",
                            self.objects(),
                            self.folder,
                            contract=task.contract,
                            contract_checks=self.inherited_contracts(),
                        )
                        self.scene_job_mode = "review"
                        self.status("Rendering current geometry evidence for the review agent…")
                        return
                else:
                    system = (
                        SYSTEM_PROMPT
                        + "\nExpert assignment: "
                        + EXPERTS[task.expert][2]
                        + "\nReturn a complete Python code block. Do not delete scene objects or use files, "
                        "network, reflection, private attributes or bpy.ops.wm. Do not call export/import "
                        "operators. Use bmesh.ops.recalc_face_normals, not normals_make_consistent. "
                        "For Geometry Nodes modifier inputs call the provided set_geometry_input(modifier, "
                        "socket.identifier, value) helper; it handles both legacy and Blender 5.2 RNA sockets. "
                        "Do not read preferences. Current Blender: " + bpy.app.version_string
                    )
                messages = [{"role": "user", "content": prompt}]
                from .inputs import attach_to_messages

                attach_to_messages(self.scene, messages, config, snapshot=self.input_snapshot)
                if self.preview and self.props.include_history:
                    history = get_conversation()
                    history.add("user", prompt)
                    messages = history.get_messages()
                self.submit_chat(config, messages, system)
            else:
                submission = task.result.get("submission")
                if submission:
                    output = Path(submission["directory"]).resolve()
                    if self.folder not in output.parents and (
                        self.parent is None or self.parent.folder not in output.parents
                    ):
                        raise ValueError("Recovery submission is outside this run")
                    action = "recover"
                else:
                    output = self.folder / ("request-" + task.id + "-" + uuid.uuid4().hex[:8])
                    task.result["submission"] = {
                        "directory": str(output),
                        "protocol": config.protocol,
                        "model": config.model,
                    }
                    action = "generate"
                self.reserve_dispatch(config, action)
                self.journal()
                dependencies = [
                    {"task": d, "result": result} for d, result in self.dependency_results().items()
                ]
                supplied = (
                    dependencies + self.input_snapshot["attachments"]
                    if config.protocol == "bridge"
                    else self.input_snapshot["attachments"]
                )
                # Media providers receive their own focused prompt, not Python instructions.
                audio_path = ""
                if task.expert == "transcriber":
                    from ..core.attachments import verified_bytes

                    audio = self.input_snapshot["audio"]
                    # Persist exactly the verified bytes for the child. Changing
                    # the UI selection or source file cannot change this request.
                    frozen = self.folder / (
                        "transcription-input" + Path(audio["path"]).suffix.lower()
                    )
                    frozen.write_bytes(verified_bytes(audio))
                    audio_path = str(frozen)
                self.job = self.job_factory(
                    {
                        "action": action,
                        "config": config.payload(),
                        "capability": task.capability,
                        "prompt": task.prompt,
                        "output_dir": str(output),
                        "input_path": audio_path,
                        "inputs": supplied,
                    }
                )

    def tick(self):
        if not self.running:
            return False
        if self.scene != bpy.context.scene:
            self.cancel("Cancelled because the active scene changed")
            return False
        if (
            not self.parent
            and not self.planning
            and self.workflow
            and any(t.contract.get("part_id") for t in self.workflow.tasks)
        ):
            return self.tick_lanes()
        if self.scene_job is not None:
            result = self.staged_result if self.staged_result is not None else self.scene_job.poll()
            if result is None:
                return True
            if (
                self.scene_job_mode == "code"
                and not result.get("error")
                and bpy.context.mode != "OBJECT"
            ):
                self.staged_result = result
                self.status(
                    "Candidate ready. Finish the current interactive edit and return to Object Mode to validate and merge."
                )
                return True
            self.staged_result = None
            job, self.scene_job = self.scene_job, None
            if self.scene_job_mode == "review":
                self.scene_job_mode = "code"
                if result.get("error"):
                    self.abort("Review evidence failed: " + result["error"])
                    return False
                from .revision import fingerprint, scene_revision

                if (
                    fingerprint(self.objects()) != self.baseline
                    or scene_revision(self.scene) != self.scene_baseline
                ):
                    self.abort("Human edit conflict: reviewer snapshot is stale")
                    return False
                from ..core.attachments import attachment, vision_parts

                self.review_evidence = result.get("preview", "")
                config = provider_for("chat", "reviewer", self.scene)
                content = [
                    {
                        "type": "text",
                        "text": self.task_prompt()
                        + "\nEvidence view metadata: "
                        + json.dumps(result.get("evidence_views", []))
                        + "\nWorkbench views only support geometry review. Cycles studio material previews support material appearance, "
                        "not final scene lighting. Animation samples cover only the named frames, not continuous motion. "
                        "Only claim evidence actually attached to this request.",
                    }
                ]
                self.review_images, self.review_views = [], []
                for path in result.get("previews", [self.review_evidence]):
                    candidate = content + vision_parts([attachment(path)], enabled=True)
                    try:
                        ensure_budget(
                            config,
                            [{"role": "user", "content": candidate}],
                            EXPERTS["reviewer"][2],
                            requested=self.props.context_budget,
                        )
                    except ValueError:
                        if not self.review_images:
                            raise
                        break
                    content = candidate
                    self.review_images.append(path)
                    self.review_views.extend(
                        v for v in result.get("evidence_views", []) if v["path"] == path
                    )
                self.submit_chat(
                    config, [{"role": "user", "content": content}], EXPERTS["reviewer"][2]
                )
                return True
            if result.get("error"):
                self.repair(self.last_code, result["error"])
            else:
                try:
                    objects = job.commit(result, self.collection)
                except ValueError as exc:
                    self.abort(str(exc))
                    return self.running
                self.visual_approval = None
                if self.input_snapshot["region"]:
                    from .revision import fingerprint, scene_revision

                    for region in self.input_snapshot["region"]:
                        target = next(
                            o for o in objects if o.get("ama_asset_id") == region["asset_id"]
                        )
                        region["fingerprint"] = fingerprint([target])
                if self.repairing_review:
                    self.repairing_review = self.repairing_validation = False
                    from .revision import fingerprint, scene_revision

                    self.baseline = fingerprint(self.objects())
                    self.scene_baseline = scene_revision(self.scene)
                    config = provider_for("chat", "reviewer", self.scene)
                    if config.options.get("vision"):
                        from .staging import SceneJob

                        self.scene_job = SceneJob(
                            "pass",
                            self.objects(),
                            self.folder,
                            contract=self.task.contract,
                            contract_checks=self.inherited_contracts(),
                        )
                        self.scene_job_mode = "review"
                    else:
                        self.submit_chat(
                            config,
                            [{"role": "user", "content": self.task_prompt()}],
                            EXPERTS["reviewer"][2],
                        )
                    self.status("Repair committed; independent review must pass again")
                    return True
                self.complete_task(
                    {
                        "code": self.last_code,
                        "output": result["output"],
                        "objects": [o.name for o in objects],
                        "quality": job.quality,
                        "preview": result.get("preview", ""),
                        "previews": result.get("previews", []),
                        "evidence_views": result.get("evidence_views", []),
                        "branch": str(job.folder),
                    }
                )
        if self.job is not None:
            result = self.job.poll()
            if result is None:
                return True
            self.job = None
            if self.active_dispatch:
                self.active_dispatch["state"] = "failed" if result.get("error") else "returned"
                owner = self.parent or self
                atomic_json(
                    owner.folder / "dispatches.json",
                    {"calls": owner.calls, "requests": owner.dispatches},
                )
            if result.get("error"):
                self.abort(result["error"])
                return self.running
            _cost_tracker.record(
                result.get("prompt_tokens", 0),
                result.get("completion_tokens", 0),
                result.get("cost"),
            )
            if self.planning:
                self.workflow = Workflow.parse(self.goal, result.get("content", ""))
                self.journal()
                self.planning = False
                if self.props.auto_run_plan:
                    self.preflight()
                    collection = bpy.data.collections.new("AI Studio " + self.folder.name)
                    self.scene.collection.children.link(collection)
                    self.collection_name = collection.name
                else:
                    self.running = False
                    self.status("Plan ready — review the steps, then Run Plan")
                    return False
            else:
                self.consume(result)
        if (
            self.pending_code is not None
            or self.pending_quality is not None
            or self.scene_job is not None
        ):
            return True
        if self.job is None and self.running:
            ready = self.workflow.ready()
            if ready:
                self.launch(ready[0])
            elif self.workflow.complete:
                self.running = False
                self.status(f"Completed {len(self.workflow.tasks)} tasks · report saved")
                self.journal()
                return False
            else:
                self.abort("Workflow cannot advance; inspect the failed task")
                return False
        return self.running

    def consume(self, result):
        if self.task.expert in CODE_EXPERTS or self.repairing_validation:
            raw = result.get("content", "")
            if self.preview and self.props.include_history:
                get_conversation().add("assistant", raw)
            try:
                code = extract_code(raw)
            except (ValueError, SyntaxError) as exc:
                self.repair(raw, str(exc))
                return
            self.last_code = code
            if current(self.scene) is (self.parent or self):
                self.props.last_code = code
                text = bpy.data.texts.get("AI Studio Code") or bpy.data.texts.new("AI Studio Code")
                text.clear()
                text.write(code)
            if self.preview or self.props.review_code:
                self.pending_code = code
                self.status(f"Review generated code for {self.task.id}, then Apply Code")
            else:
                self.execute_code(code)
        elif self.task.expert == "reviewer":
            from .revision import fingerprint, scene_revision

            if (
                fingerprint(self.objects()) != self.baseline
                or scene_revision(self.scene) != self.scene_baseline
            ):
                self.abort("Human edit conflict: model changed during creative review")
                return
            report = extract_json(result.get("content", ""))
            if not isinstance(report, dict) or not isinstance(report.get("passed"), bool):
                raise ValueError("Reviewer must return a JSON object with a boolean passed field")
            if not report["passed"]:
                self.task.result = report
                self.repairing_review = self.repairing_validation = True
                self.repair(
                    "", "Creative review needs changes: " + json.dumps(report, ensure_ascii=False)
                )
                return
            report["evidence_type"] = (
                "rendered previews and scene facts; per-view evidence types recorded"
                if self.review_evidence
                else "textual scene facts; no visual evidence"
            )
            report["preview"] = self.review_evidence
            report["previews"] = list(self.review_images)
            report["reviewed_view_count"] = len(self.review_images)
            report["evidence_views"] = list(self.review_views)
            report["fingerprint"] = self.baseline
            self.complete_task(report)
        else:
            artifacts = result.get("artifacts", [])
            from .revision import fingerprint, scene_revision

            if (
                fingerprint(self.objects()) != self.baseline
                or scene_revision(self.scene) != self.scene_baseline
            ):
                raise ValueError(
                    "Scene changed during media generation; files are retained, import requires a fresh run"
                )
            from .compat import import_transaction

            artifact_root = Path(
                self.task.result.get("submission", {}).get("directory", self.folder)
            ).resolve()
            run_root = (self.parent or self).folder.resolve()
            if artifact_root != run_root and run_root not in artifact_root.parents:
                raise ValueError("Artifact submission is outside this workflow")
            with import_transaction(self.scene):
                for item in artifacts:
                    path = Path(item["path"]).resolve()
                    if artifact_root not in path.parents:
                        raise ValueError(
                            "Worker returned an artifact outside its recorded submission directory"
                        )
                    verify_evidence(item, root=artifact_root)
                    import_artifact(item, self.collection)
                from .quality import evaluate

                report = evaluate(
                    self.objects(),
                    dict(
                        self.task.contract,
                        require_geometry=self.task.capability in {"model3d", "world"},
                    ),
                )
                if not report["passed"]:
                    raise ValueError(
                        "Imported asset failed native quality: " + "; ".join(report["errors"])
                    )
            if self.task.expert == "transcriber":
                self.props.prompt = result.get("content", "")[:2048]
            self.complete_task(
                {"artifacts": artifacts, "content": result.get("content", ""), "quality": report}
            )

    def accept_code(self):
        if self._review_child:
            child = self._review_child
            self._review_child, self.pending_code = None, None
            child.accept_code()
            return
        if self.scene != bpy.context.scene or self.pending_code is None:
            raise ValueError("No generated code is awaiting review in this scene")
        code = self.props.last_code
        self.pending_code = None
        self.execute_code(code)

    def execute_code(self, code):
        self.last_code = code
        self.status(f"Applying {self.task.id}…")
        from .revision import fingerprint, scene_revision

        if (
            fingerprint(self.objects()) != self.baseline
            or scene_revision(self.scene) != self.scene_baseline
        ):
            self.abort(
                "Human edit conflict: scene inputs changed while the model was generating code"
            )
            return
        from .staging import SceneJob

        try:
            self.scene_job = SceneJob(
                code,
                self.objects(),
                self.folder,
                contract=self.task.contract,
                regions=self.input_snapshot["region"],
                contract_checks=self.inherited_contracts(),
            )
        except ValueError as exc:
            self.repair(code, str(exc))

    def export_checked(self):
        report = self.quality_report()
        if not report["passed"]:
            raise ValueError(
                "Export blocked by native quality gate: " + "; ".join(report["errors"])
            )
        if self.props.require_visual_review and self.visual_approval != report["delivery_revision"]:
            self.pending_quality = report
            self.status(
                "Native checks passed. Inspect the current model, then Approve Visual Quality to export."
            )
            self.journal()
            return
        path = export_objects(self.folder / "asset.glb", self.objects())
        from ..core.gltf import inspect_glb
        from .compat import export_native_scene

        report["export"] = inspect_glb(path)
        native = export_native_scene(self.folder / "asset.blend", self.objects())
        self.complete_task(
            {
                "artifacts": [{"kind": "model3d", "path": path}, {"kind": "blend", "path": native}],
                "format_notes": "GLB is an interchange approximation. The native scene retains procedural shaders, world and animation. External textures/caches remain file references unless already packed.",
                "quality": report,
                "visual_review": "human approved"
                if self.visual_approval
                else "not required by user policy",
            }
        )

    def quality_report(self):
        from .quality import evaluate
        from .revision import delivery_revision

        report = evaluate(self.objects(), self.task.contract)
        root = self.parent or self
        original = root.workflow.get(self.task.id)
        report["inherited_contracts"] = []
        for dependency in root.workflow.ancestors(original):
            if not dependency.contract or dependency.expert not in CODE_EXPERTS | {
                "world",
                "model3d",
            }:
                continue
            ids = set(dependency.result.get("asset_ids", []))
            targets = [o for o in self.objects() if o.get("ama_asset_id") in ids]
            if ids and len(targets) != len(ids):
                report["errors"].append("Missing assets from dependency " + dependency.id)
            item = evaluate(targets, dependency.contract)
            report["inherited_contracts"].append({"task": dependency.id, "report": item})
            report["errors"].extend(dependency.id + ": " + error for error in item["errors"])
        report["passed"] = not report["errors"]
        report["delivery_revision"] = delivery_revision(self.objects(), self.scene)
        return report

    def inherited_contracts(self):
        root = self.parent or self
        original = root.workflow.get(self.task.id)
        return [
            {"task": t.id, "asset_ids": t.result.get("asset_ids", []), "contract": t.contract}
            for t in root.workflow.ancestors(original)
            if t.contract and t.expert in CODE_EXPERTS | {"world", "model3d"}
        ]

    def approve_quality(self):
        if self._quality_child:
            self._quality_child.approve_quality()
            self._quality_child, self.pending_quality = None, None
            return
        from .revision import delivery_revision

        if self.pending_quality is None:
            raise ValueError("No visual quality gate awaits approval")
        if (
            delivery_revision(self.objects(), self.scene)
            != self.pending_quality["delivery_revision"]
        ):
            self.pending_quality = None
            self.export_checked()
            raise ValueError(
                "Model or scene settings changed since inspection; review the refreshed report before approving"
            )
        self.visual_approval = self.pending_quality["delivery_revision"]
        self.pending_quality = None
        self.export_checked()

    def repair(self, code, error):
        count = self.repairs.get(self.task.id, 0)
        if not self.props.auto_fix or count >= self.props.max_repairs:
            self.abort(error)
            return
        self.repairs[self.task.id] = count + 1
        config = provider_for(
            "chat", "modeler" if self.repairing_validation else self.task.expert, self.scene
        )
        prompt = (
            self.task_prompt()
            + "\nThe last code failed. Correct it without duplicating objects.\n"
            + code[:100000]
            + "\nError:\n"
            + error[:6000]
        )
        self.status(f"Repairing {self.task.id} · {count + 1}/{self.props.max_repairs}")
        self.submit_chat(
            config,
            [{"role": "user", "content": prompt}],
            "Return only a complete corrected Blender Python code block. Avoid file APIs and scene deletion.",
        )

    def complete_task(self, result):
        self.repairing_validation = False
        completed_id = self.task.id
        from .revision import ensure_ids

        ensure_ids(self.objects())
        result["asset_ids"] = [o["ama_asset_id"] for o in self.objects()]
        result["objects"] = [o.name for o in self.objects()]
        for artifact in result.get("artifacts", []):
            artifact.update(file_evidence(artifact["path"], root=(self.parent or self).folder))
        previews = list(
            dict.fromkeys(
                result.get("previews", []) + ([result["preview"]] if result.get("preview") else [])
            )
        )
        result["evidence_files"] = [
            file_evidence(path, root=(self.parent or self).folder) for path in previews
        ]
        self.record_episode("succeeded", result)
        self.workflow.succeed(self.task, result)
        self.task = None
        self.journal()
        try:
            from . import conversation

            with conversation.store() as db:
                project_id = self.project_id
                db.event(
                    project_id,
                    "task_completed",
                    {
                        "run": str(self.folder),
                        "task": completed_id,
                        "quality": result.get("quality"),
                        "artifacts": result.get("artifacts", []),
                    },
                )
                if result.get("quality", {}).get("passed") and result["quality"].get("fingerprint"):
                    db.observe(
                        project_id,
                        "observed:" + self.folder.name + ":" + completed_id,
                        f"Historical checkpoint for {self.workflow.goal[:180]} / {completed_id}: "
                        f"{len(result['quality'].get('meshes', []))} meshes passed native structural checks. Re-read the current scene; this is not an aesthetic judgement.",
                        {
                            "run": str(self.folder),
                            "task": completed_id,
                            "fingerprint": result["quality"]["fingerprint"],
                        },
                    )
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.status("Task completed; memory recording unavailable: " + str(exc)[:200])

    def abort(self, message):
        self.staged_result = None
        for child in self.lanes.values():
            child.cancel(message)
        self.lanes.clear()
        if self.scene_job:
            self.scene_job.cancel()
            self.scene_job = None
        if self.job:
            self.job.cancel()
            self.job = None
        if self.workflow and self.task:
            self.record_episode("failed", {"error": str(message)[:3000]})
            self.workflow.fail(self.task, message)
            self.task = None
        self.pending_code = None
        self.pending_quality = None
        self.running = bool(not self.parent and self.workflow and self.workflow.ready())
        self.status("Stopped: " + str(message)[:700])
        try:
            self.journal()
        except OSError:
            self.status("Stopped: " + str(message)[:500] + " · Could not write the run report")

    def record_episode(self, outcome, result):
        if self.task is None:
            return
        try:
            from . import conversation

            evidence = {
                k: result[k] for k in ("error", "asset_ids", "artifacts", "preview") if k in result
            }
            if result.get("quality"):
                evidence["quality"] = {
                    k: result["quality"].get(k) for k in ("passed", "errors", "fingerprint")
                }
            with conversation.store() as db:
                db.record_episode(
                    self.project_id,
                    (self.parent or self).folder.name,
                    self.task.id,
                    self.workflow.goal,
                    outcome,
                    evidence,
                    attempts=self.task.attempts,
                )
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.status("Execution episode could not be saved: " + str(exc)[:160])

    def cancel(
        self, message="Cancelled locally; submitted remote jobs may continue at the provider"
    ):
        self.staged_result = None
        for child in self.lanes.values():
            child.cancel(message)
        self.lanes.clear()
        if self.scene_job:
            self.scene_job.cancel()
            self.scene_job = None
        if self.job:
            self.job.cancel()
            self.job = None
        if self.workflow:
            self.workflow.cancel()
        self.pending_code = None
        self.pending_quality = None
        self.running = False
        try:
            self.status(message)
            self.journal()
        except ReferenceError:
            pass

    def tick_lanes(self):
        """Independent part branches in parallel, shared writes and commits serialized."""
        for ident, child in list(self.lanes.items()):
            try:
                child.tick()
            except Exception as exc:
                child.abort(str(exc))
            if not child.running:
                task = self.workflow.get(ident)
                if child.workflow.complete:
                    result = dict(child.workflow.tasks[0].result)
                    result["objects"] = [o.name for o in child.objects()]
                    result["task_report"] = str(child.folder / "run.json")
                    if task.status != "succeeded":
                        self.workflow.succeed(task, result)
                    else:
                        task.result = result
                else:
                    self.workflow.fail(task, child.workflow.tasks[0].error or "Subtask stopped")
                self.repairs.update(child.repairs)
                del self.lanes[ident]
                self.journal()
        done = {t.id for t in self.workflow.tasks if t.status == "succeeded"}
        ready = [
            t for t in self.workflow.tasks if t.status == "queued" and set(t.depends_on) <= done
        ]
        active_parts = {
            self.workflow.get(ident).contract.get("part_id")
            if not self.workflow.get(ident).depends_on
            else None
            for ident in self.lanes
        }
        for task in ready:
            if len(self.lanes) >= self.props.max_parallel:
                break
            part = task.contract.get("part_id") if not task.depends_on else None
            if self.lanes and (None in active_parts or part is None or part in active_parts):
                continue
            # Root parts have no input geometry and therefore cannot overwrite another part.
            targets = [] if part else self.objects()
            child_workflow = Workflow.from_plan(
                self.workflow.goal,
                {
                    "assembly": self.workflow.assembly,
                    "tasks": [
                        {
                            "id": task.id,
                            "expert": task.expert,
                            "prompt": task.prompt,
                            "contract": task.contract,
                        }
                    ],
                },
            )
            child_workflow.tasks[0].attempts = task.attempts
            child_workflow.tasks[0].result = dict(task.result)
            child = StudioRun(
                self.scene,
                child_workflow,
                targets=targets,
                preview=self.preview,
                job_factory=self.job_factory,
                parent=self,
                input_results={d: self.workflow.get(d).result for d in task.depends_on},
            )
            child.repairs = {task.id: self.repairs.get(task.id, 0)}
            try:
                child.start()
            except Exception as exc:
                self.workflow.fail(task, str(exc))
                continue
            # Move child collection under the root collection without changing object transforms.
            self.collection.children.link(child.collection)
            self.scene.collection.children.unlink(child.collection)
            task.status, task.attempts = "running", task.attempts + 1
            self.lanes[task.id] = child
            active_parts.add(part)
        self.peak_parallel = max(self.peak_parallel, len(self.lanes))
        review = next((c for c in self.lanes.values() if c.pending_code is not None), None)
        if review and self._review_child is not review and current(self.scene) is self:
            self.props.last_code = review.pending_code
            text = bpy.data.texts.get("AI Studio Code") or bpy.data.texts.new("AI Studio Code")
            text.clear()
            text.write(review.pending_code)
        self._review_child = review
        self.pending_code = review.pending_code if review else None
        quality = next((c for c in self.lanes.values() if c.pending_quality is not None), None)
        self._quality_child = quality
        self.pending_quality = quality.pending_quality if quality else None
        self.journal()
        if not self.lanes:
            self.running = False
            self.status(
                "All expert tasks completed and checked"
                if self.workflow.complete
                else "Some expert tasks failed; inspect reports and retry unfinished tasks"
            )
            return False
        return True


def start_plan(scene):
    if sum(r.running for r in _active.values()) >= 2:
        raise ValueError("Two workflows are already active; finish or cancel one")
    run = StudioRun(scene)
    run.plan(scene.ama_props.workflow_goal)
    return run


def run_plan(scene):
    if sum(r.running for r in _active.values()) >= 2:
        raise ValueError("Two workflows are already active; finish or cancel one")
    workflow = Workflow.from_plan(
        scene.ama_props.workflow_goal, json.loads(scene.ama_props.plan_json)
    )
    regions = json.loads(scene.ama_props.region_json or "[]")
    targets = [
        o for o in scene.objects if o.get("ama_asset_id") in {r["asset_id"] for r in regions}
    ]
    if regions and len(targets) != len(regions):
        raise ValueError("Captured edit targets are missing; recapture the region")
    if regions and any(t.contract.get("part_id") for t in workflow.tasks):
        raise ValueError(
            "Precise edits operate on the captured assets; remove independent part tasks from this plan"
        )
    run = StudioRun(scene, workflow, targets=targets)
    run.start()
    return run


def start_single(scene, prompt, *, refine=False):
    if sum(r.running for r in _active.values()) >= 2:
        raise ValueError("Two workflows are already active; finish or cancel one")
    if not prompt.strip():
        raise ValueError("Enter a modeling prompt")
    targets = list(bpy.context.selected_objects) if refine else []
    if refine and not targets:
        raise ValueError("Select objects to refine")
    workflow = Workflow.from_plan(
        prompt,
        {"tasks": [{"id": "refine" if refine else "model", "expert": "modeler", "prompt": prompt}]},
    )
    run = StudioRun(scene, workflow, targets=targets, preview=True)
    run.start()
    return run


def start_multi_pass(scene):
    if sum(r.running for r in _active.values()) >= 2:
        raise ValueError("Two workflows are already active; finish or cancel one")
    if not scene.ama_props.prompt.strip():
        raise ValueError("Enter a modeling prompt")
    workflow = Workflow.from_plan(
        scene.ama_props.prompt,
        {
            "tasks": [
                {
                    "id": "shape",
                    "expert": "modeler",
                    "prompt": "Build the main geometry with correct proportions.",
                },
                {
                    "id": "detail",
                    "expert": "modeler",
                    "prompt": "Refine the existing geometry and add details.",
                    "depends_on": ["shape"],
                },
                {
                    "id": "materials",
                    "expert": "material",
                    "prompt": "Assign appropriate PBR materials and UVs.",
                    "depends_on": ["detail"],
                },
                {
                    "id": "inspect",
                    "expert": "inspector",
                    "prompt": "Inspect the final model.",
                    "depends_on": ["materials"],
                },
            ]
        },
    )
    run = StudioRun(scene, workflow)
    run.start()
    return run


def resume_checkpoint(scene, report_path):
    """Explicit recovery from a matching saved scene; never silently resubmits jobs."""
    from .revision import fingerprint, delivery_revision

    path = Path(bpy.path.abspath(report_path)).resolve()
    if not path.is_file() or path.stat().st_size > 16_000_000:
        raise ValueError("Choose a valid run.json checkpoint")
    data = json.loads(path.read_text(encoding="utf-8"))
    checkpoint = data.get("checkpoint", {})
    names = checkpoint.get("objects", [])
    if not isinstance(names, list) or any(n not in scene.objects for n in names):
        raise ValueError("Open the saved .blend containing all checkpoint objects before recovery")
    if fingerprint([scene.objects[n] for n in names]) != checkpoint.get("fingerprint"):
        raise ValueError(
            "Saved scene differs from the checkpoint; recovery would risk duplicating or overwriting edits"
        )
    if checkpoint.get("delivery_revision") != delivery_revision(
        [scene.objects[n] for n in names], scene
    ):
        raise ValueError(
            "Checkpoint scene settings differ or require a new version audit; revalidate before recovery"
        )
    workflow = Workflow.from_plan(data["goal"], data)
    collection = bpy.data.collections.get(data.get("collection", ""))
    if not collection:
        raise ValueError("Checkpoint collection is missing")
    actual = set(collection.all_objects) | {
        scene.objects[n] for n in checkpoint.get("targets", []) if n in scene.objects
    }
    if {o.name for o in actual} != set(names):
        raise ValueError("Checkpoint collection membership changed; revalidate before recovery")
    for task, previous in zip(workflow.tasks, data["tasks"]):
        task.result = previous.get("result", {})
        task.attempts = previous.get("attempts", 0)
        if previous.get("status") == "succeeded":
            for artifact in previous.get("result", {}).get("artifacts", []) + previous.get(
                "result", {}
            ).get("evidence_files", []):
                verify_evidence(artifact, root=path.parent)
            task.status, task.result, task.attempts = (
                "succeeded",
                previous.get("result", {}),
                previous.get("attempts", 1),
            )
    run = StudioRun(
        scene,
        workflow,
        targets=[scene.objects[n] for n in checkpoint.get("targets", [])],
        resume_folder=path.parent,
    )
    run.collection_name = collection.name
    run.calls = int(data.get("calls", 0))
    run.dispatches = data.get("dispatches", [])
    dispatch_path = path.parent / "dispatches.json"
    if dispatch_path.is_file():
        dispatched = json.loads(dispatch_path.read_text(encoding="utf-8"))
        run.calls = max(run.calls, int(dispatched.get("calls", 0)))
        run.dispatches = dispatched.get("requests", run.dispatches)
    run.repairs = data.get("repairs", {})
    if data.get("project_id") != run.project_id:
        raise ValueError("Checkpoint belongs to a different memory project")
    run.thread_id = data.get("thread_id", run.thread_id)
    run.input_snapshot = data.get("input_snapshot", run.input_snapshot)
    run.start()
    return run


def start_reviewed_code(scene, code, targets):
    """Explicit manual code review uses the same isolated execution and quality path."""
    if bpy.context.mode != "OBJECT":
        raise ValueError("Switch to Object Mode before applying reviewed code")
    workflow = Workflow.from_plan(
        "Apply reviewed Blender code",
        {
            "tasks": [
                {
                    "id": "reviewed_code",
                    "expert": "modeler",
                    "prompt": "Apply the explicitly reviewed script to selected objects",
                }
            ]
        },
    )
    run = StudioRun(scene, workflow, targets=targets)
    collection = bpy.data.collections.new("AI Studio " + run.folder.name)
    scene.collection.children.link(collection)
    run.collection_name = collection.name
    from .revision import ensure_ids, fingerprint, scene_revision

    ensure_ids(run.objects())
    run.baseline = fingerprint(run.objects())
    run.scene_baseline = scene_revision(scene)
    run.task = workflow.tasks[0]
    workflow.start(run.task)
    activate(run)
    run.execute_code(code)
    return run
