"""Generated code execution with static guard, line deadline and limited cleanup."""

import builtins
from array import array
import sys
import time
import traceback
import bpy
from ..core.security import SecurityValidator, SAFE_BUILTINS, restricted_import


class CodeExecutor:
    @classmethod
    def execute(cls, code, *, targets=None, collection=None, timeout=10):
        valid, reason = SecurityValidator.validate(code)
        if not valid:
            return False, reason
        if bpy.context.mode != "OBJECT":
            return False, "Switch to Object Mode before executing generated code"
        before = set(bpy.data.objects)
        targets = list(bpy.context.selected_objects if targets is None else targets)
        snapshots = []
        for obj in targets:
            if obj.type == "MESH":
                # Blender 3.6 can share UV storage after Mesh.copy(); writes via
                # the legacy UV API may also change the nominal backup. Capture
                # values independently so failure really restores the original.
                uv_values = []
                for layer in obj.data.uv_layers:
                    values = array("f", [0]) * (len(layer.data) * 2)
                    layer.data.foreach_get("uv", values)
                    uv_values.append((layer.name, values))
                snapshots.append(
                    (obj, obj.data.copy(), obj.matrix_world.copy(), set(obj.modifiers), uv_values)
                )
        output = []

        def capture(*args, sep=" ", end="\n"):
            if sum(len(line) for line in output) < 16000:
                output.append(sep.join(str(a) for a in args) + end)

        namespace = {
            "__builtins__": {n: getattr(builtins, n) for n in SAFE_BUILTINS},
            "__name__": "ai_model_code",
        }
        namespace["__builtins__"]["__import__"] = restricted_import
        namespace["__builtins__"]["print"] = capture
        import bmesh
        import math
        import mathutils
        import random
        import copy
        from .compat import set_geometry_input

        namespace.update(
            bpy=bpy,
            bmesh=bmesh,
            math=math,
            mathutils=mathutils,
            random=random,
            copy=copy,
            Vector=mathutils.Vector,
            Matrix=mathutils.Matrix,
            Euler=mathutils.Euler,
            Quaternion=mathutils.Quaternion,
            set_geometry_input=set_geometry_input,
        )
        started = time.monotonic()
        count = 0

        def deadline(frame, event, arg):
            nonlocal count
            if frame.f_code.co_filename == "<ai-model>" and event == "line":
                count += 1
                if count > 2_000_000 or (count % 100 == 0 and time.monotonic() - started > timeout):
                    raise TimeoutError("Generated Python exceeded its execution budget")
            return deadline

        old_trace = sys.gettrace()
        try:
            sys.settrace(deadline)
            exec(compile(code, "<ai-model>", "exec"), namespace)
            sys.settrace(old_trace)
            if collection is not None:
                for obj in set(bpy.data.objects) - before:
                    if obj.name not in collection.objects:
                        collection.objects.link(obj)
                    for owner in list(obj.users_collection):
                        if owner != collection:
                            owner.objects.unlink(obj)
            bpy.context.view_layer.update()
            return True, "".join(output).strip() or "Code executed successfully"
        except Exception:
            sys.settrace(old_trace)
            error = traceback.format_exc(limit=6)
            if bpy.context.mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except RuntimeError:
                    pass
            for obj in set(bpy.data.objects) - before:
                bpy.data.objects.remove(obj, do_unlink=True)
            for obj, mesh, matrix, modifiers, uv_values in snapshots:
                if obj.name in bpy.data.objects:
                    old_mesh = obj.data
                    obj.data, obj.matrix_world = mesh, matrix
                    for name, values in uv_values:
                        mesh.uv_layers[name].data.foreach_set("uv", values)
                    mesh.update()
                    for modifier in list(obj.modifiers):
                        if modifier not in modifiers:
                            obj.modifiers.remove(modifier)
                    if old_mesh.users == 0:
                        bpy.data.meshes.remove(old_mesh)
            return False, error
        finally:
            sys.settrace(old_trace)
            for obj, mesh, matrix, modifiers, uv_values in snapshots:
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
