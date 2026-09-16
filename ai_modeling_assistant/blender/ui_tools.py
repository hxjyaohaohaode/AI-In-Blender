"""blender / ui_tools — extracted from the original add-on."""

from ..blender.localization import get_prefs
from ..blender.localization import t
from ..blender.state import _asset_registry
from ..blender.state import _version_snapshots
from ..blender.state import get_conversation
from ..data.catalog import ENGINE_EXPORT_PRESETS
from ..data.catalog import LOD_LEVELS
from ..data.catalog import MATERIAL_PRESETS
from ..data.catalog import MODIFIER_PRESETS
from ..data.catalog import QUICK_BUILDS
from ..data.catalog import TEMPLATES
from .localization import _current_lang
from bpy.types import Panel
from typing import Dict
from typing import List
import json




class AMA_PT_QuickBuildPanel(Panel):
    """Quick build panel - instant 3D creation without API"""
    bl_label = "Quick Build (No API)"
    bl_idname = "AMA_PT_quick_build"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"

    def draw(self, context):
        layout = self.layout
        grid = layout.grid_flow(columns=3, align=True)
        for key, preset in QUICK_BUILDS.items():
            lang = _current_lang()
            label = preset.get(f"label_{lang}", preset["label_en"])
            op = grid.operator("ama.quick_build", text=label, icon='MESH_DATA')
            op.preset_key = key






class AMA_PT_HistoryPanel(Panel):
    """Conversation history panel"""
    bl_label = "Conversation History"
    bl_idname = "AMA_PT_history"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        conv = get_conversation()
        stats = conv.get_stats()

        layout.label(text=f"Messages: {stats['count']} | Est. tokens: {stats['estimated_tokens']}")
        layout.operator("ama.clear_history", text=t("clear_history"), icon='TRASH')

        # Show last few messages
        messages = conv.get_messages()
        for msg in messages[-6:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:80]
            icon = 'USER' if role == 'user' else 'OUTLINER_OB_ARMATURE' if role == 'assistant' else 'SETTINGS'
            box = layout.box()
            box.label(text=f"[{role}]", icon=icon)
            box.label(text=content)


class AMA_PT_MaterialsPanel(Panel):
    """Material library panel"""
    bl_label = "Material Library"
    bl_idname = "AMA_PT_materials"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Group materials by category
        categories: Dict[str, List[str]] = {}
        for name in MATERIAL_PRESETS:
            cat = name.split("_")[0] if "_" in name else "Other"
            categories.setdefault(cat, []).append(name)

        for cat, names in sorted(categories.items()):
            box = layout.box()
            box.label(text=cat, icon='MATERIAL')
            for name in names:
                op = box.operator("ama.apply_material", text=name.replace("_", " "), icon='DOT')
                op.material_name = name


class AMA_PT_ModifiersPanel(Panel):
    """Modifier presets panel"""
    bl_label = "Modifier Presets"
    bl_idname = "AMA_PT_modifiers"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        for name in MODIFIER_PRESETS:
            op = layout.operator("ama.apply_modifier", text=name, icon='MODIFIER')
            op.modifier_name = name


class AMA_PT_MeshEditPanel(Panel):
    """Mesh editing tools panel"""
    bl_label = "Mesh Editing"
    bl_idname = "AMA_PT_mesh_edit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Mesh operations
        col = layout.column(align=True)
        col.label(text="Edit Operations:", icon='EDITMODE_HLT')
        col.operator("ama.extrude_selected", icon='MOD_SOLIDIFY')
        col.operator("ama.bevel_selected", icon='MOD_BEVEL')
        col.operator("ama.inset_selected", icon='FACESEL')
        col.operator("ama.loop_cut", icon='MESH_DATA')
        col.operator("ama.subdivide_mesh", icon='MOD_SUBSURF')
        col.operator("ama.merge_by_distance", icon='AUTOMERGE_ON')

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Shading & Normals:", icon='SHADING_RENDERED')
        col.operator("ama.recalculate_normals", icon='NORMALS_FACE')
        col.operator("ama.smooth_shading", icon='SHADING_RENDERED')
        col.operator("ama.flat_shading", icon='SHADING_SOLID')

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Utilities:", icon='TOOL_SETTINGS')
        col.operator("ama.apply_all_modifiers", icon='MODIFIER')
        col.operator("ama.duplicate_symmetry", icon='MOD_MIRROR')


class AMA_PT_TemplatesPanel(Panel):
    """Templates panel"""
    bl_label = "Templates"
    bl_idname = "AMA_PT_templates"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        layout.prop(props, "active_template")

        template = TEMPLATES.get(props.active_template)
        if template:
            # Show parameter sliders
            try:
                params = json.loads(props.template_params_json)
            except (json.JSONDecodeError, TypeError):
                params = {}

            box = layout.box()
            lang = "zh" if getattr(get_prefs(), "language", "en") == "zh" else "en"
            for key, cfg in template["params"].items():
                label = cfg.get(f"label_{lang}", cfg.get("label_en", key))
                val = params.get(key, cfg["default"])
                # Use a generic property display
                box.label(text=f"{label}: {val}")

            layout.operator("ama.apply_template", text="Generate from Template", icon='MESH_DATA')


class AMA_PT_LODPanel(Panel):
    """LOD generation panel"""
    bl_label = "LOD Generator"
    bl_idname = "AMA_PT_lod"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.generate_lod", icon='MESH_DATA')

        # Show LOD levels
        for name, ratio in LOD_LEVELS:
            layout.label(text=f"{name}: {ratio*100:.0f}%")


class AMA_PT_MeshAnalysisPanel(Panel):
    """Mesh analysis panel"""
    bl_label = "Mesh Analysis"
    bl_idname = "AMA_PT_mesh_analysis"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.analyze_mesh", icon='VIEWZOOM')
        layout.operator("ama.quality_check", icon='CHECKMARK')
        layout.operator("ama.fix_object", icon='BRUSH_DATA')


class AMA_PT_RiggingPanel(Panel):
    """Rigging tools panel"""
    bl_label = "Rigging"
    bl_idname = "AMA_PT_rigging"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        op = layout.operator("ama.create_rig", text="Humanoid Rig", icon='ARMATURE_DATA')
        op.rig_type = "humanoid"
        op = layout.operator("ama.create_rig", text="Quadruped Rig", icon='ARMATURE_DATA')
        op.rig_type = "quadruped"


class AMA_PT_UVPanel(Panel):
    """UV tools panel"""
    bl_label = "UV Tools"
    bl_idname = "AMA_PT_uv"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        for method, label in [("smart", "Smart UV"), ("angle", "Angle Based"),
                               ("cube", "Cube"), ("cylinder", "Cylinder"), ("sphere", "Sphere")]:
            op = layout.operator("ama.uv_unwrap", text=label, icon='UV')
            op.method = method


class AMA_PT_BakePanel(Panel):
    """Bake tools panel"""
    bl_label = "Bake Tools"
    bl_idname = "AMA_PT_bake"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.bake_normals", icon='IMAGE_RGB_ALPHA')


class AMA_PT_AnimationPanel(Panel):
    """Animation tools panel"""
    bl_label = "Animation"
    bl_idname = "AMA_PT_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.walk_cycle", icon='ARMATURE_DATA')
        layout.operator("ama.breathing_anim", icon='ARMATURE_DATA')
        layout.operator("ama.camera_orbit", icon='CAMERA_DATA')


class AMA_PT_ProceduralPanel(Panel):
    """Procedural generation panel"""
    bl_label = "Procedural Generation"
    bl_idname = "AMA_PT_procedural"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.generate_terrain", icon='WORLD')
        layout.operator("ama.generate_tree", icon='OUTLINER_OB_FORCE_FIELD')
        layout.operator("ama.scatter_objects", icon='PARTICLES')


class AMA_PT_BatchPanel(Panel):
    """Batch operations panel"""
    bl_label = "Batch Operations"
    bl_idname = "AMA_PT_batch"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        # Rename
        box = layout.box()
        box.label(text="Rename", icon='SORTALPHA')
        box.prop(props, "batch_prefix")
        box.prop(props, "batch_suffix")
        box.prop(props, "batch_find")
        box.prop(props, "batch_replace")

        for mode, label in [("prefix", "Add Prefix"), ("suffix", "Add Suffix"),
                             ("replace", "Find & Replace"), ("sequential", "Sequential")]:
            op = box.operator("ama.batch_rename", text=label)
            op.mode = mode

        # Export
        box = layout.box()
        box.label(text="Export", icon='EXPORT')
        box.prop(props, "export_path")
        for fmt, label in [("fbx", "FBX"), ("obj", "OBJ"), ("gltf", "glTF"), ("stl", "STL")]:
            op = box.operator("ama.batch_export", text=f"Export {label}", icon='EXPORT')
            op.format = fmt


class AMA_PT_ScenePanel(Panel):
    """Scene assembly panel"""
    bl_label = "Scene Assembly"
    bl_idname = "AMA_PT_scene"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.assembly_layout", icon='GRID')
        layout.operator("ama.assembly_align", icon='ALIGN_MIDDLE')


class AMA_PT_VersionsPanel(Panel):
    """Version control panel"""
    bl_label = "Version Control"
    bl_idname = "AMA_PT_versions"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        layout.prop(props, "version_name")
        layout.operator("ama.scene_snapshot", icon='FILE_TICK')
        layout.operator("ama.scene_versions_list", icon='LINENUMBERS_ON')

        # Show snapshot count
        scene_name = context.scene.name
        snapshots = _version_snapshots.get(scene_name, [])
        layout.label(text=f"Snapshots: {len(snapshots)}")


class AMA_PT_SelectPanel(Panel):
    """Smart selection panel"""
    bl_label = "Smart Select"
    bl_idname = "AMA_PT_select"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.select_by_material", icon='MATERIAL')
        layout.operator("ama.select_non_manifold", icon='MESH_DATA')
        layout.operator("ama.select_loose", icon='VERTEXSEL')


class AMA_PT_CleanupPanel(Panel):
    """Cleanup tools panel"""
    bl_label = "Cleanup"
    bl_idname = "AMA_PT_cleanup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("ama.cleanup_empty", icon='TRASH')


class AMA_PT_ExportPanel(Panel):
    """Engine export panel"""
    bl_label = "Engine Export"
    bl_idname = "AMA_PT_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        layout.prop(props, "export_engine")
        layout.prop(props, "export_path")

        preset = ENGINE_EXPORT_PRESETS.get(props.export_engine, {})
        if preset:
            box = layout.box()
            lang = "zh" if getattr(get_prefs(), "language", "en") == "zh" else "en"
            box.label(text=preset.get(f"notes_{lang}", preset.get("notes_en", "")))

        layout.operator("ama.engine_export", icon='EXPORT')


class AMA_PT_AssetsPanel(Panel):
    """Asset management panel"""
    bl_label = "Asset Manager"
    bl_idname = "AMA_PT_assets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        layout.prop(props, "asset_name")
        layout.prop(props, "asset_category")
        layout.operator("ama.register_asset", icon='ADD')
        layout.operator("ama.search_assets", icon='VIEWZOOM')

        # Show registered count
        layout.label(text=f"Registered: {len(_asset_registry)}")
