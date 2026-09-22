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
    bl_options = {"REGISTER", "UNDO"}

    size: FloatProperty(name="Size", default=10.0, min=1.0, max=100.0)
    subdivisions: IntProperty(name="Subdivisions", default=64, min=8, max=256)
    height: FloatProperty(name="Height", default=1.0, min=0.1, max=10.0)
    seed: IntProperty(name="Seed", default=42, min=0, max=9999)

    def execute(self, context):
        if context.mode != "OBJECT":
            self.report({"WARNING"}, "Switch to Object Mode before generating terrain")
            return {"CANCELLED"}
        n = self.subdivisions
        vertices = [
            ((x / n - 0.5) * self.size, (y / n - 0.5) * self.size, 0)
            for y in range(n + 1)
            for x in range(n + 1)
        ]
        faces = [
            (y * (n + 1) + x, y * (n + 1) + x + 1, (y + 1) * (n + 1) + x + 1, (y + 1) * (n + 1) + x)
            for y in range(n)
            for x in range(n)
        ]
        mesh = bpy.data.meshes.new("Terrain")
        mesh.from_pydata(vertices, [], faces)
        obj = bpy.data.objects.new("Terrain", mesh)
        context.collection.objects.link(obj)

        # Displace vertices with noise-like heights
        for v in obj.data.vertices:
            # Simple multi-octave noise approximation
            x, y = v.co.x / self.size, v.co.y / self.size
            h = 0.0
            freq, amp = 1.0, 1.0
            for _ in range(4):
                h += amp * (
                    math.sin(x * freq * 5 + self.seed) * math.cos(y * freq * 5 + self.seed * 0.7)
                )
                freq *= 2.0
                amp *= 0.5
            v.co.z = h * self.height

        # Smooth shading
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        mesh.update()

        # Add green material
        mat = bpy.data.materials.new(name="Terrain_Mat")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.15, 0.35, 0.08, 1)
            bsdf.inputs["Roughness"].default_value = 0.9
        obj.data.materials.append(mat)

        self.report({"INFO"}, "Terrain generated")
        return {"FINISHED"}


class AMA_OT_GenerateTree(Operator):
    """Generate a procedural tree"""

    bl_idname = "ama.generate_tree"
    bl_label = "Generate Tree"
    bl_options = {"REGISTER", "UNDO"}

    trunk_height: FloatProperty(name="Trunk Height", default=1.5, min=0.3, max=5.0)
    trunk_radius: FloatProperty(name="Trunk Radius", default=0.08, min=0.02, max=0.3)
    crown_radius: FloatProperty(name="Crown Radius", default=0.6, min=0.2, max=2.0)
    crown_layers: IntProperty(name="Crown Layers", default=3, min=1, max=8)

    def execute(self, context):
        # Trunk
        bpy.ops.mesh.primitive_cylinder_add(
            radius=self.trunk_radius,
            depth=self.trunk_height,
            location=(0, 0, self.trunk_height / 2),
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
                radius1=layer_radius,
                radius2=0,
                depth=layer_height,
                location=(0, 0, z + layer_height / 2),
            )
            crown = context.active_object
            crown.name = f"Tree_Crown_{i}"
            crown.data.materials.append(mat_crown)

        self.report({"INFO"}, "Tree generated")
        return {"FINISHED"}


class AMA_OT_ScatterObjects(Operator):
    """Scatter selected objects randomly on active mesh"""

    bl_idname = "ama.scatter_objects"
    bl_label = "Scatter Objects"
    bl_options = {"REGISTER", "UNDO"}

    count: IntProperty(name="Count", default=10, min=1, max=100)
    scale_variation: FloatProperty(name="Scale Variation", default=0.3, min=0.0, max=1.0)
    seed: IntProperty(name="Seed", default=42)

    def execute(self, context):
        import random
        from bisect import bisect_left
        from mathutils import Matrix, Quaternion, Vector

        rng = random.Random(self.seed)

        selected = [o for o in context.selected_objects if o.type == "MESH"]
        active = context.active_object
        if not active or active.type != "MESH" or len(selected) < 2:
            self.report({"WARNING"}, "Select source objects and active target mesh")
            return {"CANCELLED"}

        sources = [o for o in selected if o != active]
        if not sources:
            self.report({"WARNING"}, "Need at least one source object besides the target")
            return {"CANCELLED"}

        if context.mode != "OBJECT":
            self.report({"WARNING"}, "Switch to Object Mode before scattering")
            return {"CANCELLED"}
        evaluated = active.evaluated_get(context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        triangles, cumulative, area = [], [], 0.0
        try:
            mesh.calc_loop_triangles()
            for triangle in mesh.loop_triangles:
                a, b, c = [evaluated.matrix_world @ mesh.vertices[i].co for i in triangle.vertices]
                normal = (b - a).cross(c - a)
                if normal.length > 1e-12:
                    area += normal.length / 2
                    triangles.append((a.copy(), b.copy(), c.copy(), normal.normalized()))
                    cumulative.append(area)
        finally:
            evaluated.to_mesh_clear()
        if not triangles:
            self.report({"WARNING"}, "Target has no non-degenerate surface to scatter onto")
            return {"CANCELLED"}

        for i in range(self.count):
            src = rng.choice(sources)
            a, b, c, normal = triangles[bisect_left(cumulative, rng.random() * area)]
            u, v = math.sqrt(rng.random()), rng.random()
            point = (1 - u) * a + u * (1 - v) * b + u * v * c
            scale = src.matrix_world.to_scale() * max(
                0.001, 1.0 + rng.uniform(-self.scale_variation, self.scale_variation)
            )
            rotation = normal.to_track_quat("Z", "Y") @ Quaternion(
                Vector((0, 0, 1)), rng.uniform(0, math.tau)
            )
            new_obj = src.copy()
            new_obj.data = src.data.copy()
            new_obj.parent = None
            if "ama_asset_id" in new_obj:
                del new_obj["ama_asset_id"]
            new_obj.name = f"{src.name}_scatter_{i}"
            context.collection.objects.link(new_obj)

            new_obj.matrix_world = Matrix.LocRotScale(point, rotation, scale)

        self.report({"INFO"}, f"Scattered {self.count} objects")
        return {"FINISHED"}
