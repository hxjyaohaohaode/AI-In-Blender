"""blender / tools_build — extracted from the original add-on."""

from ..blender.execution import CodeExecutor
from ..blender.localization import get_prefs
from ..data.catalog import QUICK_BUILDS
from ..data.catalog import TEMPLATES
from bpy.props import StringProperty
from bpy.types import Operator
import bpy
import json


class AMA_OT_QuickBuild(Operator):
    """Instantly create a 3D object from a preset (no API needed)"""
    bl_idname = "ama.quick_build"
    bl_label = "Quick Build"
    bl_description = "Instantly create a 3D model from preset code"
    bl_options = {'REGISTER', 'UNDO'}

    preset_key: StringProperty(name="Preset")

    def execute(self, context):
        preset = QUICK_BUILDS.get(self.preset_key)
        if not preset:
            self.report({'WARNING'}, f"Unknown preset: {self.preset_key}")
            return {'CANCELLED'}
        code = preset["code"]
        props = context.scene.ama_props
        props.last_code = code
        success, output = CodeExecutor.execute(code)
        if success:
            self.report({'INFO'}, output)
        else:
            self.report({'ERROR'}, output[:200])
        return {'FINISHED'} if success else {'CANCELLED'}


class AMA_OT_ApplyTemplate(Operator):
    """Apply a parameterized template"""
    bl_idname = "ama.apply_template"
    bl_label = "Apply Template"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ama_props
        template_key = props.active_template
        template = TEMPLATES.get(template_key)
        if not template:
            self.report({'WARNING'}, "Unknown template")
            return {'CANCELLED'}

        # Parse stored params
        try:
            params = json.loads(props.template_params_json)
        except (json.JSONDecodeError, TypeError):
            params = {}

        # Fill defaults
        for key, cfg in template["params"].items():
            if key not in params:
                params[key] = cfg["default"]

        # Build prompt from template
        lang = "zh" if getattr(get_prefs(), "language", "en") == "zh" else "en"
        prompt_key = f"prompt_{lang}"
        prompt_template = template.get(prompt_key, template.get("prompt_en", ""))
        try:
            prompt = prompt_template.format(**params)
        except KeyError:
            prompt = prompt_template

        # Set as prompt and send to AI
        props.prompt = prompt
        bpy.ops.ama.send_to_ai()

        self.report({'INFO'}, f"Template '{template_key}' applied")
        return {'FINISHED'}
