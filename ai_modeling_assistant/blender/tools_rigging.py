"""blender / tools_rigging — extracted from the original add-on."""

from ..data.catalog import HUMANOID_SKELETON
from ..data.catalog import QUADRUPED_SKELETON
from bpy.props import EnumProperty
from bpy.props import IntProperty
from bpy.types import Operator
import bpy


class AMA_OT_CreateRig(Operator):
    """Create an armature rig"""
    bl_idname = "ama.create_rig"
    bl_label = "Create Rig"
    bl_options = {'REGISTER', 'UNDO'}

    rig_type: EnumProperty(
        name="Type",
        items=[
            ("humanoid", "Humanoid", "Humanoid skeleton"),
            ("quadruped", "Quadruped", "Quadruped skeleton"),
        ],
        default="humanoid",
    )

    def execute(self, context):
        skeleton = HUMANOID_SKELETON if self.rig_type == "humanoid" else QUADRUPED_SKELETON

        arm_data = bpy.data.armatures.new(name=f"{self.rig_type.title()}Rig")
        arm_obj = bpy.data.objects.new(f"{self.rig_type.title()}Rig", arm_data)
        context.collection.objects.link(arm_obj)

        context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='EDIT')

        bone_map = {}
        for joint in skeleton:
            bone = arm_data.edit_bones.new(joint["name"])
            bone.head = joint["head"]
            bone.tail = joint["tail"]
            if joint["parent"] and joint["parent"] in bone_map:
                parent = arm_data.edit_bones.get(joint["parent"])
                if parent:
                    bone.parent = parent
                    bone.use_connect = False
            bone_map[joint["name"]] = bone

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Created {self.rig_type} rig with {len(skeleton)} bones")
        return {'FINISHED'}


class AMA_OT_UVUnwrap(Operator):
    """Smart UV unwrap selected objects"""
    bl_idname = "ama.uv_unwrap"
    bl_label = "UV Unwrap"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(
        name="Method",
        items=[
            ("smart", "Smart UV", "Smart UV Project"),
            ("angle", "Angle Based", "Angle-based unwrap"),
            ("cube", "Cube Projection", "Cube projection"),
            ("cylinder", "Cylinder", "Cylinder projection"),
            ("sphere", "Sphere", "Sphere projection"),
        ],
        default="smart",
    )

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            if self.method == "smart":
                bpy.ops.uv.smart_project(angle_limit=1.151917306, island_margin=0.02)
            elif self.method == "angle":
                bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
            elif self.method == "cube":
                bpy.ops.uv.cube_project(cube_size=1.0)
            elif self.method == "cylinder":
                bpy.ops.uv.cylinder_project(direction='VIEW_ON_EQUATOR', align='POLAR_ZX')
            elif self.method == "sphere":
                bpy.ops.uv.sphere_project(direction='VIEW_ON_EQUATOR', align='POLAR_ZX')

            bpy.ops.object.mode_set(mode='OBJECT')

        self.report({'INFO'}, f"UV unwrapped ({self.method})")
        return {'FINISHED'}


class AMA_OT_BakeNormals(Operator):
    """Bake normal map for selected objects"""
    bl_idname = "ama.bake_normals"
    bl_label = "Bake Normals"
    bl_options = {'REGISTER', 'UNDO'}

    resolution: IntProperty(name="Resolution", default=1024, min=256, max=8192)

    def execute(self, context):
        selected = [o for o in context.selected_objects if o.type == 'MESH']
        if len(selected) < 2:
            self.report({'WARNING'}, "Select high-poly and low-poly meshes")
            return {'CANCELLED'}

        # Create image for normal map
        img = bpy.data.images.new("NormalMap", width=self.resolution, height=self.resolution, alpha=False)

        # Setup material on low-poly with normal map node
        low_poly = selected[-1]
        mat = low_poly.data.materials[0] if low_poly.data.materials else bpy.data.materials.new(name="BakeMat")
        mat.use_nodes = True
        if not low_poly.data.materials:
            low_poly.data.materials.append(mat)

        nodes = mat.node_tree.nodes

        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.image = img
        tex_node.select = True
        nodes.active = tex_node

        # Bake settings
        scene = context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.bake_type = 'NORMAL'
        scene.cycles.use_pass_direct = False
        scene.cycles.use_pass_indirect = False

        # Select high-poly as source
        bpy.ops.object.select_all(action='DESELECT')
        selected[0].select_set(True)  # High poly
        low_poly.select_set(True)  # Low poly
        context.view_layer.objects.active = low_poly

        try:
            bpy.ops.object.bake(type='NORMAL')
            self.report({'INFO'}, f"Baked normal map at {self.resolution}x{self.resolution}")
        except RuntimeError as e:
            self.report({'ERROR'}, f"Bake failed: {e}")

        return {'FINISHED'}
