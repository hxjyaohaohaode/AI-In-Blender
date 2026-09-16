"""blender / tools_procedural — extracted from the original add-on."""

from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.types import Operator
import bpy
import math


class AMA_OT_GenerateTerrain(Operator):
    """Generate procedural terrain"""
    bl_idname = "ama.generate_terrain"
    bl_label = "Generate Terrain"
    bl_options = {'REGISTER', 'UNDO'}

    size: FloatProperty(name="Size", default=10.0, min=1.0, max=100.0)
    subdivisions: IntProperty(name="Subdivisions", default=64, min=8, max=256)
    height: FloatProperty(name="Height", default=1.0, min=0.1, max=10.0)
    seed: IntProperty(name="Seed", default=42, min=0, max=9999)

    def execute(self, context):
        import random
        random.seed(self.seed)

        bpy.ops.mesh.primitive_plane_add(size=self.size)
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "Failed to create terrain plane")
            return {'CANCELLED'}
        obj.name = "Terrain"

        # Subdivide
        bpy.ops.object.mode_set(mode='EDIT')
        for _ in range(3):
            bpy.ops.mesh.subdivide()
        bpy.ops.object.mode_set(mode='OBJECT')

        # Displace vertices with noise-like heights
        for v in obj.data.vertices:
            # Simple multi-octave noise approximation
            x, y = v.co.x / self.size, v.co.y / self.size
            h = 0.0
            freq, amp = 1.0, 1.0
            for _ in range(4):
                h += amp * (math.sin(x * freq * 5 + self.seed) * math.cos(y * freq * 5 + self.seed * 0.7))
                freq *= 2.0
                amp *= 0.5
            v.co.z = h * self.height

        # Smooth shading
        bpy.ops.object.shade_smooth()

        # Add green material
        mat = bpy.data.materials.new(name="Terrain_Mat")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.15, 0.35, 0.08, 1)
            bsdf.inputs["Roughness"].default_value = 0.9
        obj.data.materials.append(mat)

        self.report({'INFO'}, "Terrain generated")
        return {'FINISHED'}


class AMA_OT_GenerateTree(Operator):
    """Generate a procedural tree"""
    bl_idname = "ama.generate_tree"
    bl_label = "Generate Tree"
    bl_options = {'REGISTER', 'UNDO'}

    trunk_height: FloatProperty(name="Trunk Height", default=1.5, min=0.3, max=5.0)
    trunk_radius: FloatProperty(name="Trunk Radius", default=0.08, min=0.02, max=0.3)
    crown_radius: FloatProperty(name="Crown Radius", default=0.6, min=0.2, max=2.0)
    crown_layers: IntProperty(name="Crown Layers", default=3, min=1, max=8)

    def execute(self, context):
        # Trunk
        bpy.ops.mesh.primitive_cylinder_add(
            radius=self.trunk_radius, depth=self.trunk_height,
            location=(0, 0, self.trunk_height / 2)
        )
        trunk = context.active_object
        trunk.name = "Tree_Trunk"

        mat_trunk = bpy.data.materials.new(name="Trunk_Mat")
        mat_trunk.use_nodes = True
        bsdf = mat_trunk.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.35, 0.2, 0.08, 1)
            bsdf.inputs["Roughness"].default_value = 0.85
        trunk.data.materials.append(mat_trunk)

        # Crown layers (cones)
        mat_crown = bpy.data.materials.new(name="Crown_Mat")
        mat_crown.use_nodes = True
        bsdf2 = mat_crown.node_tree.nodes.get("Principled BSDF")
        if bsdf2:
            bsdf2.inputs["Base Color"].default_value = (0.1, 0.45, 0.08, 1)
            bsdf2.inputs["Roughness"].default_value = 0.8

        for i in range(self.crown_layers):
            frac = i / max(self.crown_layers - 1, 1)
            layer_radius = self.crown_radius * (1.0 - frac * 0.4)
            layer_height = self.crown_radius * 0.8
            z = self.trunk_height + i * layer_height * 0.5

            bpy.ops.mesh.primitive_cone_add(
                radius1=layer_radius, radius2=0, depth=layer_height,
                location=(0, 0, z + layer_height / 2)
            )
            crown = context.active_object
            crown.name = f"Tree_Crown_{i}"
            crown.data.materials.append(mat_crown)

        self.report({'INFO'}, "Tree generated")
        return {'FINISHED'}


class AMA_OT_ScatterObjects(Operator):
    """Scatter selected objects randomly on active mesh"""
    bl_idname = "ama.scatter_objects"
    bl_label = "Scatter Objects"
    bl_options = {'REGISTER', 'UNDO'}

    count: IntProperty(name="Count", default=10, min=1, max=100)
    scale_variation: FloatProperty(name="Scale Variation", default=0.3, min=0.0, max=1.0)
    seed: IntProperty(name="Seed", default=42)

    def execute(self, context):
        import random
        random.seed(self.seed)

        selected = [o for o in context.selected_objects if o.type == 'MESH']
        active = context.active_object
        if not active or active.type != 'MESH' or len(selected) < 2:
            self.report({'WARNING'}, "Select source objects and active target mesh")
            return {'CANCELLED'}

        sources = [o for o in selected if o != active]
        if not sources:
            self.report({'WARNING'}, "Need at least one source object besides the target")
            return {'CANCELLED'}

        # Get target mesh bounds
        bbox = [active.matrix_world @ v.co for v in active.data.vertices]
        min_x = min(v.x for v in bbox)
        max_x = max(v.x for v in bbox)
        min_y = min(v.y for v in bbox)
        max_y = max(v.y for v in bbox)
        max_z = max(v.z for v in bbox)

        for i in range(self.count):
            src = random.choice(sources)
            new_obj = src.copy()
            new_obj.data = src.data.copy()
            new_obj.name = f"{src.name}_scatter_{i}"
            context.collection.objects.link(new_obj)

            new_obj.location = (
                random.uniform(min_x, max_x),
                random.uniform(min_y, max_y),
                max_z,
            )
            s = 1.0 + random.uniform(-self.scale_variation, self.scale_variation)
            new_obj.scale = (s, s, s)
            new_obj.rotation_euler.z = random.uniform(0, math.pi * 2)

        self.report({'INFO'}, f"Scattered {self.count} objects")
        return {'FINISHED'}
