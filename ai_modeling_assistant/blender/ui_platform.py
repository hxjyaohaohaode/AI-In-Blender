"""Persistent dialogue, auditable memory and human input controls."""

import json
import bpy
from bpy.props import StringProperty, IntProperty, EnumProperty
from . import conversation, inputs
from .ai_operators import invoke_action
from .ui_studio import labels


def text_view(context, name, content):
    text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    text.clear()
    text.write(content)
    if context.area:
        context.area.type = "TEXT_EDITOR"
        context.area.spaces.active.text = text


class AMA_OT_ChatSend(bpy.types.Operator):
    bl_idname = "ama.chat_send"
    bl_label = "Send / 发送"

    def execute(self, context):
        return invoke_action(self, lambda: conversation.send(context.scene))


class AMA_OT_ChatCancel(bpy.types.Operator):
    bl_idname = "ama.chat_cancel"
    bl_label = "Cancel Reply"

    def execute(self, context):
        conversation.cancel(context.scene)
        return {"FINISHED"}


class AMA_OT_ChatThread(bpy.types.Operator):
    bl_idname = "ama.chat_thread"
    bl_label = "New Conversation / 新对话"
    thread_id: StringProperty()

    def execute(self, context):
        def apply():
            if conversation.busy(context.scene):
                raise ValueError("Cancel the current reply before switching conversations")
            with conversation.store() as db:
                project_id, _ = conversation.identity(context.scene, db)
                if self.thread_id:
                    db.thread(self.thread_id, project_id)
                    context.scene.ama_props.thread_id = self.thread_id
                else:
                    context.scene.ama_props.thread_id = db.new_thread(project_id)
            conversation.refresh(context.scene)

        return invoke_action(self, apply)


class AMA_OT_ProjectFork(bpy.types.Operator):
    bl_idname = "ama.project_fork"
    bl_label = "Fork Memory Project / 独立项目记忆"

    def execute(self, context):
        def apply():
            if conversation.busy(context.scene):
                raise ValueError("Finish the current conversation first")
            import uuid

            context.scene.ama_props.project_id = uuid.uuid4().hex
            context.scene.ama_props.thread_id = ""
            conversation.refresh(context.scene)

        return invoke_action(self, apply)


class AMA_OT_MemoryProjects(bpy.types.Operator):
    bl_idname = "ama.memory_projects"
    bl_label = "Local Projects / 本地记忆项目"
    project_id: StringProperty()

    def execute(self, context):
        def apply():
            from . import runtime

            if self.project_id:
                if conversation.busy(context.scene) or runtime.busy():
                    raise ValueError("Finish active tasks before switching the memory project")
                with conversation.store() as db:
                    if self.project_id not in {p["id"] for p in db.projects()}:
                        raise ValueError("Project does not belong to the local user profile")
                    threads = db.threads(self.project_id)
                    context.scene.ama_props.project_id = self.project_id
                    context.scene.ama_props.thread_id = threads[0]["id"] if threads else ""
            conversation.refresh(context.scene)

        return invoke_action(self, apply)


class AMA_OT_ChatHistory(bpy.types.Operator):
    bl_idname = "ama.chat_history"
    bl_label = "Full Conversation / 完整对话"

    def execute(self, context):
        def apply():
            with conversation.store() as db:
                _, thread_id = conversation.identity(context.scene, db)
                text_view(
                    context,
                    "AI Conversation",
                    "\n\n".join(
                        f"[{t['id']}] {t['role']}\n{t['content']}" for t in db.turns(thread_id)
                    ),
                )

        return invoke_action(self, apply)


class AMA_OT_PlanConversation(bpy.types.Operator):
    bl_idname = "ama.plan_conversation"
    bl_label = "Plan from Conversation / 按对话规划"

    def execute(self, context):
        def apply():
            if conversation.busy(context.scene):
                raise ValueError("Wait for the current reply and memory maintenance")
            with conversation.store() as db:
                _, thread = conversation.identity(context.scene, db)
                turns = [t for t in db.turns(thread) if t["role"] == "user"]
                if not turns:
                    raise ValueError("Start a conversation first")
                context.scene.ama_props.workflow_goal = turns[-1]["content"][:16000]
            from .runtime import start_plan

            start_plan(context.scene)

        return invoke_action(self, apply)


class AMA_OT_MemoryInspect(bpy.types.Operator):
    bl_idname = "ama.memory_inspect"
    bl_label = "Inspect Memory / 记忆审阅"

    def execute(self, context):
        def apply():
            with conversation.store() as db:
                project_id, thread_id = conversation.identity(context.scene, db)
                content = {
                    "project": project_id,
                    "thread": thread_id,
                    "database": str(conversation.database_path()),
                    "memories": [
                        dict(m, versions=db.versions(m["id"]))
                        for m in db.visible(project_id, thread_id)
                    ],
                    "execution_episodes": db.recall_episodes(project_id, "", limit=24),
                    "resolved_context_memories": db.resolved(
                        project_id, thread_id, include_user=context.scene.ama_props.personal_memory
                    ),
                    "summary": db.summary(thread_id),
                }
                text_view(
                    context, "AI Memory Audit", json.dumps(content, ensure_ascii=False, indent=2)
                )

        return invoke_action(self, apply)


class AMA_OT_MemoryReview(bpy.types.Operator):
    bl_idname = "ama.memory_review"
    bl_label = "Review Memory / 修订记忆"
    memory_id: StringProperty()
    revision: IntProperty()
    value: StringProperty(name="Memory text")
    action: EnumProperty(
        name="Decision",
        items=[
            ("verify", "Confirm / 确认", "Use this version, supersede conflicting versions"),
            ("reject", "Reject / 拒绝", "Keep audit history but do not retrieve"),
            ("restore", "Restore as candidate", "Review again"),
            ("forget", "Forget / 删除记忆", "Erase this memory and all its revisions"),
        ],
    )

    def invoke(self, context, event):
        with conversation.store() as db:
            item = db.get(self.memory_id)
            self.revision, self.value = item["revision"], item["value"]
        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        self.layout.prop(self, "value")
        self.layout.prop(self, "action")
        labels(
            self.layout,
            "Confirming resolves other memories with the same key. Forget removes the memory's versions; source conversation and filesystem backups remain separate.",
        )

    def execute(self, context):
        def apply():
            with conversation.store() as db:
                project_id, thread_id = conversation.identity(context.scene, db)
                if self.memory_id not in {m["id"] for m in db.visible(project_id, thread_id)}:
                    raise ValueError("Memory is outside this project's visible scopes")
                if self.action == "forget":
                    db.forget(self.memory_id, self.revision)
                else:
                    db.review(self.memory_id, self.revision, action=self.action, value=self.value)
            conversation.refresh(context.scene)

        return invoke_action(self, apply)


class AMA_OT_MemoryPin(bpy.types.Operator):
    bl_idname = "ama.memory_pin"
    bl_label = "Remember Latest Instruction / 记住最近指令"
    scope: EnumProperty(
        items=[
            ("project", "Project", "Only this project"),
            ("user", "Personal", "Across local projects"),
            ("session", "Session", "Expires in one day"),
        ]
    )

    def execute(self, context):
        def apply():
            with conversation.store() as db:
                project_id, thread_id = conversation.identity(context.scene, db)
                turns = [t for t in db.turns(thread_id) if t["role"] == "user"]
                if not turns:
                    raise ValueError("Send an instruction first")
                turn = turns[-1]
                value = turn["content"][:4000]
                item = db.propose(
                    project_id,
                    thread_id,
                    scope=self.scope,
                    kind="constraint",
                    key="pinned-" + str(turn["id"]),
                    value=value,
                    sources=[{"turn_id": turn["id"], "quote": value}],
                    importance=1,
                )
                db.review(item["id"], item["revision"], action="verify")
            conversation.refresh(context.scene)

        return invoke_action(self, apply)


class AMA_OT_MemoryBackup(bpy.types.Operator):
    bl_idname = "ama.memory_backup"
    bl_label = "Backup Local Memory / 备份本机记忆"

    def execute(self, context):
        def apply():
            import time

            path = conversation.database_path().with_name(
                "memory-backup-" + time.strftime("%Y%m%d-%H%M%S") + ".sqlite3"
            )
            if path.exists():
                raise ValueError("A backup with this timestamp already exists")
            with conversation.store() as db:
                db.backup(path)
            self.report({"INFO"}, "Memory backup: " + str(path))

        return invoke_action(self, apply)


class AMA_OT_MemoryForgetProject(bpy.types.Operator):
    bl_idname = "ama.memory_forget_project"
    bl_label = "Erase Project Conversations & Memory / 删除项目记忆与对话"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        def apply():
            from . import runtime

            if runtime.busy() or conversation.busy(context.scene):
                raise ValueError("Stop active tasks before erasing their project memory")
            with conversation.store() as db:
                project_id, _ = conversation.identity(context.scene, db)
                db.forget_project(project_id)
            for scene in bpy.data.scenes:
                if scene.ama_props.project_id == project_id:
                    scene.ama_props.project_id = scene.ama_props.thread_id = ""
                    scene.ama_props.chat_preview = scene.ama_props.memory_status = ""
                    conversation._ui_cache.pop(scene.as_pointer(), None)
            conversation.refresh(context.scene)

        return invoke_action(self, apply)


class AMA_OT_Attachment(bpy.types.Operator):
    bl_idname = "ama.attachment"
    bl_label = "Attach Input / 添加参考"
    clear: StringProperty(default="")

    def execute(self, context):
        def apply():
            if self.clear:
                context.scene.ama_props.attachments_json = "[]"
                context.scene.ama_props.region_json = ""
            else:
                inputs.add(context.scene, context.scene.ama_props.attachment_path)

        return invoke_action(self, apply)


class AMA_OT_Sketch(bpy.types.Operator):
    bl_idname = "ama.sketch"
    bl_label = "Draw Sketch / 绘制草图"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return invoke_action(self, inputs.new_sketch)


class AMA_OT_CaptureView(bpy.types.Operator):
    bl_idname = "ama.capture_view"
    bl_label = "Use Viewport / 采用视口参考"

    def execute(self, context):
        return invoke_action(self, lambda: inputs.capture_view(context))


class AMA_OT_EditRegion(bpy.types.Operator):
    bl_idname = "ama.edit_region"
    bl_label = "Capture Edit Region / 锚定精修区域"

    def execute(self, context):
        return invoke_action(self, lambda: inputs.capture_region(context))


class AMA_OT_ProactiveCheck(bpy.types.Operator):
    bl_idname = "ama.proactive_check"
    bl_label = "Check Next Actions / 主动建议"

    def execute(self, context):
        def apply():
            from .quality import evaluate

            report = evaluate(list(context.selected_objects), {})
            conversation.refresh(context.scene)
            suggestions = [
                "Review unconfirmed/conflicting memories: " + context.scene.ama_props.memory_status
            ]
            suggestions.extend(report["warnings"] + report["errors"])
            text_view(
                context,
                "AI Suggested Actions",
                "Read-only local suggestions; no model call or scene edit.\n\n"
                + "\n".join(suggestions),
            )

        return invoke_action(self, apply)


class AMA_PT_Conversation(bpy.types.Panel):
    bl_label = "Conversation & Memory / 对话与记忆"
    bl_idname = "AMA_PT_conversation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Model"

    def draw(self, context):
        layout, props = self.layout, context.scene.ama_props
        labels(
            layout.box(),
            props.chat_preview
            or "Your conversation is saved locally and survives Blender restarts.",
            52,
        )
        layout.prop(props, "chat_input", text="Message")
        row = layout.row(align=True)
        row.operator("ama.chat_send")
        row.operator("ama.chat_cancel" if conversation.busy(context.scene) else "ama.chat_thread")
        layout.operator("ama.chat_history")
        layout.operator("ama.plan_conversation")
        labels(layout, props.chat_status)
        row = layout.row(align=True)
        row.operator("ama.memory_inspect")
        row.operator("ama.memory_pin").scope = "project"
        labels(layout, props.memory_status)
        for name in (
            "semantic_compression",
            "memory_enabled",
            "memory_retrieval",
            "personal_memory",
            "context_budget",
        ):
            layout.prop(props, name)
        if props.project_id and props.thread_id:
            cached = conversation._ui_cache.get(context.scene.as_pointer(), {})
            layout.prop(props, "memory_page")
            for item in sorted(
                cached.get("memories", []),
                key=lambda m: m["status"] not in {"candidate", "conflict"},
            )[props.memory_page * 8 : props.memory_page * 8 + 8]:
                op = layout.operator(
                    "ama.memory_review", text=f"{item['status']} · {item['key'][:24]}"
                )
                op.memory_id = item["id"]
            layout.prop(props, "thread_page")
            for thread in cached.get("threads", [])[
                props.thread_page * 5 : props.thread_page * 5 + 5
            ]:
                if thread["id"] != props.thread_id:
                    op = layout.operator(
                        "ama.chat_thread", text=thread["title"][:32] + " · " + thread["id"][:5]
                    )
                    op.thread_id = thread["id"]
            layout.prop(props, "project_page")
            for project in cached.get("projects", [])[
                props.project_page * 5 : props.project_page * 5 + 5
            ]:
                if project["id"] != props.project_id:
                    op = layout.operator(
                        "ama.memory_projects", text=project["name"][:20] + " · " + project["id"][:8]
                    )
                    op.project_id = project["id"]
        layout.operator("ama.memory_projects")
        layout.operator("ama.project_fork")
        layout.operator("ama.memory_backup")
        layout.operator("ama.memory_forget_project")
        layout.operator("ama.proactive_check")
        layout.prop(props, "proactive_enabled")
        labels(layout, props.proactive_status)


class AMA_PT_Inputs(bpy.types.Panel):
    bl_label = "References & Precise Edits / 参考与精修"
    bl_idname = "AMA_PT_inputs"
    bl_parent_id = "AMA_PT_conversation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Model"

    def draw(self, context):
        layout, props = self.layout, context.scene.ama_props
        layout.prop(props, "attachment_path")
        row = layout.row(align=True)
        row.operator("ama.attachment")
        row.operator("ama.attachment", text="Clear").clear = "all"
        for item in inputs.items(context.scene):
            layout.label(text=f"{item['kind']} · {item['name'][:32]}")
        row = layout.row(align=True)
        row.operator("ama.sketch")
        row.operator("ama.capture_view")
        layout.operator("ama.edit_region")
        labels(
            layout,
            "Draw with native Grease Pencil, then capture the viewport as an image reference. Selected mesh indices become explicit edit anchors.",
        )


CLASSES = [
    value
    for value in list(globals().values())
    if isinstance(value, type)
    and value.__module__ == __name__
    and issubclass(value, (bpy.types.Operator, bpy.types.Panel))
]
