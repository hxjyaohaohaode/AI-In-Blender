"""blender / tools_materials — extracted from the original add-on."""

from ..data.catalog import LOD_LEVELS
from ..data.catalog import MATERIAL_PRESETS
from ..data.catalog import MODIFIER_PRESETS
from bpy.props import StringProperty
from bpy.types import Operator
import bpy


class AMA_OT_ApplyMaterial(Operator):
    """Apply a material preset to selected objects"""
    bl_idname = "ama.apply_material"
    bl_label = "Apply Material"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()

    def execute(self, context):
        preset = MATERIAL_PRESETS.get(self.material_name)
        if not preset:
            self.report({'WARNING'}, f"Unknown material: {self.material_name}")
            return {'CANCELLED'}

        mat = bpy.data.materials.new(name=self.material_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = preset["base_color"]
            bsdf.inputs["Metallic"].default_value = preset.get("metallic", 0.0)
            bsdf.inputs["Roughness"].default_value = preset.get("roughness", 0.5)
            if "transmission" in preset:
                try:
                    bsdf.inputs["Transmission Weight"].default_value = preset["transmission"]  # 4.x
                except KeyError:
                    try:
                        bsdf.inputs["Transmission"].default_value = preset["transmission"]  # 3.x
                    except KeyError:
                        pass
            if "ior" in preset:
                try:
                    bsdf.inputs["IOR"].default_value = preset["ior"]
                except KeyError:
                    pass
            if "emission" in preset:
                try:
                    bsdf.inputs["Emission Color"].default_value = preset["emission"]  # 4.x
                    bsdf.inputs["Emission Strength"].default_value = preset.get("emission_strength", 1.0)
                except KeyError:
                    try:
                        bsdf.inputs["Emission"].default_value = preset["emission"]  # 3.x
                        bsdf.inputs["Emission Strength"].default_value = preset.get("emission_strength", 1.0)
                    except KeyError:
                        pass
            if "subsurface" in preset:
                try:
                    bsdf.inputs["Subsurface Weight"].default_value = preset["subsurface"]  # 4.x
                except KeyError:
                    try:
                        bsdf.inputs["Subsurface"].default_value = preset["subsurface"]  # 3.x
                    except KeyError:
                        pass

        for obj in context.selected_objects:
            if obj.type == 'MESH':
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)

        self.report({'INFO'}, f"Applied {self.material_name}")
        return {'FINISHED'}


class AMA_OT_ApplyModifier(Operator):
    """Apply a modifier preset to selected objects"""
    bl_idname = "ama.apply_modifier"
    bl_label = "Apply Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_name: StringProperty()

    def execute(self, context):
        preset = MODIFIER_PRESETS.get(self.modifier_name)
        if not preset:
            self.report({'WARNING'}, f"Unknown modifier: {self.modifier_name}")
            return {'CANCELLED'}

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            mod = obj.modifiers.new(name=self.modifier_name, type=preset["type"])
            for key, val in preset.items():
                if key == "type":
                    continue
                if key == "use_axis" and hasattr(mod, "use_axis"):
                    for i, v in enumerate(val):
                        mod.use_axis[i] = v
                elif hasattr(mod, key):
                    try:
                        setattr(mod, key, val)
                    except (AttributeError, TypeError):
                        pass

        self.report({'INFO'}, f"Applied {self.modifier_name}")
        return {'FINISHED'}


class AMA_OT_GenerateLOD(Operator):
    """Generate LOD levels for the active object"""
    bl_idname = "ama.generate_lod"
    bl_label = "Generate LOD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object")
            return {'CANCELLED'}

        for level_name, ratio in LOD_LEVELS:
            # Duplicate
            new_obj = obj.copy()
            new_obj.data = obj.data.copy()
            new_obj.name = f"{obj.name}_{level_name}"
            context.collection.objects.link(new_obj)

            if ratio < 1.0:
                mod = new_obj.modifiers.new(name="DecimateLOD", type='DECIMATE')
                mod.ratio = ratio
                # Apply modifier
                bpy.context.view_layer.objects.active = new_obj
                bpy.ops.object.modifier_apply(modifier="DecimateLOD")
                bpy.context.view_layer.objects.active = obj

            # Move LOD levels further from origin for visibility
            new_obj.location.x += (LOD_LEVELS.index((level_name, ratio)) + 1) * 3

        self.report({'INFO'}, f"Generated {len(LOD_LEVELS)} LOD levels")
        return {'FINISHED'}
