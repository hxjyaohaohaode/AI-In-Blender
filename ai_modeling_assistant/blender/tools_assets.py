"""blender / tools_assets — extracted from the original add-on."""

from ..blender.state import _asset_registry
from ..blender.state import _cost_tracker
from ..blender.state import _version_snapshots
from ..blender.state import get_conversation
from bpy.props import EnumProperty
from bpy.props import FloatProperty
from bpy.props import StringProperty
from bpy.types import Operator
import bpy
import math
import time


class AMA_OT_ClearHistory(Operator):
    """Clear conversation history"""
    bl_idname = "ama.clear_history"
    bl_label = "Clear History"
    bl_options = {'REGISTER'}

    def execute(self, context):
        conv = get_conversation()
        conv.clear()
        props = context.scene.ama_props
        props.last_code = ""
        props.last_think = ""
        props.status_message = "History cleared"
        return {'FINISHED'}


class AMA_OT_ResetCost(Operator):
    """Reset cost tracker"""
    bl_idname = "ama.reset_cost"
    bl_label = "Reset Cost"
    bl_options = {'REGISTER'}

    def execute(self, context):
        _cost_tracker.reset()
        self.report({'INFO'}, "Cost tracker reset")
        return {'FINISHED'}


class AMA_OT_BatchRename(Operator):
    """Batch rename selected objects"""
    bl_idname = "ama.batch_rename"
    bl_label = "Batch Rename"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode",
        items=[
            ("prefix", "Add Prefix", "Add prefix to names"),
            ("suffix", "Add Suffix", "Add suffix to names"),
            ("replace", "Find & Replace", "Find and replace in names"),
            ("sequential", "Sequential", "Rename to sequential numbers"),
        ],
        default="prefix",
    )

    def execute(self, context):
        props = context.scene.ama_props
        targets = context.selected_objects if context.selected_objects else context.scene.objects

        for i, obj in enumerate(targets):
            if self.mode == "prefix":
                obj.name = props.batch_prefix + obj.name
            elif self.mode == "suffix":
                obj.name = obj.name + props.batch_suffix
            elif self.mode == "replace":
                obj.name = obj.name.replace(props.batch_find, props.batch_replace)
            elif self.mode == "sequential":
                obj.name = f"{props.batch_prefix}{i:03d}"

        self.report({'INFO'}, f"Renamed {len(targets)} objects")
        return {'FINISHED'}


class AMA_OT_SceneSnapshot(Operator):
    """Save a version snapshot of the scene"""
    bl_idname = "ama.scene_snapshot"
    bl_label = "Save Snapshot"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.ama_props
        name = props.version_name.strip() or f"Snapshot_{int(time.time())}"

        snapshot = {
            "name": name,
            "timestamp": time.time(),
            "objects": [],
        }

        for obj in context.scene.objects:
            if obj.type == 'MESH':
                obj_data = {
                    "name": obj.name,
                    "location": tuple(obj.location),
                    "rotation": tuple(obj.rotation_euler),
                    "scale": tuple(obj.scale),
                    "vertex_count": len(obj.data.vertices),
                    "face_count": len(obj.data.polygons),
                }
                snapshot["objects"].append(obj_data)

        scene_name = context.scene.name
        if scene_name not in _version_snapshots:
            _version_snapshots[scene_name] = []
        _version_snapshots[scene_name].append(snapshot)

        self.report({'INFO'}, f"Snapshot saved: {name} ({len(snapshot['objects'])} objects)")
        return {'FINISHED'}


class AMA_OT_SceneVersionsList(Operator):
    """List saved version snapshots"""
    bl_idname = "ama.scene_versions_list"
    bl_label = "List Versions"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene_name = context.scene.name
        snapshots = _version_snapshots.get(scene_name, [])
        if not snapshots:
            self.report({'INFO'}, "No snapshots saved")
            return {'FINISHED'}

        lines = [f"=== Versions for {scene_name} ==="]
        for i, snap in enumerate(snapshots):
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(snap["timestamp"]))
            lines.append(f"  {i}: {snap['name']} ({ts}, {len(snap['objects'])} objects)")

        self.report({'INFO'}, "\n".join(lines))
        return {'FINISHED'}


class AMA_OT_SelectByMaterial(Operator):
    """Select all objects using the active material"""
    bl_idname = "ama.select_by_material"
    bl_label = "Select by Material"
    bl_options = {'REGISTER'}

    def execute(self, context):
        active_obj = context.active_object
        if not active_obj or not active_obj.data.materials:
            self.report({'WARNING'}, "No material on active object")
            return {'CANCELLED'}

        mat = active_obj.data.materials[0]
        bpy.ops.object.select_all(action='DESELECT')

        count = 0
        for obj in context.scene.objects:
            if obj.type == 'MESH' and mat in obj.data.materials:
                obj.select_set(True)
                count += 1

        self.report({'INFO'}, f"Selected {count} objects with material '{mat.name}'")
        return {'FINISHED'}


class AMA_OT_SelectNonManifold(Operator):
    """Select objects with non-manifold geometry"""
    bl_idname = "ama.select_non_manifold"
    bl_label = "Select Non-Manifold"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        count = 0

        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            non_manifold = [e for e in bm.edges if not e.is_manifold]
            bm.free()
            if non_manifold:
                obj.select_set(True)
                count += 1

        self.report({'INFO'}, f"Selected {count} non-manifold objects")
        return {'FINISHED'}


class AMA_OT_SelectLoose(Operator):
    """Select objects with loose vertices"""
    bl_idname = "ama.select_loose"
    bl_label = "Select Loose"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        count = 0

        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            loose = [v for v in bm.verts if not v.link_edges]
            bm.free()
            if loose:
                obj.select_set(True)
                count += 1

        self.report({'INFO'}, f"Selected {count} objects with loose geometry")
        return {'FINISHED'}


class AMA_OT_CleanupEmpty(Operator):
    """Delete empty objects and orphan data"""
    bl_idname = "ama.cleanup_empty"
    bl_label = "Cleanup Empty"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        removed = 0

        # Remove empty objects
        for obj in list(context.scene.objects):
            if obj.type == 'EMPTY':
                bpy.data.objects.remove(obj, do_unlink=True)
                removed += 1

        # Remove orphan meshes
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
                removed += 1

        # Remove orphan materials
        for mat in list(bpy.data.materials):
            if mat.users == 0:
                bpy.data.materials.remove(mat)
                removed += 1

        # Remove orphan images
        for img in list(bpy.data.images):
            if img.users == 0 and img.name != "Render Result":
                bpy.data.images.remove(img)
                removed += 1

        self.report({'INFO'}, f"Cleaned up {removed} items")
        return {'FINISHED'}


class AMA_OT_RegisterAsset(Operator):
    """Register selected object as asset"""
    bl_idname = "ama.register_asset"
    bl_label = "Register Asset"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.ama_props
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        name = props.asset_name.strip() or obj.name
        asset = {
            "name": name,
            "category": props.asset_category,
            "object_name": obj.name,
            "type": obj.type,
            "registered_at": time.time(),
        }

        # Check for duplicates
        existing = [a for a in _asset_registry if a["name"] == name]
        if existing:
            existing[0].update(asset)
        else:
            _asset_registry.append(asset)

        self.report({'INFO'}, f"Asset registered: {name}")
        return {'FINISHED'}


class AMA_OT_SearchAssets(Operator):
    """Search registered assets"""
    bl_idname = "ama.search_assets"
    bl_label = "Search Assets"
    bl_options = {'REGISTER'}

    query: StringProperty(name="Query", default="")

    def execute(self, context):
        if not _asset_registry:
            self.report({'INFO'}, "No assets registered")
            return {'FINISHED'}

        q = self.query.lower()
        results = [a for a in _asset_registry if q in a["name"].lower() or q in a.get("category", "").lower()]

        if not results:
            self.report({'INFO'}, f"No assets matching '{self.query}'")
            return {'FINISHED'}

        lines = [f"=== Assets matching '{self.query}' ==="]
        for a in results:
            lines.append(f"  {a['name']} [{a['category']}] - {a['object_name']}")

        self.report({'INFO'}, "\n".join(lines))
        return {'FINISHED'}


class AMA_OT_AssemblyLayout(Operator):
    """Auto-layout selected objects in a grid"""
    bl_idname = "ama.assembly_layout"
    bl_label = "Auto Layout"
    bl_options = {'REGISTER', 'UNDO'}

    spacing: FloatProperty(name="Spacing", default=2.0, min=0.5, max=10.0)

    def execute(self, context):
        selected = [o for o in context.selected_objects]
        if not selected:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        cols = math.ceil(math.sqrt(len(selected)))
        for i, obj in enumerate(selected):
            row = i // cols
            col = i % cols
            obj.location.x = col * self.spacing
            obj.location.y = -row * self.spacing
            obj.location.z = 0

        self.report({'INFO'}, f"Laid out {len(selected)} objects in grid")
        return {'FINISHED'}


class AMA_OT_AssemblyAlign(Operator):
    """Align selected objects"""
    bl_idname = "ama.assembly_align"
    bl_label = "Align"
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(
        name="Axis",
        items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")],
        default="X",
    )
    mode: EnumProperty(
        name="Mode",
        items=[
            ("min", "Min", "Align to minimum"),
            ("max", "Max", "Align to maximum"),
            ("center", "Center", "Align to center"),
        ],
        default="center",
    )

    def execute(self, context):
        selected = [o for o in context.selected_objects]
        if len(selected) < 2:
            self.report({'WARNING'}, "Select at least 2 objects")
            return {'CANCELLED'}

        axis_idx = {"X": 0, "Y": 1, "Z": 2}[self.axis]
        coords = [o.location[axis_idx] for o in selected]

        if self.mode == "min":
            target = min(coords)
        elif self.mode == "max":
            target = max(coords)
        else:
            target = (min(coords) + max(coords)) / 2

        for obj in selected:
            obj.location[axis_idx] = target

        self.report({'INFO'}, f"Aligned {len(selected)} objects on {self.axis} ({self.mode})")
        return {'FINISHED'}
