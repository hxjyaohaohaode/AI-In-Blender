"""Thin UI operators for the asynchronous studio runtime."""

import bpy
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator
from . import runtime
from .state import preferences, _session_keys


def invoke_action(operator, callback):
    try:
        callback()
        return {"FINISHED"}
    except Exception as exc:
        operator.report({"ERROR"}, str(exc)[:500])
        return {"CANCELLED"}


class AMA_OT_SendToAI(Operator):
    bl_idname = "ama.send_to_ai"
    bl_label = "Generate Code"

    def execute(self, context):
        return invoke_action(
            self, lambda: runtime.start_single(context.scene, context.scene.ama_props.prompt)
        )


class AMA_OT_RefineObject(Operator):
    bl_idname = "ama.refine_object"
    bl_label = "Refine Selected"

    def execute(self, context):
        return invoke_action(
            self,
            lambda: runtime.start_single(
                context.scene, context.scene.ama_props.prompt, refine=True
            ),
        )


class AMA_OT_MultiPassGenerate(Operator):
    bl_idname = "ama.multi_pass_generate"
    bl_label = "Multi-Pass Generate"

    def execute(self, context):
        return invoke_action(self, lambda: runtime.start_multi_pass(context.scene))


class AMA_OT_ExecuteCode(Operator):
    bl_idname = "ama.execute_code"
    bl_label = "Apply Code"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        run = runtime.current(context.scene)
        if run and run.running and run.pending_code is not None:
            return invoke_action(self, run.accept_code)
        if runtime.busy():
            self.report({"WARNING"}, "Wait for the active job or cancel it")
            return {"CANCELLED"}
        if not context.scene.ama_props.last_code.strip():
            return {"CANCELLED"}
        return invoke_action(
            self,
            lambda: runtime.start_reviewed_code(
                context.scene, context.scene.ama_props.last_code, list(context.selected_objects)
            ),
        )


class AMA_OT_CodeEditExecute(Operator):
    bl_idname = "ama.code_edit_execute"
    bl_label = "Run Edited Code"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        text = bpy.data.texts.get("AI Studio Code")
        if text:
            context.scene.ama_props.last_code = text.as_string()
        return AMA_OT_ExecuteCode.execute(self, context)


class AMA_OT_CreatePlan(Operator):
    bl_idname = "ama.create_plan"
    bl_label = "Create Expert Plan / 规划"

    def execute(self, context):
        return invoke_action(self, lambda: runtime.start_plan(context.scene))


class AMA_OT_RunPlan(Operator):
    bl_idname = "ama.run_plan"
    bl_label = "Run Plan / 执行"

    def execute(self, context):
        return invoke_action(self, lambda: runtime.run_plan(context.scene))


class AMA_OT_CancelWorkflow(Operator):
    bl_idname = "ama.cancel_workflow"
    bl_label = "Cancel / 取消"

    def execute(self, context):
        run = runtime.current(context.scene)
        if run and run.running:
            run.cancel()
        return {"FINISHED"}


class AMA_OT_RetryWorkflow(Operator):
    bl_idname = "ama.retry_workflow"
    bl_label = "Retry Unfinished Tasks / 重试"

    def execute(self, context):
        def retry():
            if runtime.busy():
                raise ValueError("A workflow is already active")
            run = runtime.current(context.scene)
            if not run or not run.workflow:
                raise ValueError("No workflow to retry in this session")
            run.preflight()
            run.workflow.retry()
            run.repairs.clear()
            run.task, run.pending_code = None, None
            run.running = True
            run.status("Retrying unfinished tasks")
            runtime.activate(run)

        return invoke_action(self, retry)


class AMA_OT_OpenCode(Operator):
    bl_idname = "ama.open_code"
    bl_label = "Open in Text Editor"

    def execute(self, context):
        text = bpy.data.texts.get("AI Studio Code") or bpy.data.texts.new("AI Studio Code")
        if not text.as_string():
            text.write(context.scene.ama_props.last_code)
        if context.area:
            context.area.type = "TEXT_EDITOR"
            context.area.spaces.active.text = text
        return {"FINISHED"}


class AMA_OT_OpenPlan(Operator):
    bl_idname = "ama.open_plan"
    bl_label = "Edit Plan in Text Editor"

    def execute(self, context):
        import json

        text = bpy.data.texts.get("AI Studio Plan") or bpy.data.texts.new("AI Studio Plan")
        text.clear()
        try:
            data = json.loads(context.scene.ama_props.plan_json or '{"tasks": []}')
        except ValueError:
            data = {"tasks": []}
        text.write(json.dumps(data, ensure_ascii=False, indent=2))
        if context.area:
            context.area.type = "TEXT_EDITOR"
            context.area.spaces.active.text = text
        return {"FINISHED"}


class AMA_OT_ApplyPlan(Operator):
    bl_idname = "ama.apply_plan"
    bl_label = "Use Edited Plan"

    def execute(self, context):
        def apply():
            import json
            from ..core.agents import Workflow

            if runtime.busy():
                raise ValueError("Cancel the running workflow before editing its plan")
            text = bpy.data.texts.get("AI Studio Plan")
            if not text:
                raise ValueError("Open a plan in the Text Editor first")
            data = json.loads(text.as_string())
            goal = data.get("goal") or context.scene.ama_props.workflow_goal
            workflow = Workflow.from_plan(goal, data)
            context.scene.ama_props.plan_json = json.dumps(workflow.snapshot(), ensure_ascii=False)
            context.scene.ama_props.workflow_goal = goal
            context.scene.ama_props.workflow_status = "Edited plan validated — ready to run"

        return invoke_action(self, apply)


class AMA_OT_ProviderAdd(Operator):
    bl_idname = "ama.provider_add"
    bl_label = "Add Provider"

    def execute(self, context):
        prefs = preferences()
        if not prefs:
            return {"CANCELLED"}
        profile = prefs.providers.add()
        profile.name = f"Model {len(prefs.providers)}"
        prefs.provider_index = len(prefs.providers) - 1
        return {"FINISHED"}


class AMA_OT_ProviderRemove(Operator):
    bl_idname = "ama.provider_remove"
    bl_label = "Remove Provider"

    def execute(self, context):
        prefs = preferences()
        if not prefs or not prefs.providers:
            return {"CANCELLED"}
        index = min(prefs.provider_index, len(prefs.providers) - 1)
        _session_keys.pop(prefs.providers[index].as_pointer(), None)
        prefs.providers.remove(index)
        prefs.provider_index = min(index, max(0, len(prefs.providers) - 1))
        return {"FINISHED"}


class AMA_OT_OpenReport(Operator):
    bl_idname = "ama.open_report"
    bl_label = "Read Run Report"

    def execute(self, context):
        from pathlib import Path

        path = Path(context.scene.ama_props.workflow_report)
        if not path.is_file():
            self.report({"WARNING"}, "No run report yet")
            return {"CANCELLED"}
        text = bpy.data.texts.get("AI Studio Report") or bpy.data.texts.new("AI Studio Report")
        text.clear()
        text.write(path.read_text(encoding="utf-8"))
        if context.area:
            context.area.type = "TEXT_EDITOR"
            context.area.spaces.active.text = text
        return {"FINISHED"}


class AMA_OT_ApproveQuality(Operator):
    bl_idname = "ama.approve_quality"
    bl_label = "Approve Visual Quality / 确认视觉质量"

    def execute(self, context):
        def approve():
            run = runtime.current(context.scene)
            if not run:
                raise ValueError("No active workflow")
            run.approve_quality()

        return invoke_action(self, approve)


class AMA_OT_SelectWorkflow(Operator):
    bl_idname = "ama.select_workflow"
    bl_label = "Select Workflow"
    run_id: StringProperty()

    def execute(self, context):
        run = runtime._all_runs.get(self.run_id)
        if not run or run.scene != context.scene:
            return {"CANCELLED"}
        runtime.focus(run)
        return {"FINISHED"}


class AMA_OT_ResumeWorkflow(Operator):
    bl_idname = "ama.resume_workflow"
    bl_label = "Resume Saved Checkpoint / 恢复检查点"

    def execute(self, context):
        return invoke_action(
            self,
            lambda: runtime.resume_checkpoint(
                context.scene, context.scene.ama_props.workflow_report
            ),
        )


class AMA_OT_OpenPreview(Operator):
    bl_idname = "ama.open_preview"
    bl_label = "View Latest Preview / 查看预览"
    view: EnumProperty(
        items=[
            ("primary", "Perspective", "Geometry perspective"),
            ("back", "Reverse", "Reverse geometry view"),
            ("top", "Top", "Top geometry view"),
        ],
        default="primary",
    )

    def execute(self, context):
        def apply():
            run = runtime.current(context.scene)
            previews = (
                sorted(run.folder.rglob("preview.png"), key=lambda p: p.stat().st_mtime)
                if run
                else []
            )
            if not previews:
                raise ValueError("No rendered branch preview is available yet")
            path = (
                previews[-1]
                if self.view == "primary"
                else previews[-1].with_name("preview-" + self.view + ".png")
            )
            if not path.is_file():
                raise ValueError(
                    "This older candidate has no requested view; generate a fresh preview"
                )
            image = bpy.data.images.load(str(path), check_existing=True)
            if context.area:
                context.area.type = "IMAGE_EDITOR"
                context.area.spaces.active.image = image

        return invoke_action(self, apply)


class AMA_OT_Demo(Operator):
    bl_idname = "ama.offline_demo"
    bl_label = "Offline Studio Demo / 离线示例"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if runtime.busy():
            return {"CANCELLED"}
        from .demo import build_demo

        return invoke_action(self, lambda: build_demo(context.scene))


CLASSES = [
    AMA_OT_SendToAI,
    AMA_OT_RefineObject,
    AMA_OT_MultiPassGenerate,
    AMA_OT_ExecuteCode,
    AMA_OT_CodeEditExecute,
    AMA_OT_CreatePlan,
    AMA_OT_RunPlan,
    AMA_OT_CancelWorkflow,
    AMA_OT_RetryWorkflow,
    AMA_OT_OpenCode,
    AMA_OT_ProviderAdd,
    AMA_OT_ProviderRemove,
    AMA_OT_OpenReport,
    AMA_OT_Demo,
    AMA_OT_OpenPlan,
    AMA_OT_ApplyPlan,
    AMA_OT_ApproveQuality,
    AMA_OT_SelectWorkflow,
    AMA_OT_ResumeWorkflow,
    AMA_OT_OpenPreview,
]
