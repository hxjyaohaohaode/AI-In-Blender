"""Exports preserve source meshes, modifiers, transforms and selection."""
from pathlib import Path
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from .compat import export_objects, safe_filename


class AMA_OT_BatchExport(Operator):
    bl_idname = "ama.batch_export"
    bl_label = "Batch Export"
    format: EnumProperty(name="Format", items=[(x, x.upper(), x) for x in ("fbx", "obj", "gltf", "stl")], default="fbx")

    def execute(self, context):
        folder = Path(bpy.path.abspath(context.scene.ama_props.export_path))
        targets = [o for o in (context.selected_objects or list(context.scene.objects)) if o.type == "MESH"]
        if not targets:
            self.report({'WARNING'}, "Select mesh objects to export")
            return {'CANCELLED'}
        failures = []
        fmt = "glb" if self.format == "gltf" else self.format
        for obj in targets:
            try:
                export_objects(folder / (safe_filename(obj.name) + "." + fmt), [obj], fmt)
            except Exception as exc:
                failures.append(f"{obj.name}: {exc}")
        if failures:
            self.report({'ERROR'}, f"{len(failures)} exports failed: {failures[0]}"[:250])
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported {len(targets)} objects")
        return {'FINISHED'}


class AMA_OT_EngineExport(Operator):
    bl_idname = "ama.engine_export"
    bl_label = "Engine Export"

    def execute(self, context):
        props = context.scene.ama_props
        fmt = "glb" if props.export_engine == "godot" else "fbx"
        path = Path(bpy.path.abspath(props.export_path)) / ("scene_export." + fmt)
        try:
            export_objects(path, list(context.selected_objects or context.scene.objects), fmt, props.export_engine)
        except Exception as exc:
            self.report({'ERROR'}, str(exc)[:250])
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported {path.name}")
        return {'FINISHED'}
