"""blender / tools_animation — extracted from the original add-on."""

from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.types import Operator
import bpy
import math


class AMA_OT_WalkCycle(Operator):
    """Create a simple walk cycle animation"""
    bl_idname = "ama.walk_cycle"
    bl_label = "Walk Cycle"
    bl_options = {'REGISTER', 'UNDO'}

    frames: IntProperty(name="Frames", default=30, min=10, max=120)

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        scene = context.scene
        scene.frame_start = 1
        scene.frame_end = self.frames

        # Simple up-down oscillation for walk
        for frame in range(1, self.frames + 1):
            scene.frame_set(frame)
            t = (frame - 1) / self.frames * 2 * math.pi
            obj.location.z = abs(math.sin(t)) * 0.05
            obj.keyframe_insert(data_path="location", index=2, frame=frame)

            # Slight side sway
            obj.location.x = math.sin(t * 0.5) * 0.01
            obj.keyframe_insert(data_path="location", index=0, frame=frame)

        self.report({'INFO'}, f"Created walk cycle ({self.frames} frames)")
        return {'FINISHED'}


class AMA_OT_BreathingAnim(Operator):
    """Create breathing animation"""
    bl_idname = "ama.breathing_anim"
    bl_label = "Breathing"
    bl_options = {'REGISTER', 'UNDO'}

    frames: IntProperty(name="Frames", default=60, min=20, max=240)
    intensity: FloatProperty(name="Intensity", default=0.02, min=0.001, max=0.1)

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        scene = context.scene
        scene.frame_start = 1
        scene.frame_end = self.frames

        base_scale = list(obj.scale)

        for frame in range(1, self.frames + 1):
            scene.frame_set(frame)
            t = (frame - 1) / self.frames * 2 * math.pi
            s = math.sin(t) * self.intensity
            obj.scale = (base_scale[0] + s, base_scale[1] + s * 0.3, base_scale[2] + s)
            obj.keyframe_insert(data_path="scale", frame=frame)

        self.report({'INFO'}, "Created breathing animation")
        return {'FINISHED'}


class AMA_OT_CameraOrbit(Operator):
    """Create camera orbit animation"""
    bl_idname = "ama.camera_orbit"
    bl_label = "Camera Orbit"
    bl_options = {'REGISTER', 'UNDO'}

    frames: IntProperty(name="Frames", default=120, min=30, max=600)
    radius: FloatProperty(name="Radius", default=5.0, min=1.0, max=50.0)
    height: FloatProperty(name="Height", default=2.0, min=0.0, max=20.0)

    def execute(self, context):
        scene = context.scene
        scene.frame_start = 1
        scene.frame_end = self.frames

        # Find or create camera
        cam = None
        for obj in scene.objects:
            if obj.type == 'CAMERA':
                cam = obj
                break
        if not cam:
            cam_data = bpy.data.cameras.new("OrbitCam")
            cam = bpy.data.objects.new("OrbitCam", cam_data)
            context.collection.objects.link(cam)
            scene.camera = cam

        for frame in range(1, self.frames + 1):
            scene.frame_set(frame)
            t = (frame - 1) / self.frames * 2 * math.pi
            cam.location = (
                math.cos(t) * self.radius,
                math.sin(t) * self.radius,
                self.height,
            )
            cam.keyframe_insert(data_path="location", frame=frame)
            # Point at origin
            direction = cam.location
            cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
            cam.keyframe_insert(data_path="rotation_euler", frame=frame)

        self.report({'INFO'}, f"Created camera orbit ({self.frames} frames)")
        return {'FINISHED'}
