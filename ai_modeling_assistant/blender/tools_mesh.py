"""blender / tools_mesh — extracted from the original add-on."""

from ..blender.quality import MeshAnalyzer
from ..blender.quality import QualityChecker
from ..blender.scene import PostProcessor
from bpy.props import EnumProperty
from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.types import Operator
import bpy
from .compat import recalculate_normals
import logging
logger = logging.getLogger("AIInBlender")


class AMA_OT_AnalyzeMesh(Operator):
    """Analyze mesh quality of active object"""
    bl_idname = "ama.analyze_mesh"
    bl_label = "Analyze Mesh"
    bl_options = {'REGISTER'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        result = MeshAnalyzer.analyze(obj)
        if "error" in result:
            self.report({'WARNING'}, result["error"])
            return {'CANCELLED'}

        lines = [f"=== Mesh Analysis: {result['name']} ==="]
        lines.append(f"Vertices: {result['vertices']}")
        lines.append(f"Faces: {result['faces']} (Quads: {result['quads']}, Tris: {result['triangles']}, N-gons: {result['ngons']})")
        lines.append(f"Materials: {result['materials']}")
        lines.append(f"UV Layers: {result['uv_layers']}")
        lines.append(f"Non-manifold edges: {result['non_manifold_edges']}")
        lines.append(f"Loose vertices: {result['loose_vertices']}")
        lines.append(f"Loose edges: {result['loose_edges']}")
        if "dimensions" in result:
            d = result["dimensions"]
            lines.append(f"Dimensions: {d[0]:.3f} x {d[1]:.3f} x {d[2]:.3f}")

        msg = "\n".join(lines)
        self.report({'INFO'}, msg)
        logger.info(msg)
        return {'FINISHED'}


class AMA_OT_QualityCheck(Operator):
    """Run quality check on all meshes"""
    bl_idname = "ama.quality_check"
    bl_label = "Quality Check"
    bl_options = {'REGISTER'}

    def execute(self, context):
        issues = QualityChecker.check_all()
        if not issues:
            self.report({'INFO'}, "All meshes passed quality check")
            return {'FINISHED'}

        lines = [f"Found {len(issues)} issues:"]
        for issue in issues:
            lines.append(f"  [{issue['severity']}] {issue['object']}: {issue['type']} x{issue['count']}")

        self.report({'WARNING'}, "\n".join(lines))
        return {'FINISHED'}


class AMA_OT_FixObject(Operator):
    """Fix mesh issues on active object"""
    bl_idname = "ama.fix_object"
    bl_label = "Fix Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        success, msg = QualityChecker.fix_object(obj.name)
        if success:
            self.report({'INFO'}, msg)
        else:
            self.report({'WARNING'}, msg)
        return {'FINISHED'}


class AMA_OT_PostProcess(Operator):
    """Run automatic post-processing on all scene meshes"""
    bl_idname = "ama.post_process"
    bl_label = "Post-Process"
    bl_description = "Auto-clean all meshes: remove doubles, fix normals, delete loose geometry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        success, msg = PostProcessor.process_all()
        self.report({'INFO'}, msg[:300])
        return {'FINISHED'}


class AMA_OT_ExtrudeSelected(Operator):
    """Extrude selected faces"""
    bl_idname = "ama.extrude_selected"
    bl_label = "Extrude"
    bl_description = "Extrude selected faces along normal"
    bl_options = {'REGISTER', 'UNDO'}

    distance: FloatProperty(name="Distance", default=0.1, min=-10.0, max=10.0)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, self.distance)}
        )
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Extruded by {self.distance}")
        return {'FINISHED'}


class AMA_OT_BevelSelected(Operator):
    """Bevel selected edges"""
    bl_idname = "ama.bevel_selected"
    bl_label = "Bevel"
    bl_description = "Bevel selected edges"
    bl_options = {'REGISTER', 'UNDO'}

    offset: FloatProperty(name="Offset", default=0.02, min=0.001, max=1.0)
    segments: IntProperty(name="Segments", default=3, min=1, max=12)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.bevel(offset=self.offset, segments=self.segments)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Beveled (offset={self.offset}, segments={self.segments})")
        return {'FINISHED'}


class AMA_OT_InsetSelected(Operator):
    """Inset selected faces"""
    bl_idname = "ama.inset_selected"
    bl_label = "Inset"
    bl_description = "Inset selected faces"
    bl_options = {'REGISTER', 'UNDO'}

    thickness: FloatProperty(name="Thickness", default=0.05, min=0.001, max=1.0)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.inset(thickness=self.thickness)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Inset (thickness={self.thickness})")
        return {'FINISHED'}


class AMA_OT_LoopCut(Operator):
    """Add loop cuts to active mesh"""
    bl_idname = "ama.loop_cut"
    bl_label = "Loop Cut"
    bl_description = "Add loop cuts to the mesh"
    bl_options = {'REGISTER', 'UNDO'}

    cuts: IntProperty(name="Number of Cuts", default=2, min=1, max=20)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.loopcut_slide(MESH_OT_loopcut={"number_cuts": self.cuts})
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Added {self.cuts} loop cuts")
        return {'FINISHED'}


class AMA_OT_SubdivideMesh(Operator):
    """Subdivide selected faces"""
    bl_idname = "ama.subdivide_mesh"
    bl_label = "Subdivide"
    bl_description = "Subdivide mesh faces"
    bl_options = {'REGISTER', 'UNDO'}

    cuts: IntProperty(name="Cuts", default=2, min=1, max=10)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.subdivide(number_cuts=self.cuts)
        recalculate_normals()
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Subdivided ({self.cuts} cuts)")
        return {'FINISHED'}


class AMA_OT_MergeByDistance(Operator):
    """Merge vertices by distance"""
    bl_idname = "ama.merge_by_distance"
    bl_label = "Merge by Distance"
    bl_description = "Merge vertices within threshold distance"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(name="Threshold", default=0.001, min=0.0001, max=0.1)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=self.threshold)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Merged vertices (threshold={self.threshold})")
        return {'FINISHED'}


class AMA_OT_RecalculateNormals(Operator):
    """Recalculate normals for selected objects"""
    bl_idname = "ama.recalculate_normals"
    bl_label = "Recalculate Normals"
    bl_description = "Make all face normals consistent (outward)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            recalculate_normals()
            bpy.ops.object.mode_set(mode='OBJECT')
            count += 1

        self.report({'INFO'}, f"Recalculated normals for {count} objects")
        return {'FINISHED'}


class AMA_OT_SmoothShading(Operator):
    """Apply smooth shading to selected objects"""
    bl_idname = "ama.smooth_shading"
    bl_label = "Smooth Shading"
    bl_description = "Apply smooth shading"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.shade_smooth()
        self.report({'INFO'}, "Applied smooth shading")
        return {'FINISHED'}


class AMA_OT_FlatShading(Operator):
    """Apply flat shading to selected objects"""
    bl_idname = "ama.flat_shading"
    bl_label = "Flat Shading"
    bl_description = "Apply flat shading"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.shade_flat()
        self.report({'INFO'}, "Applied flat shading")
        return {'FINISHED'}


class AMA_OT_ApplyAllModifiers(Operator):
    """Apply all modifiers on selected objects"""
    bl_idname = "ama.apply_all_modifiers"
    bl_label = "Apply All Modifiers"
    bl_description = "Apply all modifiers on selected mesh objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            context.view_layer.objects.active = obj
            for mod in list(obj.modifiers):
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    count += 1
                except RuntimeError as e:
                    logger.warning("Failed to apply modifier %s on %s: %s", mod.name, obj.name, e)
        self.report({'INFO'}, f"Applied {count} modifiers")
        return {'FINISHED'}


class AMA_OT_DuplicateSymmetry(Operator):
    """Mirror selected objects across an axis"""
    bl_idname = "ama.duplicate_symmetry"
    bl_label = "Mirror Duplicate"
    bl_description = "Duplicate and mirror objects for symmetry"
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(
        name="Axis",
        items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")],
        default="X",
    )

    def execute(self, context):
        selected = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}

        axis_idx = {"X": 0, "Y": 1, "Z": 2}[self.axis]
        new_objects = []

        for obj in selected:
            new_obj = obj.copy()
            new_obj.data = obj.data.copy()
            new_obj.name = f"{obj.name}_Mirror{self.axis}"
            context.collection.objects.link(new_obj)

            # Mirror location
            new_obj.location[axis_idx] *= -1

            # Mirror scale
            scale = list(new_obj.scale)
            scale[axis_idx] *= -1
            new_obj.scale = tuple(scale)

            new_objects.append(new_obj)

        # Select new objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in new_objects:
            obj.select_set(True)

        self.report({'INFO'}, f"Mirrored {len(new_objects)} objects on {self.axis} axis")
        return {'FINISHED'}
