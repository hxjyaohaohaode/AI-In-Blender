"""The studio presents real task state and explicit model capabilities."""

import json
import textwrap
import unicodedata
from bpy.types import Panel, UIList
from . import runtime
from .state import preferences, available_capabilities, _cost_tracker


def labels(layout, text, width=48):
    for line in str(text).splitlines():
        wide = sum(unicodedata.east_asian_width(c) in {"W", "F"} for c in line)
        effective = max(16, int(width * len(line) / max(1, len(line) + wide)))
        for part in textwrap.wrap(line, width=effective) or [""]:
            layout.label(text=part)


class AMA_UL_Providers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "enabled", text="")
        layout.prop(item, "name", text="", emboss=False)
        layout.label(text=item.protocol)


def draw_providers(layout, prefs):
    row = layout.row()
    row.template_list("AMA_UL_Providers", "", prefs, "providers", prefs, "provider_index", rows=3)
    buttons = row.column(align=True)
    buttons.operator("ama.provider_add", text="", icon="ADD")
    buttons.operator("ama.provider_remove", text="", icon="REMOVE")
    if not prefs.providers:
        labels(
            layout,
            "Add providers to route experts to different models. Without profiles, the basic chat settings are used.",
        )
        return
    profile = prefs.providers[min(prefs.provider_index, len(prefs.providers) - 1)]
    for prop in ("name", "protocol", "base_url", "model", "api_key", "key_env"):
        layout.prop(profile, prop)
    if profile.protocol in {"bridge", "chat"}:
        layout.prop(profile, "capabilities")
    if profile.protocol == "bridge":
        labels(
            layout, "Video/world providers need an Async Jobs Bridge server. See docs/PROVIDERS.md."
        )
    else:
        layout.label(text="Capabilities: " + ", ".join(sorted(profile.capabilities)))
    layout.prop(profile, "experts")
    row = layout.row(align=True)
    row.prop(profile, "timeout")
    row.prop(profile, "max_tokens")
    layout.prop(profile, "temperature")
    layout.prop(profile, "options_json")
    layout.label(text="Keys: session memory or named environment variable", icon="LOCKED")


class AMA_PT_MainPanel(Panel):
    bl_label = "AI in Blender · Agent Platform"
    bl_idname = "AMA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Model"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props
        working = runtime.busy()
        run = runtime.current(context.scene)
        for item in runtime.list_runs(context.scene):
            op = layout.operator(
                "ama.select_workflow",
                text=("▶ " if item.running else "• ")
                + (item.workflow.goal[:28] if item.workflow else "Planning…"),
            )
            op.run_id = item.folder.name
        column = layout.column()
        column.enabled = sum(r.running for r in runtime._active.values()) < 2
        column.prop(props, "workflow_goal", text="Brief / 目标")
        row = column.row(align=True)
        row.operator("ama.create_plan", text="Plan / 规划", icon="OUTLINER")
        action = row.row(align=True)
        action.enabled = bool(props.plan_json)
        action.operator("ama.run_plan", text="Run / 执行", icon="PLAY")
        column.prop(props, "auto_run_plan")
        column.prop(props, "review_code")
        if run and run.running:
            layout.operator("ama.cancel_workflow", icon="CANCEL")
        status = layout.box()
        labels(status, props.workflow_status[:700])
        if run and run.pending_code is not None:
            row = layout.row(align=True)
            row.operator("ama.open_code", text="Review Code", icon="TEXT")
            row.operator("ama.execute_code", text="Apply Code", icon="CHECKMARK")
        if run and run.pending_quality is not None:
            labels(
                layout.box(),
                "Native checks passed. Inspect the model and available branch preview before visual approval.",
            )
            layout.operator("ama.approve_quality", icon="CHECKMARK")
        try:
            tasks = json.loads(props.plan_json).get("tasks", []) if props.plan_json else []
        except (ValueError, AttributeError):
            tasks = []
        if tasks:
            controls = layout.row(align=True)
            controls.enabled = not working
            controls.operator("ama.open_plan", text="Edit Plan", icon="TEXT")
            controls.operator("ama.apply_plan", text="Use Edited Plan", icon="CHECKMARK")
            layout.prop(props, "show_task_details")
            box = layout.box()
            done = sum(t.get("status") == "succeeded" for t in tasks)
            box.label(text=f"Expert tasks: {done}/{len(tasks)} complete")
            for task in tasks[:24]:
                state = task.get("status", "queued")
                icon = {
                    "succeeded": "CHECKMARK",
                    "failed": "ERROR",
                    "running": "TIME",
                    "cancelled": "CANCEL",
                    "blocked": "LOCKED",
                }.get(state, "DOT")
                box.label(text=f"{task['id']} · {task['expert']} · {state}", icon=icon)
                if props.show_task_details:
                    labels(box, task.get("prompt", "")[:500])
                if state == "failed":
                    labels(box, task.get("error", "")[-220:])
            if not working and any(
                t.get("status") in {"failed", "cancelled", "blocked"} for t in tasks
            ):
                layout.operator("ama.retry_workflow", icon="FILE_REFRESH")
        row = layout.row(align=True)
        row.operator("ama.open_report", icon="TEXT")
        layout.operator("ama.open_preview", icon="IMAGE_DATA")
        views = layout.row(align=True)
        views.operator("ama.open_preview", text="Reverse / 背面").view = "back"
        views.operator("ama.open_preview", text="Top / 顶面").view = "top"
        demo = row.row()
        demo.enabled = not working
        demo.operator("ama.offline_demo", text="Offline Demo", icon="MESH_ICOSPHERE")
        layout.label(text="Available: " + ", ".join(sorted(available_capabilities())))


class AMA_PT_GenerationPanel(Panel):
    bl_label = "Modeling / 精修"
    bl_idname = "AMA_PT_generation"
    bl_parent_id = "AMA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Model"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props
        column = layout.column()
        column.enabled = not runtime.busy()
        column.prop(props, "prompt", text="Prompt")
        row = column.row(align=True)
        row.operator("ama.send_to_ai")
        row.operator("ama.refine_object")
        column.operator("ama.multi_pass_generate")
        labels(layout, props.status_message[:300])


class AMA_PT_CodeEditorPanel(Panel):
    bl_label = "Code Review / 代码审阅"
    bl_idname = "AMA_PT_code_editor"
    bl_parent_id = "AMA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Model"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props
        if props.last_code:
            layout.label(text=f"{len(props.last_code.splitlines())} lines of generated Python")
            layout.operator("ama.open_code", icon="TEXT")
            layout.prop(props, "last_code", text="Code")
            row = layout.row(align=True)
            row.operator("ama.execute_code")
            row.operator("ama.code_edit_execute")
        else:
            layout.label(text="Generate code or run an offline preset first")
        labels(
            layout,
            "Generated Python uses Blender permissions. The code guard is not an OS sandbox.",
        )


class AMA_PT_APISettingsPanel(Panel):
    bl_label = "Models & Settings / 模型配置"
    bl_idname = "AMA_PT_api_settings"
    bl_parent_id = "AMA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Model"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not runtime.busy()
        props = context.scene.ama_props
        prefs = preferences()
        if prefs:
            layout.prop(prefs, "language")
            draw_providers(layout.box(), prefs)
        if not prefs or not any(profile.enabled for profile in prefs.providers):
            box = layout.box()
            box.label(text="Basic Chat Provider")
            for name in (
                "api_preset",
                "api_url",
                "model",
                "api_key",
                "key_env",
                "temperature",
                "max_tokens",
                "request_timeout",
            ):
                box.prop(props, name)
        for name in (
            "artifact_dir",
            "input_audio",
            "auto_fix",
            "max_repairs",
            "include_history",
            "max_history_tokens",
            "basic_vision",
            "max_parallel",
            "max_calls",
            "require_visual_review",
        ):
            layout.prop(props, name)
        layout.prop(props, "workflow_report", text="Saved run.json")
        layout.operator("ama.resume_workflow")
        stats = _cost_tracker.get_totals()
        layout.label(text=f"Requests: {stats['requests']} · Tokens: {stats['total_tokens']}")
        layout.label(text="Billing: consult the provider's usage dashboard")
        layout.operator("ama.reset_cost", text="Reset Usage Counters")


CLASSES = [
    AMA_UL_Providers,
    AMA_PT_MainPanel,
    AMA_PT_GenerationPanel,
    AMA_PT_CodeEditorPanel,
    AMA_PT_APISettingsPanel,
]
