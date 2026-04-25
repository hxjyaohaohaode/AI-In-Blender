# -*- coding: utf-8 -*-
"""
AI Modeling Assistant for Blender
=================================
AI-powered 3D modeling assistant supporting any OpenAI-compatible API.
Compatible with Blender 3.6+ and 4.x.

Author: Community
License: GPL-3.0
Repository: https://github.com/your-repo/ai-modeling-assistant
"""

bl_info = {
    "name": "AI Modeling Assistant",
    "author": "Community",
    "version": (2, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D View > Sidebar > AI Model",
    "description": "AI-powered 3D modeling assistant for Blender",
    "warning": "",
    "doc_url": "https://github.com/your-repo/ai-modeling-assistant",
    "category": "3D View",
}

import bpy
import json
import math
import sys
import time
import traceback
import ssl
import urllib.request
import urllib.error
import re
import threading
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from bpy.props import (
    StringProperty, EnumProperty, BoolProperty,
    IntProperty, FloatProperty, CollectionProperty,
    PointerProperty
)
from bpy.types import Panel, Operator, PropertyGroup, UIList

# ============================================================================
#  Logging
# ============================================================================
logger = logging.getLogger("AIModelingAssistant")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[AI Model] %(levelname)s: %(message)s"
    ))
    logger.addHandler(_handler)

# ============================================================================
#  Constants
# ============================================================================

# --- System Prompt (comprehensive modeling expertise) ---
SYSTEM_PROMPT = r"""You are an expert Blender Python modeler. You create beautiful, detailed, production-quality 3D models. You think deeply before writing code.

===== THINKING PROCESS (mandatory — do this silently before every response) =====

PHASE 1 — DESIGN ANALYSIS
- What is the object? What is its purpose (game prop / architectural / character / vehicle)?
- Identify ALL distinct parts. A "chair" isn't one box — it's seat, backrest, 4 legs, armrests, crossbars, decorative elements.
- For each part: what geometric shape best represents it? (box, cylinder, sphere, cone, torus, lathe profile, extruded shape?)

PHASE 2 — PROPORTIONS & SCALE
- Work in meters. Reference real-world sizes:
  Chair seat: 0.45m high, 0.45x0.45m | Table: 0.75m high | Door: 2.0x0.9m | Human: 1.75m tall
  Sword: ~1.1m total | Shield: ~0.6m diameter | Barrel: 0.6m tall, 0.4m diameter
- Ensure parts connect logically. Legs touch the floor. Seat sits on legs. Backrest rises from seat.

PHASE 3 — TOPOLOGY STRATEGY
- HARD SURFACE (furniture, weapons, architecture): Start from cubes/cylinders. Use extrude + bevel for detail. Sharp edges with bevel modifier.
- ORGANIC (characters, creatures, plants): Start from spheres. Use subdivision surface + edge loops. Smooth shading.
- MECHANICAL (gears, pipes, joints): Boolean operations. Precise dimensions. Multiple materials.
- DECORATIVE (scrollwork, filigree): Use curves with bevel. Lathe/spin for radial patterns.

PHASE 4 — MATERIAL STRATEGY
- Each distinct part gets its own named material.
- Match real-world PBR properties:
  Metal: metallic=1.0, roughness=0.1-0.4 | Wood: metallic=0, roughness=0.6-0.8
  Glass: transmission=0.9+, ior=1.45, roughness=0 | Plastic: metallic=0, roughness=0.3-0.5
  Stone: metallic=0, roughness=0.7-0.9 | Fabric: metallic=0, roughness=0.8-1.0
  Leather: metallic=0, roughness=0.5-0.7 | Emission: emission_strength=2-20
- Add surface variation: noise texture → bump node for realism.

PHASE 5 — QUALITY SELF-CHECK
- Face count appropriate? (Props <2k, Characters <30k, Buildings <10k)
- All normals outward? Did you call normals_make_consistent?
- No loose vertices? Did you call remove_doubles?
- Each part named descriptively in English?
- Symmetric? Used Mirror modifier?
- Organic parts have smooth shading?
- Transforms applied (rotation=1, scale=1)?

===== OUTPUT FORMAT =====
Line 1: # THINK: [concise summary: what parts, how many faces, materials planned]
Lines 2+: Pure Python code. No markdown. No explanation after code.

===== MODELING TECHNIQUES (use these, don't just stack primitives) =====

--- TECHNIQUE 1: EXTRUDE MODELING (best for hard-surface) ---
Start with a cube, enter edit mode, extrude faces to shape the object.
```python
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0.5))
obj = bpy.context.active_object; obj.name = "Part"
bpy.ops.object.mode_set(mode='EDIT')
import bmesh; bm = bmesh.from_edit_mesh(obj.data)
# Select top face, extrude upward
bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value":(0,0,0.3)})
# Scale the extruded face
bpy.ops.transform.resize(value=(0.8, 0.8, 1.0))
# Bevel edges for realism
bpy.ops.mesh.bevel(offset=0.02, segments=3)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.mesh.remove_doubles(threshold=0.001)
bmesh.update_edit_mesh(obj.data)
bpy.ops.object.mode_set(mode='OBJECT')
```

--- TECHNIQUE 2: SPIN/LATHE (best for vases, goblets, columns, bottles) ---
Create a profile curve, then spin it around an axis.
```python
# Create profile vertices manually
bpy.ops.object.mode_set(mode='EDIT')
import bmesh; bm = bmesh.from_edit_mesh(obj.data)
# Add profile vertices (half cross-section)
verts = []
for x, z in [(0.05,0), (0.15,0.02), (0.18,0.1), (0.15,0.2), (0.08,0.22), (0.06,0.25)]:
    verts.append(bm.verts.new((x, 0, z)))
# Spin around Z axis
bmesh.ops.spin(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:],
    axis=(0,0,1), cent=(0,0,0), steps=32, angle=2*math.pi,
    use_duplicate=False, use_normal_flip=False)
bmesh.update_edit_mesh(obj.data)
bpy.ops.object.mode_set(mode='OBJECT')
```

--- TECHNIQUE 3: SUBDIVISION SURFACE (best for organic shapes) ---
Start with low-poly cage, add subdivision modifier for smooth result.
```python
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0.5))
obj = bpy.context.active_object
# Add edge loops for control
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.loopcut_slide(MESH_OT_loopcut={"number_cuts":3})
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
mod = obj.modifiers.new("Subdiv", 'SUBSURF')
mod.levels = 2; mod.render_levels = 3
bpy.ops.object.shade_smooth()
```

--- TECHNIQUE 4: BOOLEAN OPERATIONS (best for complex cutouts) ---
Use one mesh to cut/carve another.
```python
# Create the cutter
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.5, location=(0,0,0.5))
cutter = bpy.context.active_object; cutter.name = "Cutter"
# Add boolean to main object
mod = main_obj.modifiers.new("BoolCut", 'BOOLEAN')
mod.operation = 'DIFFERENCE'; mod.object = cutter
cutter.hide_set(True)  # Hide cutter
```

--- TECHNIQUE 5: CURVE + BEVEL (best for pipes, trim, decorative elements) ---
```python
curve_data = bpy.data.curves.new('PipeCurve', 'CURVE')
curve_data.dimensions = '3D'; curve_data.bevel_depth = 0.01
spline = curve_data.splines.new('BEZIER')
spline.bezier_points.add(2)
spline.bezier_points[0].co = (0,0,0); spline.bezier_points[0].handle_right = (0.2,0,0)
spline.bezier_points[1].co = (0.5,0,0.3); spline.bezier_points[1].handle_right = (0.7,0,0.3)
spline.bezier_points[2].co = (1,0,0); spline.bezier_points[2].handle_right = (1.2,0,0)
curve_obj = bpy.data.objects.new('Pipe', curve_data)
bpy.context.collection.objects.link(curve_obj)
```

--- TECHNIQUE 6: ARRAY + CURVE (best for chains, fences, repeating patterns) ---
```python
# Create one link
bpy.ops.mesh.primitive_torus_add(major_radius=0.02, minor_radius=0.005)
link = bpy.context.active_object
# Array along curve
mod = link.modifiers.new("Array", 'ARRAY')
mod.count = 20; mod.use_relative_offset = False
mod.use_constant_offset = True; mod.constant_offset_displace = (0.04, 0, 0)
# Curve modifier to follow path
mod2 = link.modifiers.new("Curve", 'CURVE')
mod2.object = curve_path
```

--- TECHNIQUE 7: PROPORTIONAL EDITING (for organic deformation) ---
```python
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')
# Select a vertex
bm.verts[42].select = True
bpy.ops.transform.translate(value=(0, 0, 0.1), use_proportional_edit=True,
    proportional_edit_falloff='SMOOTH', proportional_size=0.3)
```

--- TECHNIQUE 8: WIREFRAME + SKIN (for tree branches, coral, abstract shapes) ---
```python
bpy.ops.mesh.primitive_plane_add()
obj = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.delete(type='VERT')
# Add vertices manually
import bmesh; bm = bmesh.from_edit_mesh(obj.data)
v0 = bm.verts.new((0,0,0)); v1 = bm.verts.new((0,0,1)); v2 = bm.verts.new((0.3,0,1.3))
bm.edges.new((v0,v1)); bm.edges.new((v1,v2))
bmesh.update_edit_mesh(obj.data)
bpy.ops.object.mode_set(mode='OBJECT')
mod = obj.modifiers.new("Skin", 'SKIN')
mod2 = obj.modifiers.new("Subdiv", 'SUBSURF')
mod2.levels = 2
```

===== MATERIAL NODE PATTERNS =====

# Pattern A: Simple PBR
mat = bpy.data.materials.new("Name"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs['Base Color'].default_value = (R,G,B,1)
p.inputs['Roughness'].default_value = 0.5
p.inputs['Metallic'].default_value = 0.0

# Pattern B: PBR with bump/normal detail
mat = bpy.data.materials.new("Name"); mat.use_nodes = True
nodes = mat.node_tree.nodes; links = mat.node_tree.links
p = nodes["Principled BSDF"]
noise = nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 50
bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.3
links.new(noise.outputs['Fac'], bump.inputs['Height'])
links.new(bump.outputs['Normal'], p.inputs['Normal'])

# Pattern C: Two-tone gradient
mat = bpy.data.materials.new("Name"); mat.use_nodes = True
nodes = mat.node_tree.nodes; links = mat.node_tree.links
p = nodes["Principled BSDF"]
grad = nodes.new('ShaderNodeTexGradient'); grad.gradient_type = 'LINEAR'
ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (R1,G1,B1,1)
ramp.color_ramp.elements[1].color = (R2,G2,B2,1)
links.new(grad.outputs['Color'], ramp.inputs['Fac'])
links.new(ramp.outputs['Color'], p.inputs['Base Color'])

# Pattern D: Glass with tint
mat = bpy.data.materials.new("Glass"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs['Base Color'].default_value = (0.9,0.95,1.0,1)
p.inputs['Roughness'].default_value = 0.0
try: p.inputs['Transmission Weight'].default_value = 0.95  # 4.x
except KeyError:
    try: p.inputs['Transmission'].default_value = 0.95  # 3.x
    except KeyError: pass
try: p.inputs['IOR'].default_value = 1.45
except KeyError: pass

# Blender 3.x/4.x compatibility wrapper
def set_principled(node, key3, key4, value):
    try: node.inputs[key4].default_value = value  # Try 4.x name first
    except KeyError:
        try: node.inputs[key3].default_value = value  # Fallback to 3.x
        except KeyError: pass

===== MODIFIER PATTERNS =====
# Bevel for hard edges
mod = obj.modifiers.new("Bevel", 'BEVEL'); mod.width = 0.01; mod.segments = 2; mod.limit_method = 'ANGLE'; mod.angle_limit = 1.047

# Subdivision for organic
mod = obj.modifiers.new("Subdiv", 'SUBSURF'); mod.levels = 2; mod.render_levels = 3

# Mirror for symmetry
mod = obj.modifiers.new("Mirror", 'MIRROR'); mod.use_axis = (True,False,False); mod.use_clip = True; mod.merge_threshold = 0.001

# Solidify for shells
mod = obj.modifiers.new("Solidify", 'SOLIDIFY'); mod.thickness = 0.02; mod.offset = -1

# Array for repetition
mod = obj.modifiers.new("Array", 'ARRAY'); mod.count = 8; mod.relative_offset_displace = (1.5,0,0)

# Boolean for cutouts
mod = obj.modifiers.new("Bool", 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = cutter_obj

===== REAL-WORLD DIMENSION REFERENCE =====
Furniture: seat 0.45m, table 0.75m, desk 0.74m, bed 0.45m high, 2.0x0.9m
Architecture: door 2.0x0.9m, window 1.2x1.0m, wall 0.2m thick, floor 0.15m
Character: total 1.75m, head 0.22m, shoulder width 0.45m, arm 0.65m, leg 0.85m
Weapons: sword 1.1m, dagger 0.35m, shield 0.6m dia, bow 1.5m
Vehicles: car 4.5x1.8x1.5m, door 0.9m, wheel 0.35m dia
Containers: barrel 0.6x0.4m, crate 0.4m, bottle 0.25m, cup 0.08m dia

===== RULES =====
1. Import ONLY: bpy, bmesh, math, mathutils, random. NEVER import os/subprocess/sys/http.
2. Name every object descriptively in English: "Chair_BackRest", "Sword_Guard", "House_Roof"
3. Use Principled BSDF for ALL materials (game-engine compatible)
4. Colors as RGBA 0-1: (0.8, 0.2, 0.1, 1.0)
5. Wrap each major part creation in try/except
6. End with print() showing: parts created, total faces, materials used
7. Smooth shading for organic shapes. Flat for hard-surface.
8. ALWAYS apply transforms: bpy.ops.object.transform_apply(rotation=True, scale=True)
9. ALWAYS recalculate normals: bpy.ops.mesh.normals_make_consistent(inside=False)
10. ALWAYS remove doubles: bpy.ops.mesh.remove_doubles(threshold=0.001)
11. Use Mirror for any symmetric geometry
12. Use Bevel modifier on hard-surface edges (width=0.01, segments=2)
13. Add noise→bump to materials for surface detail
14. Do NOT just stack basic primitives. Use extrude, spin, boolean, subdivision, curves.
"""

# --- Localization ---
I18N = {
    "en": {
        "panel_title": "AI Modeling Assistant",
        "send": "Send to AI",
        "prompt_label": "Describe what to create:",
        "settings": "API Settings",
        "api_url": "API URL",
        "api_key": "API Key",
        "model": "Model Name",
        "temperature": "Temperature",
        "max_tokens": "Max Tokens",
        "api_preset": "Preset",
        "custom": "Custom",
        "execute": "Execute Code",
        "fix": "Auto Fix",
        "clear_history": "Clear History",
        "history": "Conversation History",
        "materials": "Material Library",
        "templates": "Templates",
        "modifiers": "Modifier Presets",
        "lod": "LOD Generator",
        "mesh_analysis": "Mesh Analysis",
        "quality_check": "Quality Check",
        "rigging": "Rigging",
        "uv_tools": "UV Tools",
        "bake": "Bake Tools",
        "animation": "Animation",
        "procedural": "Procedural Gen",
        "batch": "Batch Ops",
        "scene": "Scene Assembly",
        "versions": "Version Control",
        "select": "Smart Select",
        "cleanup": "Cleanup Tools",
        "export": "Engine Export",
        "assets": "Asset Manager",
        "generating": "Generating...",
        "executing": "Executing...",
        "success": "Success",
        "error": "Error",
        "cost": "Cost",
        "tokens": "Tokens",
        "auto_fix_attempts": "Auto-fix attempts",
        "scene_context": "Scene Context",
        "security_blocked": "Code blocked by security check",
        "refine": "AI Refine",
        "multi_pass": "Multi-Pass Gen",
        "post_process": "Post-Process",
        "mesh_ops": "Mesh Editing",
        "ai_workflow": "AI Workflow",
    },
    "zh": {
        "panel_title": "AI 建模助手",
        "send": "发送给AI",
        "prompt_label": "描述要创建的内容：",
        "settings": "API 设置",
        "api_url": "API 地址",
        "api_key": "API 密钥",
        "model": "模型名称",
        "temperature": "温度",
        "max_tokens": "最大Token",
        "api_preset": "预设",
        "custom": "自定义",
        "execute": "执行代码",
        "fix": "自动修复",
        "clear_history": "清除历史",
        "history": "对话历史",
        "materials": "材质库",
        "templates": "模板系统",
        "modifiers": "修改器预设",
        "lod": "LOD 生成",
        "mesh_analysis": "网格分析",
        "quality_check": "质检工具",
        "rigging": "骨骼绑定",
        "uv_tools": "UV 工具",
        "bake": "烘焙工具",
        "animation": "动画系统",
        "procedural": "程序化生成",
        "batch": "批量操作",
        "scene": "场景组装",
        "versions": "版本管理",
        "select": "智能选择",
        "cleanup": "清理工具",
        "export": "引擎导出",
        "assets": "资产管理",
        "generating": "生成中...",
        "executing": "执行中...",
        "success": "成功",
        "error": "错误",
        "cost": "费用",
        "tokens": "Token数",
        "auto_fix_attempts": "自动修复次数",
        "scene_context": "场景上下文",
        "security_blocked": "代码被安全检查阻止",
        "refine": "AI 精修",
        "multi_pass": "多阶段生成",
        "post_process": "后处理",
        "mesh_ops": "网格编辑",
        "ai_workflow": "AI 工作流",
    },
}

def t(key: str) -> str:
    """Get localized string based on addon preferences."""
    lang = "zh" if getattr(get_prefs(), "language", "en") == "zh" else "en"
    return I18N.get(lang, I18N["en"]).get(key, key)


# --- Security: Dangerous patterns & allowed builtins ---
DANGEROUS_PATTERNS = [
    r'\bimport\s+os\b', r'\bimport\s+subprocess\b', r'\bimport\s+sys\b',
    r'\bimport\s+shutil\b', r'\bimport\s+socket\b', r'\bimport\s+http\b',
    r'\bfrom\s+os\b', r'\bfrom\s+subprocess\b', r'\bfrom\s+sys\b',
    r'\bfrom\s+shutil\b', r'\b__import__\b', r'\beval\s*\(',
    r'\bexec\s*\(', r'\bcompile\s*\(', r'\bopen\s*\(',
    r'\bos\.', r'\bpathlib\b', r'\bglob\b',
    r'\brequests\b', r'\burllib\b', r'\bhttp\.client\b',
    r'\bctypes\b', r'\bimportlib\b', r'\bgetattr\s*\(',
    r'\bsetattr\s*\(', r'\bdelattr\s*\(',
    r'\b__builtins__\b', r'\b__globals__\b', r'\b__locals__\b',
    r'\binput\s*\(', r'\braw_input\s*\(',
]
DANGEROUS_RE = [re.compile(p) for p in DANGEROUS_PATTERNS]

# Whitelisted builtins for sandboxed execution
ALLOWED_BUILTINS = {
    'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter',
    'float', 'frozenset', 'getattr', 'hasattr', 'hash', 'hex', 'id',
    'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map',
    'max', 'min', 'next', 'object', 'oct', 'ord', 'pow', 'print',
    'property', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
    'sorted', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip',
    'True', 'False', 'None', 'NotImplemented', 'Ellipsis',
    '__name__', '__doc__', '__import__',
}

# --- Quick Build Commands (instant 3D creation, no API needed) ---
QUICK_BUILDS: Dict[str, Dict[str, Any]] = {
    "human_male": {
        "label_en": "🧑 Human Male",
        "label_zh": "🧑 人类男性",
        "code": '''import bpy, math
objs = []
# Head
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, segments=32, ring_count=16, location=(0, 0, 1.65))
head = bpy.context.active_object; head.name = "Head"; objs.append(head)
# Body
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.2))
body = bpy.context.active_object; body.name = "Body"
body.scale = (0.2, 0.12, 0.35); bpy.ops.object.transform_apply(scale=True); objs.append(body)
# Arms
for side, sx in [("R", 0.25), ("L", -0.25)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=0.55, location=(sx, 0, 1.3))
    a = bpy.context.active_object; a.name = f"Arm_{side}"; objs.append(a)
# Legs
for side, sx in [("R", 0.08), ("L", -0.08)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.7, location=(sx, 0, 0.55))
    l = bpy.context.active_object; l.name = f"Leg_{side}"; objs.append(l)
# Material
mat = bpy.data.materials.new(name="Skin"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.961, 0.871, 0.702, 1)
p.inputs["Roughness"].default_value = 0.6
try: p.inputs["Subsurface Weight"].default_value = 0.1
except KeyError:
    try: p.inputs["Subsurface"].default_value = 0.1
    except KeyError: pass
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created human male: {len(objs)} parts")
''',
    },
    "sword": {
        "label_en": "⚔ Sword",
        "label_zh": "⚔ 长剑",
        "code": '''import bpy
objs = []
# Blade
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.55))
blade = bpy.context.active_object; blade.name = "Blade"
blade.scale = (0.03, 0.005, 0.5); bpy.ops.object.transform_apply(scale=True); objs.append(blade)
# Guard
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.28))
guard = bpy.context.active_object; guard.name = "Guard"
guard.scale = (0.12, 0.02, 0.015); bpy.ops.object.transform_apply(scale=True); objs.append(guard)
# Grip
bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.18, location=(0, 0, 0.18))
grip = bpy.context.active_object; grip.name = "Grip"; objs.append(grip)
# Pommel
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.02, location=(0, 0, 0.08))
pommel = bpy.context.active_object; pommel.name = "Pommel"; objs.append(pommel)
# Material
mat = bpy.data.materials.new(name="SwordMetal"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.753, 0.753, 0.753, 1)
p.inputs["Metallic"].default_value = 1.0; p.inputs["Roughness"].default_value = 0.2
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created sword: {len(objs)} parts")
''',
    },
    "shield": {
        "label_en": "🛡 Shield",
        "label_zh": "🛡 盾牌",
        "code": '''import bpy
objs = []
bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.04, vertices=32, location=(0, 0, 1.0))
shield = bpy.context.active_object; shield.name = "Shield_Face"; objs.append(shield)
bpy.ops.mesh.primitive_torus_add(major_radius=0.35, minor_radius=0.02, location=(0, 0, 1.0))
rim = bpy.context.active_object; rim.name = "Shield_Rim"; objs.append(rim)
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.08, location=(0, 0, 1.0))
boss = bpy.context.active_object; boss.name = "Shield_Boss"; objs.append(boss)
mat_metal = bpy.data.materials.new(name="ShieldMetal"); mat_metal.use_nodes = True
p = mat_metal.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.6, 0.6, 0.65, 1)
p.inputs["Metallic"].default_value = 1.0; p.inputs["Roughness"].default_value = 0.3
mat_wood = bpy.data.materials.new(name="ShieldWood"); mat_wood.use_nodes = True
p2 = mat_wood.node_tree.nodes["Principled BSDF"]
p2.inputs["Base Color"].default_value = (0.45, 0.3, 0.15, 1); p2.inputs["Roughness"].default_value = 0.7
shield.data.materials.append(mat_wood)
for o in [rim, boss]: o.data.materials.append(mat_metal)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created shield: {len(objs)} parts")
''',
    },
    "potion": {
        "label_en": "💊 Potion",
        "label_zh": "💊 药水瓶",
        "code": '''import bpy
objs = []
# Bottle body
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, segments=32, ring_count=16, location=(0, 0, 0.06))
bottle = bpy.context.active_object; bottle.name = "Bottle_Body"
bottle.scale = (1, 1, 1.5); bpy.ops.object.transform_apply(scale=True); objs.append(bottle)
# Neck
bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.03, location=(0, 0, 0.13))
neck = bpy.context.active_object; neck.name = "Bottle_Neck"; objs.append(neck)
# Cork
bpy.ops.mesh.primitive_cylinder_add(radius=0.018, depth=0.015, location=(0, 0, 0.155))
cork = bpy.context.active_object; cork.name = "Cork"; objs.append(cork)
# Glass material
mat_glass = bpy.data.materials.new(name="PotionGlass"); mat_glass.use_nodes = True
p = mat_glass.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.8, 0.1, 0.1, 1)
p.inputs["Roughness"].default_value = 0.05
try:
    p.inputs["Transmission Weight"].default_value = 0.9
except KeyError:
    try:
        p.inputs["Transmission"].default_value = 0.9
    except KeyError: pass
try: p.inputs["IOR"].default_value = 1.45
except KeyError: pass
bottle.data.materials.append(mat_glass)
# Cork material
mat_cork = bpy.data.materials.new(name="Cork"); mat_cork.use_nodes = True
p2 = mat_cork.node_tree.nodes["Principled BSDF"]
p2.inputs["Base Color"].default_value = (0.6, 0.4, 0.2, 1); p2.inputs["Roughness"].default_value = 0.8
cork.data.materials.append(mat_cork)
neck.data.materials.append(mat_glass)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created potion: {len(objs)} parts")
''',
    },
    "table": {
        "label_en": "🪑 Table",
        "label_zh": "🪑 桌子",
        "code": '''import bpy
objs = []
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.75))
top = bpy.context.active_object; top.name = "Table_Top"
top.scale = (0.6, 0.4, 0.03); bpy.ops.object.transform_apply(scale=True); objs.append(top)
for sx, sy in [(0.5, 0.3), (0.5, -0.3), (-0.5, 0.3), (-0.5, -0.3)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.73, location=(sx, sy, 0.365))
    leg = bpy.context.active_object; leg.name = "Table_Leg"; objs.append(leg)
mat = bpy.data.materials.new(name="TableWood"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.45, 0.3, 0.15, 1); p.inputs["Roughness"].default_value = 0.65
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created table: {len(objs)} parts")
''',
    },
    "chair": {
        "label_en": "💺 Chair",
        "label_zh": "💺 椅子",
        "code": '''import bpy
objs = []
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.45))
seat = bpy.context.active_object; seat.name = "Chair_Seat"
seat.scale = (0.25, 0.25, 0.02); bpy.ops.object.transform_apply(scale=True); objs.append(seat)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.23, 0.8))
back = bpy.context.active_object; back.name = "Chair_Back"
back.scale = (0.23, 0.02, 0.35); bpy.ops.object.transform_apply(scale=True); objs.append(back)
for sx, sy in [(0.2, 0.2), (0.2, -0.2), (-0.2, 0.2), (-0.2, -0.2)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.44, location=(sx, sy, 0.22))
    leg = bpy.context.active_object; leg.name = "Chair_Leg"; objs.append(leg)
mat = bpy.data.materials.new(name="ChairWood"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.5, 0.35, 0.18, 1); p.inputs["Roughness"].default_value = 0.65
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created chair: {len(objs)} parts")
''',
    },
    "house": {
        "label_en": "🏠 House",
        "label_zh": "🏠 房屋",
        "code": '''import bpy
objs = []
# Walls
walls_data = [(4,0.3,3,0,-2,1.5),(4,0.3,3,0,2,1.5),(0.3,4,3,-2,0,1.5),(0.3,4,3,2,0,1.5)]
for i,(sx,sy,sz,x,y,z) in enumerate(walls_data):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x,y,z))
    w = bpy.context.active_object; w.name = f"Wall_{i}"
    w.scale = (sx/2,sy/2,sz/2); bpy.ops.object.transform_apply(scale=True); objs.append(w)
# Roof
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,3.2))
roof = bpy.context.active_object; roof.name = "Roof"
roof.scale = (2.2,2.2,0.15); bpy.ops.object.transform_apply(scale=True); objs.append(roof)
# Floor
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0))
floor = bpy.context.active_object; floor.name = "Floor"
floor.scale = (2,2,0.05); bpy.ops.object.transform_apply(scale=True); objs.append(floor)
mat = bpy.data.materials.new(name="WallStone"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.98,0.92,0.84,1); p.inputs["Roughness"].default_value = 0.5
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created house: {len(objs)} parts")
''',
    },
    "dragon": {
        "label_en": "🐉 Dragon",
        "label_zh": "🐉 火龙幼崽",
        "code": '''import bpy, math
objs = []
# Body
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, segments=32, ring_count=16, location=(0, 0, 0.7))
body = bpy.context.active_object; body.name = "Dragon_Body"
body.scale = (1.3, 0.6, 0.7); bpy.ops.object.transform_apply(scale=True); objs.append(body)
# Head
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, segments=32, ring_count=16, location=(0.6, 0, 0.9))
head = bpy.context.active_object; head.name = "Dragon_Head"
head.scale = (1.2, 0.8, 0.9); bpy.ops.object.transform_apply(scale=True); objs.append(head)
# Snout
bpy.ops.mesh.primitive_cone_add(radius1=0.08, radius2=0.02, depth=0.3, location=(0.85, 0, 0.85))
snout = bpy.context.active_object; snout.name = "Dragon_Snout"
snout.rotation_euler = (0, math.radians(90), 0); objs.append(snout)
# Wings
for side, sy in [("R", 0.6), ("L", -0.6)]:
    bpy.ops.mesh.primitive_plane_add(size=0.8, location=(0, sy, 1.0))
    wing = bpy.context.active_object; wing.name = f"Dragon_Wing_{side}"
    wing.scale = (1.5, 1, 1); wing.rotation_euler = (0, 0, math.radians(30 if sy > 0 else -30))
    bpy.ops.object.transform_apply(scale=True, rotation=True); objs.append(wing)
# Legs
for i, (x, y) in enumerate([(0.3, 0.2), (0.3, -0.2), (-0.3, 0.2), (-0.3, -0.2)]):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.4, location=(x, y, 0.2))
    leg = bpy.context.active_object; leg.name = f"Dragon_Leg_{i}"; objs.append(leg)
# Tail
bpy.ops.mesh.primitive_cone_add(radius1=0.1, radius2=0.01, depth=0.8, location=(-0.7, 0, 0.6))
tail = bpy.context.active_object; tail.name = "Dragon_Tail"
tail.rotation_euler = (0, math.radians(-70), 0); objs.append(tail)
# Horns
for sy in [0.06, -0.06]:
    bpy.ops.mesh.primitive_cone_add(radius1=0.02, radius2=0.005, depth=0.15, location=(0.55, sy, 1.1))
    horn = bpy.context.active_object; horn.name = "Dragon_Horn"; objs.append(horn)
# Material
mat = bpy.data.materials.new(name="DragonScale"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.8, 0.25, 0.05, 1)
p.inputs["Roughness"].default_value = 0.4; p.inputs["Metallic"].default_value = 0.3
# Emissive eyes
mat_eye = bpy.data.materials.new(name="DragonEye"); mat_eye.use_nodes = True
pe = mat_eye.node_tree.nodes["Principled BSDF"]
pe.inputs["Base Color"].default_value = (1, 0.2, 0, 1)
try:
    pe.inputs["Emission Color"].default_value = (1, 0.3, 0, 1)
    pe.inputs["Emission Strength"].default_value = 10.0
except KeyError:
    try:
        pe.inputs["Emission"].default_value = (1, 0.3, 0, 1)
        pe.inputs["Emission Strength"].default_value = 10.0
    except KeyError: pass
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created dragon: {len(objs)} parts")
''',
    },
    "crystal": {
        "label_en": "💎 Crystal",
        "label_zh": "💎 水晶",
        "code": '''import bpy, math, random
random.seed(42)
objs = []
for i in range(5):
    h = random.uniform(0.2, 0.6)
    angle = random.uniform(0, math.radians(25))
    bpy.ops.mesh.primitive_cone_add(radius1=0.05, radius2=0.005, depth=h,
        location=(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), h/2))
    c = bpy.context.active_object; c.name = f"Crystal_{i}"
    c.rotation_euler = (angle * random.uniform(-1,1), angle * random.uniform(-1,1), 0)
    objs.append(c)
mat = bpy.data.materials.new(name="Crystal"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.2, 0.5, 0.9, 1)
p.inputs["Roughness"].default_value = 0.05; p.inputs["Metallic"].default_value = 0.1
try:
    p.inputs["Transmission Weight"].default_value = 0.8
except KeyError:
    try:
        p.inputs["Transmission"].default_value = 0.8
    except KeyError: pass
try: p.inputs["IOR"].default_value = 2.0
except KeyError: pass
try:
    p.inputs["Emission Color"].default_value = (0.2, 0.5, 1.0, 1)
    p.inputs["Emission Strength"].default_value = 3.0
except KeyError:
    try:
        p.inputs["Emission"].default_value = (0.2, 0.5, 1.0, 1)
        p.inputs["Emission Strength"].default_value = 3.0
    except KeyError: pass
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created crystal cluster: {len(objs)} crystals")
''',
    },
    "tree": {
        "label_en": "🌳 Tree",
        "label_zh": "🌳 树木",
        "code": '''import bpy
objs = []
# Trunk
bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=1.5, location=(0, 0, 0.75))
trunk = bpy.context.active_object; trunk.name = "Tree_Trunk"; objs.append(trunk)
# Crown (3 spheres)
for z, r in [(1.8, 0.5), (2.2, 0.4), (2.5, 0.25)]:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=(0, 0, z))
    crown = bpy.context.active_object; crown.name = "Tree_Crown"; objs.append(crown)
# Materials
mat_bark = bpy.data.materials.new(name="Bark"); mat_bark.use_nodes = True
p = mat_bark.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.35, 0.2, 0.1, 1); p.inputs["Roughness"].default_value = 0.85
mat_leaf = bpy.data.materials.new(name="Leaves"); mat_leaf.use_nodes = True
p2 = mat_leaf.node_tree.nodes["Principled BSDF"]
p2.inputs["Base Color"].default_value = (0.1, 0.5, 0.1, 1); p2.inputs["Roughness"].default_value = 0.7
trunk.data.materials.append(mat_bark)
for o in objs[1:]: o.data.materials.append(mat_leaf)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created tree: {len(objs)} parts")
''',
    },
    "mushroom": {
        "label_en": "🍄 Mushroom",
        "label_zh": "🍄 蘑菇",
        "code": '''import bpy, random
random.seed(42)
objs = []
for i in range(3):
    h = random.uniform(0.08, 0.2)
    x = random.uniform(-0.3, 0.3)
    y = random.uniform(-0.3, 0.3)
    # Stem
    bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=h, location=(x, y, h/2))
    stem = bpy.context.active_object; stem.name = f"Mushroom_Stem_{i}"; objs.append(stem)
    # Cap
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, segments=16, ring_count=8, location=(x, y, h))
    cap = bpy.context.active_object; cap.name = f"Mushroom_Cap_{i}"
    cap.scale = (1.2, 1.2, 0.6); bpy.ops.object.transform_apply(scale=True); objs.append(cap)
mat_stem = bpy.data.materials.new(name="MushroomStem"); mat_stem.use_nodes = True
p = mat_stem.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.9, 0.85, 0.7, 1); p.inputs["Roughness"].default_value = 0.8
mat_cap = bpy.data.materials.new(name="MushroomCap"); mat_cap.use_nodes = True
p2 = mat_cap.node_tree.nodes["Principled BSDF"]
p2.inputs["Base Color"].default_value = (0.2, 0.6, 0.9, 1); p2.inputs["Roughness"].default_value = 0.6
try:
    p2.inputs["Emission Color"].default_value = (0.3, 0.7, 1.0, 1)
    p2.inputs["Emission Strength"].default_value = 5.0
except KeyError:
    try:
        p2.inputs["Emission"].default_value = (0.3, 0.7, 1.0, 1)
        p2.inputs["Emission Strength"].default_value = 5.0
    except KeyError: pass
for o in objs:
    if "Stem" in o.name: o.data.materials.append(mat_stem)
    else: o.data.materials.append(mat_cap)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created mushroom cluster: {len(objs)} parts")
''',
    },
    "skeleton": {
        "label_en": "💀 Skeleton",
        "label_zh": "💀 骷髅战士",
        "code": '''import bpy
objs = []
# Skull
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, segments=32, ring_count=16, location=(0, 0, 1.65))
skull = bpy.context.active_object; skull.name = "Skull"; objs.append(skull)
# Spine
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.5, location=(0, 0, 1.3))
spine = bpy.context.active_object; spine.name = "Spine"; objs.append(spine)
# Ribcage
for i in range(4):
    bpy.ops.mesh.primitive_torus_add(major_radius=0.12, minor_radius=0.01,
        location=(0, 0, 1.1 - i*0.08))
    rib = bpy.context.active_object; rib.name = f"Rib_{i}"
    rib.scale = (1, 0.5, 1); bpy.ops.object.transform_apply(scale=True); objs.append(rib)
# Arms
for side, sx in [("R", 0.15), ("L", -0.15)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.5, location=(sx, 0, 1.15))
    arm = bpy.context.active_object; arm.name = f"Arm_{side}"; objs.append(arm)
# Legs
for side, sx in [("R", 0.07), ("L", -0.07)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.65, location=(sx, 0, 0.5))
    leg = bpy.context.active_object; leg.name = f"Leg_{side}"; objs.append(leg)
mat = bpy.data.materials.new(name="Bone"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.85, 0.82, 0.75, 1); p.inputs["Roughness"].default_value = 0.7
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created skeleton: {len(objs)} parts")
''',
    },
    "crown": {
        "label_en": "👑 Crown",
        "label_zh": "👑 王冠",
        "code": '''import bpy, math
objs = []
# Base ring
bpy.ops.mesh.primitive_torus_add(major_radius=0.1, minor_radius=0.015, location=(0, 0, 1.7))
base = bpy.context.active_object; base.name = "Crown_Base"; objs.append(base)
# Points
for i in range(7):
    angle = i * (2 * math.pi / 7)
    x = 0.1 * math.cos(angle)
    y = 0.1 * math.sin(angle)
    bpy.ops.mesh.primitive_cone_add(radius1=0.02, radius2=0.003, depth=0.08,
        location=(x, y, 1.78))
    point = bpy.context.active_object; point.name = f"Crown_Point_{i}"; objs.append(point)
# Gems
for i in range(7):
    angle = i * (2 * math.pi / 7)
    x = 0.1 * math.cos(angle)
    y = 0.1 * math.sin(angle)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.008, location=(x, y, 1.72))
    gem = bpy.context.active_object; gem.name = f"Crown_Gem_{i}"; objs.append(gem)
mat_gold = bpy.data.materials.new(name="CrownGold"); mat_gold.use_nodes = True
p = mat_gold.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (1.0, 0.843, 0.0, 1)
p.inputs["Metallic"].default_value = 1.0; p.inputs["Roughness"].default_value = 0.15
mat_ruby = bpy.data.materials.new(name="CrownRuby"); mat_ruby.use_nodes = True
p2 = mat_ruby.node_tree.nodes["Principled BSDF"]
p2.inputs["Base Color"].default_value = (0.8, 0.05, 0.1, 1)
p2.inputs["Roughness"].default_value = 0.1
try:
    p2.inputs["Emission Color"].default_value = (0.5, 0.0, 0.05, 1)
    p2.inputs["Emission Strength"].default_value = 3.0
except KeyError:
    try:
        p2.inputs["Emission"].default_value = (0.5, 0.0, 0.05, 1)
        p2.inputs["Emission Strength"].default_value = 3.0
    except KeyError: pass
for o in objs:
    if "Gem" in o.name: o.data.materials.append(mat_ruby)
    else: o.data.materials.append(mat_gold)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created crown: {len(objs)} parts")
''',
    },
    "archway": {
        "label_en": "🏛 Archway",
        "label_zh": "🏛 拱门",
        "code": '''import bpy, math
objs = []
# Left pillar
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.6, 0, 1.2))
lp = bpy.context.active_object; lp.name = "Pillar_L"
lp.scale = (0.2, 0.2, 1.2); bpy.ops.object.transform_apply(scale=True); objs.append(lp)
# Right pillar
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.6, 0, 1.2))
rp = bpy.context.active_object; rp.name = "Pillar_R"
rp.scale = (0.2, 0.2, 1.2); bpy.ops.object.transform_apply(scale=True); objs.append(rp)
# Arch (half torus)
bpy.ops.mesh.primitive_torus_add(major_radius=0.6, minor_radius=0.12,
    location=(0, 0, 2.4))
arch = bpy.context.active_object; arch.name = "Arch"
arch.scale = (1, 0.3, 1); bpy.ops.object.transform_apply(scale=True); objs.append(arch)
mat = bpy.data.materials.new(name="ArchStone"); mat.use_nodes = True
p = mat.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.7, 0.68, 0.65, 1); p.inputs["Roughness"].default_value = 0.7
for o in objs: o.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created archway: {len(objs)} parts")
''',
    },
    "chest": {
        "label_en": "📦 Chest",
        "label_zh": "📦 宝箱",
        "code": '''import bpy, math
objs = []
# Box body
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.15))
box = bpy.context.active_object; box.name = "Chest_Body"
box.scale = (0.3, 0.2, 0.15); bpy.ops.object.transform_apply(scale=True); objs.append(box)
# Lid (rounded top)
bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=0.6, vertices=32,
    location=(0, 0, 0.32), rotation=(math.pi/2, 0, 0))
lid = bpy.context.active_object; lid.name = "Chest_Lid"
lid.scale = (1, 1, 0.4); bpy.ops.object.transform_apply(scale=True); objs.append(lid)
# Lock
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.2, 0.2))
lock = bpy.context.active_object; lock.name = "Chest_Lock"
lock.scale = (0.03, 0.02, 0.04); bpy.ops.object.transform_apply(scale=True); objs.append(lock)
mat_wood = bpy.data.materials.new(name="ChestWood"); mat_wood.use_nodes = True
p = mat_wood.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.45, 0.28, 0.12, 1); p.inputs["Roughness"].default_value = 0.7
mat_metal = bpy.data.materials.new(name="ChestMetal"); mat_metal.use_nodes = True
p2 = mat_metal.node_tree.nodes["Principled BSDF"]
p2.inputs["Base Color"].default_value = (0.7, 0.65, 0.3, 1)
p2.inputs["Metallic"].default_value = 1.0; p2.inputs["Roughness"].default_value = 0.3
for o in [box, lid]: o.data.materials.append(mat_wood)
lock.data.materials.append(mat_metal)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created chest: {len(objs)} parts")
''',
    },
    "torch": {
        "label_en": "🔥 Torch",
        "label_zh": "🔥 火把",
        "code": '''import bpy
objs = []
# Handle
bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.4, location=(0, 0, 0.2))
handle = bpy.context.active_object; handle.name = "Torch_Handle"; objs.append(handle)
# Head (wrapped top)
bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.08, location=(0, 0, 0.42))
head = bpy.context.active_object; head.name = "Torch_Head"; objs.append(head)
# Flame (emissive sphere)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, segments=16, ring_count=8, location=(0, 0, 0.5))
flame = bpy.context.active_object; flame.name = "Torch_Flame"
flame.scale = (0.8, 0.8, 1.5); bpy.ops.object.transform_apply(scale=True); objs.append(flame)
mat_wood = bpy.data.materials.new(name="TorchWood"); mat_wood.use_nodes = True
p = mat_wood.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.4, 0.25, 0.1, 1); p.inputs["Roughness"].default_value = 0.8
mat_flame = bpy.data.materials.new(name="TorchFlame"); mat_flame.use_nodes = True
p2 = mat_flame.node_tree.nodes["Principled BSDF"]
p2.inputs["Base Color"].default_value = (1.0, 0.6, 0.1, 1)
try:
    p2.inputs["Emission Color"].default_value = (1.0, 0.5, 0.1, 1)
    p2.inputs["Emission Strength"].default_value = 20.0
except KeyError:
    try:
        p2.inputs["Emission"].default_value = (1.0, 0.5, 0.1, 1)
        p2.inputs["Emission Strength"].default_value = 20.0
    except KeyError: pass
for o in [handle, head]: o.data.materials.append(mat_wood)
flame.data.materials.append(mat_flame)
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
print(f"Created torch: {len(objs)} parts")
''',
    },
}

# --- PBR Material Presets ---
MATERIAL_PRESETS: Dict[str, Dict[str, Any]] = {
    "Metal_Steel": {"base_color": (0.6, 0.63, 0.65, 1), "metallic": 1.0, "roughness": 0.3},
    "Metal_Gold": {"base_color": (1.0, 0.766, 0.336, 1), "metallic": 1.0, "roughness": 0.2},
    "Metal_Copper": {"base_color": (0.95, 0.64, 0.54, 1), "metallic": 1.0, "roughness": 0.25},
    "Metal_Bronze": {"base_color": (0.8, 0.5, 0.2, 1), "metallic": 1.0, "roughness": 0.35},
    "Metal_Aluminum": {"base_color": (0.91, 0.92, 0.92, 1), "metallic": 1.0, "roughness": 0.15},
    "Plastic_White": {"base_color": (0.95, 0.95, 0.95, 1), "metallic": 0.0, "roughness": 0.4},
    "Plastic_Red": {"base_color": (0.8, 0.05, 0.05, 1), "metallic": 0.0, "roughness": 0.35},
    "Plastic_Blue": {"base_color": (0.05, 0.15, 0.8, 1), "metallic": 0.0, "roughness": 0.35},
    "Plastic_Green": {"base_color": (0.05, 0.6, 0.1, 1), "metallic": 0.0, "roughness": 0.35},
    "Plastic_Black": {"base_color": (0.05, 0.05, 0.05, 1), "metallic": 0.0, "roughness": 0.3},
    "Wood_Oak": {"base_color": (0.65, 0.45, 0.25, 1), "metallic": 0.0, "roughness": 0.7},
    "Wood_Pine": {"base_color": (0.75, 0.6, 0.35, 1), "metallic": 0.0, "roughness": 0.65},
    "Wood_Dark": {"base_color": (0.25, 0.15, 0.08, 1), "metallic": 0.0, "roughness": 0.6},
    "Glass_Clear": {"base_color": (1, 1, 1, 1), "metallic": 0.0, "roughness": 0.0, "transmission": 1.0, "ior": 1.45},
    "Glass_Tinted": {"base_color": (0.8, 0.9, 1, 1), "metallic": 0.0, "roughness": 0.0, "transmission": 0.9, "ior": 1.45},
    "Rubber_Black": {"base_color": (0.02, 0.02, 0.02, 1), "metallic": 0.0, "roughness": 0.9},
    "Rubber_White": {"base_color": (0.9, 0.9, 0.9, 1), "metallic": 0.0, "roughness": 0.85},
    "Fabric_Cotton": {"base_color": (0.85, 0.82, 0.78, 1), "metallic": 0.0, "roughness": 0.95},
    "Fabric_Silk": {"base_color": (0.9, 0.85, 0.8, 1), "metallic": 0.0, "roughness": 0.3},
    "Concrete": {"base_color": (0.5, 0.5, 0.48, 1), "metallic": 0.0, "roughness": 0.85},
    "Stone_Granite": {"base_color": (0.45, 0.43, 0.42, 1), "metallic": 0.0, "roughness": 0.75},
    "Stone_Marble": {"base_color": (0.9, 0.88, 0.85, 1), "metallic": 0.0, "roughness": 0.15},
    "Ceramic": {"base_color": (0.92, 0.9, 0.85, 1), "metallic": 0.0, "roughness": 0.1},
    "Leather_Brown": {"base_color": (0.4, 0.25, 0.12, 1), "metallic": 0.0, "roughness": 0.6},
    "Leather_Black": {"base_color": (0.08, 0.06, 0.05, 1), "metallic": 0.0, "roughness": 0.55},
    "Emissive_White": {"base_color": (1, 1, 1, 1), "metallic": 0.0, "roughness": 0.5, "emission": (1, 1, 1, 1), "emission_strength": 5.0},
    "Emissive_Blue": {"base_color": (0.1, 0.3, 1, 1), "metallic": 0.0, "roughness": 0.5, "emission": (0.1, 0.3, 1, 1), "emission_strength": 5.0},
    "Emissive_Red": {"base_color": (1, 0.1, 0.1, 1), "metallic": 0.0, "roughness": 0.5, "emission": (1, 0.1, 0.1, 1), "emission_strength": 5.0},
    "Water": {"base_color": (0.1, 0.25, 0.35, 1), "metallic": 0.0, "roughness": 0.0, "transmission": 0.95, "ior": 1.33},
    "Skin_Human": {"base_color": (0.8, 0.55, 0.4, 1), "metallic": 0.0, "roughness": 0.45, "subsurface": 0.3},
}

# --- Template Definitions ---
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "chair": {
        "name_en": "Chair",
        "name_zh": "椅子",
        "params": {
            "seat_width": {"default": 0.45, "min": 0.2, "max": 1.0, "label_en": "Seat Width", "label_zh": "座宽"},
            "seat_depth": {"default": 0.45, "min": 0.2, "max": 1.0, "label_en": "Seat Depth", "label_zh": "座深"},
            "seat_height": {"default": 0.45, "min": 0.2, "max": 0.8, "label_en": "Seat Height", "label_zh": "座高"},
            "back_height": {"default": 0.4, "min": 0.0, "max": 1.0, "label_en": "Back Height", "label_zh": "靠背高"},
            "leg_thickness": {"default": 0.04, "min": 0.02, "max": 0.1, "label_en": "Leg Thickness", "label_zh": "腿粗"},
        },
        "prompt_en": "A chair with seat {seat_width}m wide, {seat_depth}m deep, seat at {seat_height}m, back {back_height}m high, legs {leg_thickness}m thick.",
        "prompt_zh": "一把椅子，座宽{seat_width}米，座深{seat_depth}米，座高{seat_height}米，靠背高{back_height}米，腿粗{leg_thickness}米。",
    },
    "table": {
        "name_en": "Table",
        "name_zh": "桌子",
        "params": {
            "top_width": {"default": 1.2, "min": 0.4, "max": 3.0, "label_en": "Top Width", "label_zh": "桌面宽"},
            "top_depth": {"default": 0.8, "min": 0.3, "max": 2.0, "label_en": "Top Depth", "label_zh": "桌面深"},
            "height": {"default": 0.75, "min": 0.3, "max": 1.5, "label_en": "Height", "label_zh": "高度"},
            "leg_thickness": {"default": 0.05, "min": 0.02, "max": 0.15, "label_en": "Leg Thickness", "label_zh": "腿粗"},
            "top_thickness": {"default": 0.03, "min": 0.01, "max": 0.1, "label_en": "Top Thickness", "label_zh": "桌面厚"},
        },
        "prompt_en": "A table with top {top_width}m x {top_depth}m, height {height}m, legs {leg_thickness}m thick, top {top_thickness}m thick.",
        "prompt_zh": "一张桌子，桌面{top_width}x{top_depth}米，高{height}米，腿粗{leg_thickness}米，桌面厚{top_thickness}米。",
    },
    "sword": {
        "name_en": "Sword",
        "name_zh": "剑",
        "params": {
            "blade_length": {"default": 0.8, "min": 0.3, "max": 1.5, "label_en": "Blade Length", "label_zh": "刃长"},
            "blade_width": {"default": 0.05, "min": 0.02, "max": 0.15, "label_en": "Blade Width", "label_zh": "刃宽"},
            "guard_width": {"default": 0.12, "min": 0.05, "max": 0.3, "label_en": "Guard Width", "label_zh": "护手宽"},
            "handle_length": {"default": 0.15, "min": 0.08, "max": 0.4, "label_en": "Handle Length", "label_zh": "柄长"},
        },
        "prompt_en": "A sword: blade {blade_length}m long {blade_width}m wide, guard {guard_width}m wide, handle {handle_length}m.",
        "prompt_zh": "一把剑：刃长{blade_length}米宽{blade_width}米，护手宽{guard_width}米，柄长{handle_length}米。",
    },
    "house": {
        "name_en": "Simple House",
        "name_zh": "简单房屋",
        "params": {
            "width": {"default": 6.0, "min": 3.0, "max": 20.0, "label_en": "Width", "label_zh": "宽度"},
            "depth": {"default": 8.0, "min": 3.0, "max": 20.0, "label_en": "Depth", "label_zh": "深度"},
            "wall_height": {"default": 2.8, "min": 2.0, "max": 5.0, "label_en": "Wall Height", "label_zh": "墙高"},
            "roof_pitch": {"default": 30.0, "min": 0.0, "max": 60.0, "label_en": "Roof Pitch (deg)", "label_zh": "屋顶角度"},
        },
        "prompt_en": "A simple house {width}m wide, {depth}m deep, walls {wall_height}m high, roof pitch {roof_pitch} degrees.",
        "prompt_zh": "一个简单房屋，宽{width}米，深{depth}米，墙高{wall_height}米，屋顶角度{roof_pitch}度。",
    },
    "tree": {
        "name_en": "Tree",
        "name_zh": "树",
        "params": {
            "trunk_height": {"default": 1.5, "min": 0.5, "max": 5.0, "label_en": "Trunk Height", "label_zh": "树干高"},
            "trunk_radius": {"default": 0.1, "min": 0.03, "max": 0.5, "label_en": "Trunk Radius", "label_zh": "树干半径"},
            "crown_radius": {"default": 0.8, "min": 0.3, "max": 3.0, "label_en": "Crown Radius", "label_zh": "树冠半径"},
            "crown_layers": {"default": 3, "min": 1, "max": 6, "label_en": "Crown Layers", "label_zh": "树冠层数"},
        },
        "prompt_en": "A tree: trunk {trunk_height}m tall radius {trunk_radius}m, crown radius {crown_radius}m with {crown_layers} cone layers.",
        "prompt_zh": "一棵树：树干高{trunk_height}米半径{trunk_radius}米，树冠半径{crown_radius}米，{crown_layers}层锥形。",
    },
    "humanoid": {
        "name_en": "Humanoid Figure",
        "name_zh": "人形",
        "params": {
            "height": {"default": 1.75, "min": 0.5, "max": 3.0, "label_en": "Total Height", "label_zh": "总高"},
            "head_size": {"default": 0.2, "min": 0.1, "max": 0.4, "label_en": "Head Size", "label_zh": "头大小"},
            "shoulder_width": {"default": 0.45, "min": 0.2, "max": 0.8, "label_en": "Shoulder Width", "label_zh": "肩宽"},
        },
        "prompt_en": "A humanoid figure {height}m tall, head {head_size}m, shoulders {shoulder_width}m wide. Simple blocky style.",
        "prompt_zh": "一个人形，高{height}米，头{head_size}米，肩宽{shoulder_width}米。简单方块风格。",
    },
    "pillar": {
        "name_en": "Column / Pillar",
        "name_zh": "柱子",
        "params": {
            "height": {"default": 3.0, "min": 0.5, "max": 10.0, "label_en": "Height", "label_zh": "高度"},
            "radius": {"default": 0.2, "min": 0.05, "max": 1.0, "label_en": "Radius", "label_zh": "半径"},
            "segments": {"default": 16, "min": 6, "max": 64, "label_en": "Segments", "label_zh": "分段数"},
            "taper": {"default": 0.0, "min": -0.5, "max": 0.5, "label_en": "Taper", "label_zh": "锥度"},
        },
        "prompt_en": "A column {height}m tall, radius {radius}m, {segments} sides, taper factor {taper}. Add base and capital.",
        "prompt_zh": "一根柱子高{height}米，半径{radius}米，{segments}边，锥度{taper}。添加底座和柱头。",
    },
    "gear": {
        "name_en": "Gear",
        "name_zh": "齿轮",
        "params": {
            "radius": {"default": 0.3, "min": 0.05, "max": 1.0, "label_en": "Radius", "label_zh": "半径"},
            "teeth": {"default": 12, "min": 6, "max": 64, "label_en": "Teeth Count", "label_zh": "齿数"},
            "thickness": {"default": 0.05, "min": 0.01, "max": 0.2, "label_en": "Thickness", "label_zh": "厚度"},
            "hole_radius": {"default": 0.05, "min": 0.01, "max": 0.3, "label_en": "Hole Radius", "label_zh": "孔半径"},
        },
        "prompt_en": "A gear with radius {radius}m, {teeth} teeth, thickness {thickness}m, center hole {hole_radius}m radius.",
        "prompt_zh": "一个齿轮，半径{radius}米，{teeth}齿，厚{thickness}米，中心孔半径{hole_radius}米。",
    },
}

# --- Modifier Presets ---
MODIFIER_PRESETS: Dict[str, Dict[str, Any]] = {
    "Subdivision Surface": {"type": "SUBSURF", "levels": 2, "render_levels": 3},
    "Mirror X": {"type": "MIRROR", "use_axis": [True, False, False]},
    "Mirror XY": {"type": "MIRROR", "use_axis": [True, True, False]},
    "Mirror XYZ": {"type": "MIRROR", "use_axis": [True, True, True]},
    "Array Linear": {"type": "ARRAY", "count": 5, "offset": (2, 0, 0)},
    "Array Circular": {"type": "ARRAY", "count": 8, "use_relative_offset": False, "use_constant_offset": True, "constant_offset": (0, 0, 0)},
    "Bevel": {"type": "BEVEL", "width": 0.01, "segments": 3},
    "Solidify": {"type": "SOLIDIFY", "thickness": 0.01},
    "Triangulate": {"type": "TRIANGULATE"},
    "Decimate 50%": {"type": "DECIMATE", "ratio": 0.5},
    "Decimate 25%": {"type": "DECIMATE", "ratio": 0.25},
    "Boolean Union": {"type": "BOOLEAN", "operation": "UNION"},
    "Boolean Intersect": {"type": "BOOLEAN", "operation": "INTERSECT"},
    "Boolean Difference": {"type": "BOOLEAN", "operation": "DIFFERENCE"},
    "Smooth": {"type": "SMOOTH", "factor": 0.5, "iterations": 10},
    "Lattice": {"type": "LATTICE"},
    "Shrinkwrap": {"type": "SHRINKWRAP"},
    "Cast Sphere": {"type": "CAST", "cast_type": "SPHERE"},
    "Cast Cylinder": {"type": "CAST", "cast_type": "CYLINDER"},
    "Wave": {"type": "WAVE", "height": 0.1, "width": 1.5},
    "Displace": {"type": "DISPLACE", "strength": 0.2},
    "Screw": {"type": "SCREW", "steps": 16, "screw_offset": 0.5},
    "Wireframe": {"type": "WIREFRAME", "thickness": 0.01},
    "Skin": {"type": "SKIN"},
}

# --- LOD Reduction Levels ---
LOD_LEVELS: List[Tuple[str, float]] = [
    ("LOD0_Full", 1.0),
    ("LOD1_High", 0.5),
    ("LOD2_Medium", 0.25),
    ("LOD3_Low", 0.1),
    ("LOD4_Billboard", 0.05),
]

# --- Humanoid Skeleton Joints ---
HUMANOID_SKELETON: List[Dict[str, Any]] = [
    {"name": "Root", "head": (0, 0, 1.0), "tail": (0, 0, 1.05), "parent": None},
    {"name": "Spine", "head": (0, 0, 1.05), "tail": (0, 0, 1.25), "parent": "Root"},
    {"name": "Spine.001", "head": (0, 0, 1.25), "tail": (0, 0, 1.45), "parent": "Spine"},
    {"name": "Chest", "head": (0, 0, 1.45), "tail": (0, 0, 1.6), "parent": "Spine.001"},
    {"name": "Neck", "head": (0, 0, 1.6), "tail": (0, 0, 1.7), "parent": "Chest"},
    {"name": "Head", "head": (0, 0, 1.7), "tail": (0, 0, 1.9), "parent": "Neck"},
    {"name": "Shoulder.L", "head": (0.05, 0, 1.55), "tail": (0.2, 0, 1.55), "parent": "Chest"},
    {"name": "UpperArm.L", "head": (0.2, 0, 1.55), "tail": (0.45, 0, 1.55), "parent": "Shoulder.L"},
    {"name": "ForeArm.L", "head": (0.45, 0, 1.55), "tail": (0.65, 0, 1.55), "parent": "UpperArm.L"},
    {"name": "Hand.L", "head": (0.65, 0, 1.55), "tail": (0.75, 0, 1.55), "parent": "ForeArm.L"},
    {"name": "Shoulder.R", "head": (-0.05, 0, 1.55), "tail": (-0.2, 0, 1.55), "parent": "Chest"},
    {"name": "UpperArm.R", "head": (-0.2, 0, 1.55), "tail": (-0.45, 0, 1.55), "parent": "Shoulder.R"},
    {"name": "ForeArm.R", "head": (-0.45, 0, 1.55), "tail": (-0.65, 0, 1.55), "parent": "UpperArm.R"},
    {"name": "Hand.R", "head": (-0.65, 0, 1.55), "tail": (-0.75, 0, 1.55), "parent": "ForeArm.R"},
    {"name": "Hip.L", "head": (0.1, 0, 1.0), "tail": (0.1, 0, 0.55), "parent": "Root"},
    {"name": "UpperLeg.L", "head": (0.1, 0, 0.95), "tail": (0.1, 0, 0.55), "parent": "Hip.L"},
    {"name": "LowerLeg.L", "head": (0.1, 0, 0.55), "tail": (0.1, 0, 0.1), "parent": "UpperLeg.L"},
    {"name": "Foot.L", "head": (0.1, 0, 0.1), "tail": (0.1, -0.15, 0.0), "parent": "LowerLeg.L"},
    {"name": "Toe.L", "head": (0.1, -0.15, 0.0), "tail": (0.1, -0.25, 0.0), "parent": "Foot.L"},
    {"name": "Hip.R", "head": (-0.1, 0, 1.0), "tail": (-0.1, 0, 0.55), "parent": "Root"},
    {"name": "UpperLeg.R", "head": (-0.1, 0, 0.95), "tail": (-0.1, 0, 0.55), "parent": "Hip.R"},
    {"name": "LowerLeg.R", "head": (-0.1, 0, 0.55), "tail": (-0.1, 0, 0.1), "parent": "UpperLeg.R"},
    {"name": "Foot.R", "head": (-0.1, 0, 0.1), "tail": (-0.1, -0.15, 0.0), "parent": "LowerLeg.R"},
    {"name": "Toe.R", "head": (-0.1, -0.15, 0.0), "tail": (-0.1, -0.25, 0.0), "parent": "Foot.R"},
]

QUADRUPED_SKELETON: List[Dict[str, Any]] = [
    {"name": "Root", "head": (0, 0, 0.8), "tail": (0, 0, 0.85), "parent": None},
    {"name": "Spine", "head": (0, 0, 0.85), "tail": (0, 0.3, 0.85), "parent": "Root"},
    {"name": "Spine.001", "head": (0, 0.3, 0.85), "tail": (0, 0.6, 0.85), "parent": "Spine"},
    {"name": "Chest", "head": (0, 0.6, 0.85), "tail": (0, 0.8, 0.9), "parent": "Spine.001"},
    {"name": "Neck", "head": (0, 0.8, 0.9), "tail": (0, 1.0, 1.1), "parent": "Chest"},
    {"name": "Head", "head": (0, 1.0, 1.1), "tail": (0, 1.15, 1.15), "parent": "Neck"},
    {"name": "Tail", "head": (0, 0, 0.85), "tail": (0, -0.3, 0.9), "parent": "Root"},
    {"name": "Tail.001", "head": (0, -0.3, 0.9), "tail": (0, -0.55, 0.95), "parent": "Tail"},
    {"name": "FrontLeg.L", "head": (0.15, 0.7, 0.85), "tail": (0.15, 0.7, 0.4), "parent": "Chest"},
    {"name": "FrontLower.L", "head": (0.15, 0.7, 0.4), "tail": (0.15, 0.7, 0.0), "parent": "FrontLeg.L"},
    {"name": "FrontFoot.L", "head": (0.15, 0.7, 0.0), "tail": (0.15, 0.6, 0.0), "parent": "FrontLower.L"},
    {"name": "FrontLeg.R", "head": (-0.15, 0.7, 0.85), "tail": (-0.15, 0.7, 0.4), "parent": "Chest"},
    {"name": "FrontLower.R", "head": (-0.15, 0.7, 0.4), "tail": (-0.15, 0.7, 0.0), "parent": "FrontLeg.R"},
    {"name": "FrontFoot.R", "head": (-0.15, 0.7, 0.0), "tail": (-0.15, 0.6, 0.0), "parent": "FrontLower.R"},
    {"name": "BackLeg.L", "head": (0.15, 0.1, 0.8), "tail": (0.15, 0.05, 0.4), "parent": "Root"},
    {"name": "BackLower.L", "head": (0.15, 0.05, 0.4), "tail": (0.15, 0.05, 0.0), "parent": "BackLeg.L"},
    {"name": "BackFoot.L", "head": (0.15, 0.05, 0.0), "tail": (0.15, -0.05, 0.0), "parent": "BackLower.L"},
    {"name": "BackLeg.R", "head": (-0.15, 0.1, 0.8), "tail": (-0.15, 0.05, 0.4), "parent": "Root"},
    {"name": "BackLower.R", "head": (-0.15, 0.05, 0.4), "tail": (-0.15, 0.05, 0.0), "parent": "BackLeg.R"},
    {"name": "BackFoot.R", "head": (-0.15, 0.05, 0.0), "tail": (-0.15, -0.05, 0.0), "parent": "BackLower.R"},
]

# --- Engine Export Presets ---
ENGINE_EXPORT_PRESETS: Dict[str, Dict[str, Any]] = {
    "Unity": {
        "scale": 1.0,
        "forward": "-Z",
        "up": "Y",
        "apply_modifiers": True,
        "triangulate": True,
        "format": "fbx",
        "notes_en": "FBX with Y-up, -Z forward. Apply modifiers before export.",
        "notes_zh": "FBX格式，Y轴向上，-Z轴向前。导出前应用修改器。",
    },
    "Unreal": {
        "scale": 1.0,
        "forward": "X",
        "up": "Z",
        "apply_modifiers": True,
        "triangulate": True,
        "format": "fbx",
        "notes_en": "FBX with Z-up, X forward. Scale 1.0 (cm in UE).",
        "notes_zh": "FBX格式，Z轴向上，X轴向前。缩放1.0（UE中为厘米）。",
    },
    "Godot": {
        "scale": 1.0,
        "forward": "Z",
        "up": "Y",
        "apply_modifiers": True,
        "triangulate": False,
        "format": "glb",
        "notes_en": "GLB/GLTF preferred. Y-up, Z-forward.",
        "notes_zh": "推荐GLB/GLTF格式。Y轴向上，Z轴向前。",
    },
}


# ============================================================================
#  Utility: Preference accessor
# ============================================================================

def get_prefs():
    """Safely get addon preferences."""
    try:
        addon = bpy.context.preferences.addons.get(__name__.split(".")[0] if "." in __name__ else __name__)
        if addon:
            return addon.preferences
    except Exception:
        pass
    return None


# ============================================================================
#  Cost Tracker (thread-safe)
# ============================================================================

class CostTracker:
    """Thread-safe token and cost tracker."""

    _lock = threading.Lock()

    def __init__(self):
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost: float = 0.0
        self.history: List[Dict[str, Any]] = []

    def record(self, prompt_tokens: int, completion_tokens: int, cost: float) -> None:
        with self._lock:
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_cost += cost
            self.history.append({
                "time": time.time(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
            })

    def get_totals(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "prompt_tokens": self.total_prompt_tokens,
                "completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
                "cost": round(self.total_cost, 6),
                "requests": len(self.history),
            }

    def reset(self) -> None:
        with self._lock:
            self.total_prompt_tokens = 0
            self.total_completion_tokens = 0
            self.total_cost = 0.0
            self.history.clear()


# Global cost tracker instance
_cost_tracker = CostTracker()


# ============================================================================
#  Conversation History (with token estimation)
# ============================================================================

class ConversationHistory:
    """Manages conversation history with token estimation and summarization."""

    def __init__(self, max_tokens: int = 16000):
        self.messages: List[Dict[str, str]] = []
        self.max_tokens = max_tokens

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation: ~4 chars per token for English, ~2 for CJK."""
        cjk_count = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))
        other_count = len(text) - cjk_count
        return cjk_count // 2 + other_count // 4

    def _total_tokens(self) -> int:
        return sum(self._estimate_tokens(m.get("content", "")) for m in self.messages)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self._compress_if_needed()

    def _compress_if_needed(self) -> None:
        """Summarize older messages if approaching token limit."""
        while self._total_tokens() > self.max_tokens and len(self.messages) > 3:
            # Keep system message if present, compress oldest user/assistant pair
            system_msgs = [m for m in self.messages if m.get("role") == "system"]
            other_msgs = [m for m in self.messages if m.get("role") != "system"]
            if len(other_msgs) >= 2:
                # Summarize the two oldest messages
                old = other_msgs[:2]
                summary = "[Summary] " + " | ".join(
                    m.get("content", "")[:100] for m in old
                )
                other_msgs = [{"role": "system", "content": summary}] + other_msgs[2:]
            self.messages = system_msgs + other_msgs

    def get_messages(self) -> List[Dict[str, str]]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()

    def get_stats(self) -> Dict[str, int]:
        return {
            "count": len(self.messages),
            "estimated_tokens": self._total_tokens(),
        }


# ============================================================================
#  Security Validator
# ============================================================================

class SecurityValidator:
    """Validates AI-generated code against dangerous patterns."""

    @staticmethod
    def validate(code: str) -> Tuple[bool, str]:
        """
        Check code for dangerous patterns.
        Returns (is_safe, reason).
        """
        for pattern in DANGEROUS_RE:
            match = pattern.search(code)
            if match:
                return False, f"Dangerous pattern detected: {match.group()}"
        return True, ""

    @staticmethod
    def clean_response(raw: str) -> str:
        """Extract Python code from AI response, stripping markdown fences."""
        # Remove # THINK: line
        lines = raw.strip().split("\n")
        code_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```python") or stripped.startswith("```"):
                in_code = not in_code if "```" in stripped else True
                continue
            if stripped.startswith("# THINK:"):
                continue
            code_lines.append(line)
        # If we never entered a code block, return everything except THINK line
        result = "\n".join(code_lines).strip()
        # Remove trailing ``` if any
        if result.endswith("```"):
            result = result[:-3].strip()
        return result


# ============================================================================
#  Scene Context Generator
# ============================================================================

class SceneContextGenerator:
    """Generates comprehensive scene context for AI — the AI's 'eyes' into the scene."""

    @staticmethod
    def generate() -> str:
        lines = []
        scene = bpy.context.scene
        lines.append(f"=== SCENE CONTEXT ===")
        lines.append(f"Scene: {scene.name} | Objects: {len(scene.objects)} | Frame: {scene.frame_start}-{scene.frame_end}")

        # Selected objects (what the user is working on)
        selected = bpy.context.selected_objects
        if selected:
            lines.append(f"\nSELECTED ({len(selected)}):")
            for obj in selected:
                lines.append(SceneContextGenerator._describe_object(obj, "  "))

        # All mesh objects with full detail
        mesh_objects = [o for o in scene.objects if o.type == 'MESH']
        if mesh_objects:
            lines.append(f"\nALL MESH OBJECTS ({len(mesh_objects)}):")
            total_faces = 0
            for obj in mesh_objects:
                lines.append(SceneContextGenerator._describe_object(obj, "  "))
                total_faces += len(obj.data.polygons) if obj.data else 0
            lines.append(f"  Total scene faces: {total_faces}")

        # Non-mesh objects
        other = [o for o in scene.objects if o.type not in {'MESH'}]
        if other:
            lines.append(f"\nOTHER OBJECTS ({len(other)}):")
            for obj in other[:20]:
                loc = obj.location
                lines.append(f"  {obj.name} [{obj.type}] @ ({loc.x:.2f},{loc.y:.2f},{loc.z:.2f})")

        # Materials in scene
        mats = [m for m in bpy.data.materials if m.users > 0]
        if mats:
            lines.append(f"\nMATERIALS ({len(mats)}):")
            for m in mats[:15]:
                lines.append(f"  {m.name} (users={m.users})")

        # Bounding box of entire scene
        if mesh_objects:
            all_coords = []
            for obj in mesh_objects:
                for v in obj.data.vertices:
                    all_coords.append(obj.matrix_world @ v.co)
            if all_coords:
                xs = [c.x for c in all_coords]
                ys = [c.y for c in all_coords]
                zs = [c.z for c in all_coords]
                lines.append(f"\nSCENE BOUNDS: X[{min(xs):.2f}..{max(xs):.2f}] Y[{min(ys):.2f}..{max(ys):.2f}] Z[{min(zs):.2f}..{max(zs):.2f}]")

        return "\n".join(lines)

    @staticmethod
    def _describe_object(obj, indent="") -> str:
        """Detailed description of a single object."""
        loc = obj.location
        dims = obj.dimensions
        lines = [f"{indent}{obj.name} [{obj.type}] pos=({loc.x:.2f},{loc.y:.2f},{loc.z:.2f}) size=({dims.x:.2f},{dims.y:.2f},{dims.z:.2f})"]

        if obj.type == 'MESH' and obj.data:
            mesh = obj.data
            lines[-1] += f" faces={len(mesh.polygons)} verts={len(mesh.vertices)}"

            # Materials
            if mesh.materials:
                mat_names = [m.name if m else "?" for m in mesh.materials]
                lines[-1] += f" mats=[{','.join(mat_names)}]"

            # Modifiers
            if obj.modifiers:
                mod_names = [f"{m.name}({m.type})" for m in obj.modifiers]
                lines[-1] += f" mods=[{','.join(mod_names)}]"

            # UV info
            if mesh.uv_layers:
                lines[-1] += f" uvs={len(mesh.uv_layers)}"

            # Quick quality check
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(mesh)
            loose = len([v for v in bm.verts if not v.link_edges])
            non_manifold = len([e for e in bm.edges if not e.is_manifold])
            ngons = len([f for f in bm.faces if len(f.verts) > 4])
            bm.free()
            issues = []
            if loose: issues.append(f"loose_v={loose}")
            if non_manifold: issues.append(f"non_manifold={non_manifold}")
            if ngons: issues.append(f"ngons={ngons}")
            if issues:
                lines[-1] += f" ISSUES=[{','.join(issues)}]"

        return "\n".join(lines)


class PlanningEngine:
    """
    Decomposes complex requests into structured multi-part plans.
    This is the 'brain' that gives the AI holistic understanding.
    """

    @staticmethod
    def create_plan(request: str, scene_context: str) -> str:
        """Create a structured plan for complex modeling requests."""
        plan = f"""
===== SCENE PLANNING REQUEST =====
The user wants to create: {request}

Current scene state:
{scene_context}

You MUST plan before coding. Follow this structure:

STEP 1 — PART DECOMPOSITION
List every distinct geometric part needed. For each part specify:
- Part name (English, descriptive)
- Geometric approach (primitive/extrude/boolean/subdivision/curve)
- Approximate dimensions (meters)
- Material type

STEP 2 — SPATIAL LAYOUT
Plan where each part goes in 3D space. Ensure parts connect properly.
- Use a consistent coordinate system (Z-up, Y-forward)
- Parts should not overlap unless intentionally
- Leave appropriate gaps for joints, hinges, etc.

STEP 3 — DEPENDENCY ORDER
Which parts must be created first? Boolean operations need both objects.
Modifiers reference other objects. Plan the creation order.

STEP 4 — CODE STRUCTURE
Plan your code as:
1. Create all base geometry first
2. Apply transforms and modifiers
3. Create and assign materials
4. Final cleanup (normals, remove doubles, smooth shading)

Now write the code following your plan. Each part in its own try/except block.
"""
        return plan


class PostProcessor:
    """
    Automatic post-processing to improve model quality after generation.
    """

    @staticmethod
    def process_all() -> Tuple[bool, str]:
        """Run all post-processing steps on scene mesh objects."""
        results = []
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH':
                continue
            result = PostProcessor.process_object(obj)
            if result:
                results.append(f"{obj.name}: {result}")

        if results:
            return True, "Post-processing:\n" + "\n".join(results)
        return True, "Post-processing: no issues found"

    @staticmethod
    def process_object(obj: bpy.types.Object) -> str:
        """Post-process a single mesh object."""
        changes = []

        try:
            # 1. Remove doubles
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles(threshold=0.001)

            # 2. Recalculate normals
            bpy.ops.mesh.normals_make_consistent(inside=False)

            # 3. Delete loose geometry
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_loose()
            bpy.ops.mesh.delete(type='VERT')

            bpy.ops.object.mode_set(mode='OBJECT')
            changes.append("cleaned geometry")
        except RuntimeError as e:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass
            changes.append(f"cleanup error: {e}")

        # 4. Ensure smooth shading for organic shapes (high face count)
        if obj.data and len(obj.data.polygons) > 100:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.shade_smooth()
            changes.append("smooth shading")

        # 5. Apply transforms if not identity
        if (obj.rotation_euler.x != 0 or obj.rotation_euler.y != 0 or
                obj.rotation_euler.z != 0 or
                obj.scale.x != 1 or obj.scale.y != 1 or obj.scale.z != 1):
            bpy.context.view_layer.objects.active = obj
            try:
                bpy.ops.object.transform_apply(rotation=True, scale=True)
                changes.append("applied transforms")
            except RuntimeError:
                pass

        # 6. Ensure at least one material
        if obj.data and len(obj.data.materials) == 0:
            mat = bpy.data.materials.new(name=f"{obj.name}_Mat")
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
                bsdf.inputs["Roughness"].default_value = 0.5
            obj.data.materials.append(mat)
            changes.append("added default material")

        return "; ".join(changes) if changes else ""


class RefinementEngine:
    """
    Enables iterative refinement — improve existing models, not just create new ones.
    """

    @staticmethod
    def build_refinement_prompt(user_request: str) -> str:
        """
        Build a prompt that tells the AI to refine existing objects
        rather than creating from scratch.
        """
        selected = bpy.context.selected_objects
        if not selected:
            return user_request

        parts = []
        parts.append(f"REFINEMENT REQUEST: {user_request}")
        parts.append("")
        parts.append("The following objects already exist and need to be improved:")
        parts.append("You MUST modify these existing objects, NOT create new ones.")
        parts.append("Use bmesh to edit their geometry in place.")
        parts.append("")

        for obj in selected:
            if obj.type != 'MESH':
                continue
            desc = SceneContextGenerator._describe_object(obj, "")
            parts.append(f"OBJECT: {desc}")

            # Describe current geometry
            mesh = obj.data
            parts.append(f"  Current shape: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces")

            # Bounding box
            if mesh.vertices:
                import bmesh
                bm = bmesh.new()
                bm.from_mesh(mesh)
                bbox_min = tuple(min(v.co[i] for v in bm.verts) for i in range(3))
                bbox_max = tuple(max(v.co[i] for v in bm.verts) for i in range(3))
                bm.free()
                parts.append(f"  BBox: ({bbox_min[0]:.2f},{bbox_min[1]:.2f},{bbox_min[2]:.2f}) to ({bbox_max[0]:.2f},{bbox_max[1]:.2f},{bbox_max[2]:.2f})")

        parts.append("")
        parts.append("Use bmesh operations to modify the existing mesh:")
        parts.append("- bmesh.ops.extrude_face_region() for adding detail")
        parts.append("- bmesh.ops.bevel() for edge refinement")
        parts.append("- bmesh.ops.subdivide_edges() for more geometry")
        parts.append("- bmesh.ops.translate() / scale() / rotate() for shape changes")
        parts.append("- bmesh.ops.delete() for removing unwanted parts")
        parts.append("Always call bm.to_mesh(obj.data) and bm.free() when done.")

        return "\n".join(parts)


# ============================================================================
#  API Engine
# ============================================================================

class APIEngine:
    """Handles communication with any OpenAI-compatible API."""

    # Cost per 1M tokens (input/output) for common models
    KNOWN_COSTS: Dict[str, Tuple[float, float]] = {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-3.5-turbo": (0.50, 1.50),
        "claude-3-5-sonnet": (3.00, 15.00),
        "claude-3-haiku": (0.25, 1.25),
        "deepseek-chat": (0.14, 0.28),
        "deepseek-reasoner": (0.55, 2.19),
        "qwen-plus": (0.40, 1.20),
        "qwen-turbo": (0.05, 0.20),
    }

    def __init__(self, api_url: str, api_key: str, model: str,
                 temperature: float = 0.7, max_tokens: int = 4096):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on known model pricing."""
        # Find longest matching key (avoid gpt-4o matching gpt-4o-mini)
        input_rate, output_rate = 0.0, 0.0
        best_match_len = 0
        model_lower = self.model.lower()
        for key, (ir, or_) in self.KNOWN_COSTS.items():
            if key in model_lower and len(key) > best_match_len:
                input_rate, output_rate = ir, or_
                best_match_len = len(key)
        if input_rate == 0:
            return 0.0
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000

    def chat(self, messages: List[Dict[str, str]], system_prompt: str = "") -> Dict[str, Any]:
        """
        Send a chat completion request.
        Returns: {"content": str, "prompt_tokens": int, "completion_tokens": int, "cost": float, "error": str}
        """
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        url = self.api_url
        if not url.endswith("/chat/completions"):
            url = url + "/chat/completions"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        # SSL context with verification enabled
        ctx = ssl.create_default_context()

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return {"content": "", "prompt_tokens": 0, "completion_tokens": 0,
                    "cost": 0.0, "error": f"HTTP {e.code}: {error_body[:500]}"}
        except urllib.error.URLError as e:
            return {"content": "", "prompt_tokens": 0, "completion_tokens": 0,
                    "cost": 0.0, "error": f"URL Error: {e.reason}"}
        except json.JSONDecodeError as e:
            return {"content": "", "prompt_tokens": 0, "completion_tokens": 0,
                    "cost": 0.0, "error": f"JSON parse error: {e}"}
        except Exception as e:
            return {"content": "", "prompt_tokens": 0, "completion_tokens": 0,
                    "cost": 0.0, "error": f"Request failed: {type(e).__name__}: {e}"}

        # Parse response
        try:
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            cost = self._estimate_cost(prompt_tokens, completion_tokens)
            _cost_tracker.record(prompt_tokens, completion_tokens, cost)
            return {
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "error": "",
            }
        except (KeyError, IndexError, TypeError) as e:
            return {"content": "", "prompt_tokens": 0, "completion_tokens": 0,
                    "cost": 0.0, "error": f"Failed to parse response: {e}"}


# ============================================================================
#  Sandboxed Code Executor
# ============================================================================

class CodeExecutor:
    """Executes AI-generated code in a restricted environment."""

    # Modules allowed in the sandbox
    ALLOWED_MODULES = {
        "bpy", "bmesh", "mathutils", "math", "random",
        "collections", "itertools", "functools", "copy",
    }

    @classmethod
    def execute(cls, code: str) -> Tuple[bool, str]:
        """
        Execute code in a sandboxed environment.
        Returns (success, output_or_error).
        """
        # Security check
        is_safe, reason = SecurityValidator.validate(code)
        if not is_safe:
            return False, f"Security: {reason}"

        # Build sandboxed namespace
        import builtins
        safe_builtins = {}
        for name in ALLOWED_BUILTINS:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)

        sandbox = {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",
        }

        # Inject safe modules
        try:
            sandbox["bpy"] = bpy
            import bmesh
            sandbox["bmesh"] = bmesh
            from mathutils import Vector, Matrix, Euler, Quaternion
            sandbox["Vector"] = Vector
            sandbox["Matrix"] = Matrix
            sandbox["Euler"] = Euler
            sandbox["Quaternion"] = Quaternion
            import math
            sandbox["math"] = math
            import random
            sandbox["random"] = random
            import copy
            sandbox["copy"] = copy
        except ImportError as e:
            return False, f"Failed to import safe module: {e}"

        # Capture output
        output_lines = []

        class OutputCapture:
            def write(self, text):
                if text.strip():
                    output_lines.append(text.rstrip())
            def flush(self):
                pass

        old_stdout = sys.stdout
        sys.stdout = OutputCapture()

        try:
            exec(code, sandbox)
            output = "\n".join(output_lines)
            return True, output if output else "Code executed successfully (no output)"
        except Exception as e:
            tb = traceback.format_exc()
            return False, f"Execution error:\n{tb}"
        finally:
            sys.stdout = old_stdout


# ============================================================================
#  Auto-Fix Engine
# ============================================================================

class AutoFixEngine:
    """Attempts to automatically fix failed code."""

    MAX_ATTEMPTS = 3

    @classmethod
    def fix_and_retry(cls, original_prompt: str, code: str, error: str,
                      api: APIEngine, history: ConversationHistory) -> Tuple[bool, str, int]:
        """
        Attempt to fix code up to MAX_ATTEMPTS times.
        Returns (success, final_code, attempts_made).
        """
        for attempt in range(1, cls.MAX_ATTEMPTS + 1):
            fix_prompt = (
                f"The following code failed with error:\n{error}\n\n"
                f"Original code:\n{code}\n\n"
                f"Please fix the code. Return ONLY the corrected Python code."
            )
            history.add("user", fix_prompt)
            result = api.chat(history.get_messages(), system_prompt=SYSTEM_PROMPT)

            if result["error"]:
                logger.warning("Auto-fix API error (attempt %d): %s", attempt, result["error"])
                continue

            fixed_code = SecurityValidator.clean_response(result["content"])
            history.add("assistant", result["content"])

            success, output = CodeExecutor.execute(fixed_code)
            if success:
                return True, fixed_code, attempt

            code = fixed_code
            error = output
            logger.info("Auto-fix attempt %d failed: %s", attempt, output[:200])

        return False, code, cls.MAX_ATTEMPTS


# ============================================================================
#  Mesh Analysis Utilities
# ============================================================================

class MeshAnalyzer:
    """Detailed mesh quality analysis tools."""

    @staticmethod
    def analyze(obj: bpy.types.Object) -> Dict[str, Any]:
        """Comprehensive mesh analysis for an object."""
        if obj.type != 'MESH':
            return {"error": f"{obj.name} is not a mesh"}

        mesh = obj.data
        result = {
            "name": obj.name,
            "vertices": len(mesh.vertices),
            "edges": len(mesh.edges),
            "faces": len(mesh.polygons),
            "materials": len(mesh.materials),
            "has_uvs": len(mesh.uv_layers) > 0,
            "uv_layers": len(mesh.uv_layers),
        }

        # Check for non-manifold
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)

        non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
        loose_verts = [v for v in bm.verts if not v.link_edges]
        loose_edges = [e for e in bm.edges if not e.link_faces]
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        tris = [f for f in bm.faces if len(f.verts) == 3]

        result["non_manifold_edges"] = len(non_manifold_edges)
        result["loose_vertices"] = len(loose_verts)
        result["loose_edges"] = len(loose_edges)
        result["ngons"] = len(ngons)
        result["triangles"] = len(tris)
        result["quads"] = result["faces"] - len(ngons) - len(tris)

        # Check normals
        flipped = 0
        for f in bm.faces:
            if f.normal.z < -0.5:
                flipped += 1
        result["possibly_flipped_faces"] = flipped

        bm.free()

        # Bounding box
        bbox = [obj.matrix_world @ v.co for v in mesh.vertices]
        if bbox:
            xs = [v.x for v in bbox]
            ys = [v.y for v in bbox]
            zs = [v.z for v in bbox]
            result["bbox_min"] = (min(xs), min(ys), min(zs))
            result["bbox_max"] = (max(xs), max(ys), max(zs))
            result["dimensions"] = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

        return result


# ============================================================================
#  Quality Check & Fix Tools
# ============================================================================

class QualityChecker:
    """Automated quality detection and repair."""

    @staticmethod
    def check_all() -> List[Dict[str, Any]]:
        """Check all mesh objects in the scene."""
        issues = []
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH':
                continue
            analysis = MeshAnalyzer.analyze(obj)
            if "error" in analysis:
                continue

            if analysis["loose_vertices"] > 0:
                issues.append({"object": obj.name, "type": "loose_vertices",
                               "count": analysis["loose_vertices"], "severity": "warning"})
            if analysis["loose_edges"] > 0:
                issues.append({"object": obj.name, "type": "loose_edges",
                               "count": analysis["loose_edges"], "severity": "warning"})
            if analysis["non_manifold_edges"] > 0:
                issues.append({"object": obj.name, "type": "non_manifold",
                               "count": analysis["non_manifold_edges"], "severity": "warning"})
            if analysis["possibly_flipped_faces"] > 0:
                issues.append({"object": obj.name, "type": "flipped_normals",
                               "count": analysis["possibly_flipped_faces"], "severity": "error"})
            if analysis["ngons"] > 0:
                issues.append({"object": obj.name, "type": "ngons",
                               "count": analysis["ngons"], "severity": "info"})
            if analysis["materials"] == 0:
                issues.append({"object": obj.name, "type": "no_material",
                               "count": 1, "severity": "info"})
        return issues

    @staticmethod
    def fix_object(obj_name: str) -> Tuple[bool, str]:
        """Attempt to fix common mesh issues."""
        obj = bpy.context.scene.objects.get(obj_name)
        if not obj or obj.type != 'MESH':
            return False, "Object not found or not a mesh"

        fixes = []
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        # Remove loose vertices
        loose = [v for v in bm.verts if not v.link_edges]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
            fixes.append(f"Removed {len(loose)} loose vertices")

        # Remove loose edges
        loose_e = [e for e in bm.edges if not e.link_faces]
        if loose_e:
            bmesh.ops.delete(bm, geom=loose_e, context='EDGES')
            fixes.append(f"Removed {len(loose_e)} loose edges")

        # Recalculate normals
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        fixes.append("Recalculated normals")

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        return True, "; ".join(fixes) if fixes else "No issues found"


# ============================================================================
#  Property Groups
# ============================================================================

class AMA_Properties(PropertyGroup):
    """Main addon properties stored per-scene."""

    # Prompt
    prompt: StringProperty(
        name="Prompt",
        description="Describe what to create",
        default="",
        maxlen=2048,
    )

    # API Settings
    api_url: StringProperty(
        name="API URL",
        description="OpenAI-compatible API endpoint",
        default="https://api.openai.com/v1",
    )
    api_key: StringProperty(
        name="API Key",
        description="API authentication key",
        default="",
        subtype='PASSWORD',
    )
    model: StringProperty(
        name="Model",
        description="Model name",
        default="gpt-4o-mini",
    )
    temperature: FloatProperty(
        name="Temperature",
        description="Generation temperature (0.0-2.0)",
        default=0.7, min=0.0, max=2.0,
    )
    max_tokens: IntProperty(
        name="Max Tokens",
        description="Maximum tokens in response",
        default=4096, min=256, max=128000,
    )
    api_preset: EnumProperty(
        name="Preset",
        description="API preset (or Custom)",
        items=[
            ("custom", "Custom / 自定义", "Use custom API settings"),
            ("openai", "OpenAI", "OpenAI API"),
            ("deepseek", "DeepSeek", "DeepSeek API"),
            ("qwen", "Qwen (Alibaba)", "Alibaba Qwen API"),
            ("zhipu", "Zhipu (GLM)", "Zhipu GLM API"),
            ("moonshot", "Moonshot", "Moonshot API"),
            ("siliconflow", "SiliconFlow", "SiliconFlow API"),
            ("groq", "Groq", "Groq API"),
            ("together", "Together AI", "Together AI API"),
            ("openrouter", "OpenRouter", "OpenRouter API"),
            ("ollama", "Ollama (Local)", "Local Ollama API"),
            ("lmstudio", "LM Studio (Local)", "Local LM Studio API"),
            ("deepseek_v3", "DeepSeek V3", "DeepSeek V3 API"),
            ("deepseek_coder", "DeepSeek Coder", "DeepSeek Coder API"),
            ("qwen_plus", "Qwen-Plus", "Alibaba Qwen-Plus"),
            ("qwen_turbo", "Qwen-Turbo", "Alibaba Qwen-Turbo"),
            ("qwen3_coder", "Qwen3-Coder", "Alibaba Qwen3-Coder"),
            ("glm4", "GLM-4", "Zhipu GLM-4"),
            ("glm4_flash", "GLM-4-Flash", "Zhipu GLM-4-Flash (Free)"),
            ("kimi", "Kimi (Moonshot)", "Moonshot Kimi API"),
            ("siliconflow_ds", "SiliconFlow DeepSeek", "SiliconFlow DeepSeek-V3"),
            ("siliconflow_qw", "SiliconFlow Qwen3", "SiliconFlow Qwen3-8B (Free)"),
        ],
        default="custom",
    )

    # UI state
    auto_fix: BoolProperty(
        name="Auto Fix",
        description="Automatically attempt to fix failed code",
        default=True,
    )
    show_scene_context: BoolProperty(
        name="Scene Context",
        description="Include scene context in AI request",
        default=True,
    )
    include_history: BoolProperty(
        name="Include History",
        description="Include conversation history in requests",
        default=True,
    )
    max_history_tokens: IntProperty(
        name="Max History Tokens",
        description="Maximum tokens for conversation history",
        default=16000, min=1000, max=200000,
    )

    # Last generated code (for display/execution)
    last_code: StringProperty(
        name="Last Code",
        description="Last AI-generated code",
        default="",
    )
    last_think: StringProperty(
        name="Last Think",
        description="AI's thinking process",
        default="",
    )
    status_message: StringProperty(
        name="Status",
        default="Ready",
    )

    # LOD settings
    lod_target: StringProperty(
        name="LOD Target",
        description="Object name for LOD generation",
        default="",
    )

    # Version snapshots
    version_name: StringProperty(
        name="Version Name",
        description="Name for version snapshot",
        default="",
    )

    # Asset management
    asset_name: StringProperty(
        name="Asset Name",
        description="Name for asset registration",
        default="",
    )
    asset_category: StringProperty(
        name="Asset Category",
        description="Category for asset",
        default="General",
    )

    # Batch operations
    batch_prefix: StringProperty(
        name="Prefix",
        description="Prefix for batch rename",
        default="",
    )
    batch_suffix: StringProperty(
        name="Suffix",
        description="Suffix for batch rename",
        default="",
    )
    batch_find: StringProperty(
        name="Find",
        description="Text to find in names",
        default="",
    )
    batch_replace: StringProperty(
        name="Replace",
        description="Replacement text",
        default="",
    )

    # Export
    export_engine: EnumProperty(
        name="Engine",
        items=[
            ("unity", "Unity", "Unity Engine"),
            ("unreal", "Unreal Engine", "Unreal Engine"),
            ("godot", "Godot", "Godot Engine"),
        ],
        default="unity",
    )
    export_path: StringProperty(
        name="Export Path",
        description="Export file path",
        default="//",
        subtype='DIR_PATH',
    )

    # Template params (stored as JSON string)
    template_params_json: StringProperty(
        name="Template Params",
        default="{}",
    )
    active_template: EnumProperty(
        name="Template",
        items=[
            ("chair", "Chair", "椅子"),
            ("table", "Table", "桌子"),
            ("sword", "Sword", "剑"),
            ("house", "Simple House", "简单房屋"),
            ("tree", "Tree", "树"),
            ("humanoid", "Humanoid Figure", "人形"),
            ("pillar", "Column / Pillar", "柱子"),
            ("gear", "Gear", "齿轮"),
        ],
        default="chair",
    )


class AMA_AddonPreferences(bpy.types.AddonPreferences):
    """Addon preferences for global settings."""
    bl_idname = __name__.split(".")[0] if "." in __name__ else __name__

    language: EnumProperty(
        name="Language / 语言",
        items=[
            ("en", "English", "English interface"),
            ("zh", "中文", "Chinese interface"),
        ],
        default="en",
    )

    # Persistent API presets (stored as JSON)
    custom_presets_json: StringProperty(
        name="Custom API Presets",
        description="JSON string of custom API presets",
        default="[]",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "language")
        layout.separator()
        layout.label(text="Custom API Presets are managed in the sidebar panel.")


# ============================================================================
#  Global State
# ============================================================================

# Conversation history per scene
_conversation_histories: Dict[str, ConversationHistory] = {}
# Version snapshots: {scene_name: [{name, timestamp, objects_data}]}
_version_snapshots: Dict[str, List[Dict]] = {}
# Asset registry
_asset_registry: List[Dict[str, Any]] = []


def get_conversation(scene_name: str = None) -> ConversationHistory:
    """Get or create conversation history for a scene."""
    if scene_name is None:
        scene_name = bpy.context.scene.name
    if scene_name not in _conversation_histories:
        _conversation_histories[scene_name] = ConversationHistory()
    return _conversation_histories[scene_name]


def get_api_engine() -> APIEngine:
    """Create API engine from current properties."""
    props = bpy.context.scene.ama_props
    return APIEngine(
        api_url=props.api_url,
        api_key=props.api_key,
        model=props.model,
        temperature=props.temperature,
        max_tokens=props.max_tokens,
    )


def apply_preset(preset_name: str, props) -> None:
    """Apply an API preset to properties."""
    presets = {
        "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
        "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
        "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        "moonshot": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        "siliconflow": ("https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-7B-Instruct"),
        "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
        "together": ("https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
        "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct"),
        "ollama": ("http://localhost:11434/v1", "llama3.1"),
        "lmstudio": ("http://localhost:1234/v1", "local-model"),
        # Chinese model presets
        "deepseek_v3": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "deepseek_coder": ("https://api.deepseek.com/v1", "deepseek-coder"),
        "qwen_plus": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
        "qwen_turbo": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
        "qwen3_coder": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3-coder-next"),
        "glm4": ("https://open.bigmodel.cn/api/paas/v4", "glm-4"),
        "glm4_flash": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        "kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        "siliconflow_ds": ("https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3"),
        "siliconflow_qw": ("https://api.siliconflow.cn/v1", "Qwen/Qwen3-8B"),
    }
    if preset_name in presets:
        url, model = presets[preset_name]
        props.api_url = url
        props.model = model


# ============================================================================
#  Operators
# ============================================================================

class AMA_OT_SendToAI(Operator):
    """Send prompt to AI and generate code"""
    bl_idname = "ama.send_to_ai"
    bl_label = "Send to AI"
    bl_description = "Send prompt to AI and generate modeling code"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ama_props

        if not props.prompt.strip():
            self.report({'WARNING'}, "Please enter a prompt")
            return {'CANCELLED'}

        if not props.api_key.strip() and "localhost" not in props.api_url and "127.0.0.1" not in props.api_url:
            self.report({'WARNING'}, "Please set API key")
            return {'CANCELLED'}

        # Apply preset if not custom
        if props.api_preset != "custom":
            apply_preset(props.api_preset, props)

        api = get_api_engine()
        conv = get_conversation()

        # Build user message
        user_parts = [props.prompt]

        if props.show_scene_context:
            ctx = SceneContextGenerator.generate()
            user_parts.append(f"\n--- Scene Context ---\n{ctx}")

        user_msg = "\n".join(user_parts)

        if props.include_history:
            conv.add("user", user_msg)
            messages = conv.get_messages()
        else:
            messages = [{"role": "user", "user_msg": user_msg}]

        props.status_message = t("generating")
        # Force UI update
        context.area.tag_redraw()

        # Run API call (blocking for now; could be threaded)
        result = api.chat(messages, system_prompt=SYSTEM_PROMPT)

        if result["error"]:
            props.status_message = f"{t('error')}: {result['error'][:100]}"
            self.report({'ERROR'}, result["error"][:200])
            return {'CANCELLED'}

        raw = result["content"]
        code = SecurityValidator.clean_response(raw)

        # Extract THINK line
        think_line = ""
        for line in raw.split("\n"):
            if line.strip().startswith("# THINK:"):
                think_line = line.strip()[8:].strip()
                break

        props.last_code = code
        props.last_think = think_line
        if props.include_history:
            conv.add("assistant", raw)

        stats = _cost_tracker.get_totals()
        props.status_message = (
            f"{t('success')} | {result['prompt_tokens']}+{result['completion_tokens']} tokens | "
            f"${stats['cost']:.4f} total"
        )
        logger.info("Generated code for prompt: %s", props.prompt[:80])
        return {'FINISHED'}


class AMA_OT_QuickBuild(Operator):
    """Instantly create a 3D object from a preset (no API needed)"""
    bl_idname = "ama.quick_build"
    bl_label = "Quick Build"
    bl_description = "Instantly create a 3D model from preset code"
    bl_options = {'REGISTER', 'UNDO'}

    preset_key: StringProperty(name="Preset")

    def execute(self, context):
        preset = QUICK_BUILDS.get(self.preset_key)
        if not preset:
            self.report({'WARNING'}, f"Unknown preset: {self.preset_key}")
            return {'CANCELLED'}
        code = preset["code"]
        props = context.scene.ama_props
        props.last_code = code
        success, output = CodeExecutor.execute(code)
        if success:
            self.report({'INFO'}, output)
        else:
            self.report({'ERROR'}, output[:200])
        return {'FINISHED'}


class AMA_OT_CodeEditExecute(Operator):
    """Execute code from the code editor box"""
    bl_idname = "ama.code_edit_execute"
    bl_label = "Run Code"
    bl_description = "Execute the code in the editor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ama_props
        code = props.last_code.strip()
        if not code:
            self.report({'WARNING'}, "No code to execute")
            return {'CANCELLED'}
        success, output = CodeExecutor.execute(code)
        if success:
            self.report({'INFO'}, output[:200])
        else:
            self.report({'ERROR'}, output[:200])
        return {'FINISHED'}


class AMA_OT_ExecuteCode(Operator):
    """Execute the last AI-generated code"""
    bl_idname = "ama.execute_code"
    bl_label = "Execute Code"
    bl_description = "Execute the generated Python code in Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ama_props
        code = props.last_code

        if not code.strip():
            self.report({'WARNING'}, "No code to execute")
            return {'CANCELLED'}

        # Security check
        is_safe, reason = SecurityValidator.validate(code)
        if not is_safe:
            props.status_message = f"{t('security_blocked')}: {reason}"
            self.report({'ERROR'}, f"Security: {reason}")
            return {'CANCELLED'}

        props.status_message = t("executing")
        context.area.tag_redraw()

        success, output = CodeExecutor.execute(code)

        if success:
            props.status_message = f"{t('success')}: {output[:100]}"
            self.report({'INFO'}, output[:200])
        else:
            props.status_message = f"{t('error')}: {output[:100]}"
            self.report({'ERROR'}, output[:200])

            # Auto-fix
            if props.auto_fix:
                api = get_api_engine()
                conv = get_conversation()
                fixed, final_code, attempts = AutoFixEngine.fix_and_retry(
                    props.prompt, code, output, api, conv
                )
                if fixed:
                    props.last_code = final_code
                    success2, output2 = CodeExecutor.execute(final_code)
                    if success2:
                        props.status_message = f"Auto-fixed ({attempts} attempts): {output2[:80]}"
                        self.report({'INFO'}, f"Auto-fixed after {attempts} attempts")
                    else:
                        props.status_message = f"Auto-fix failed after {attempts} attempts"
                else:
                    props.status_message = f"Auto-fix exhausted ({attempts} attempts)"

        return {'FINISHED'}


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
                bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
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
        links = mat.node_tree.links

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


class AMA_OT_BatchExport(Operator):
    """Export selected objects"""
    bl_idname = "ama.batch_export"
    bl_label = "Batch Export"
    bl_options = {'REGISTER'}

    format: EnumProperty(
        name="Format",
        items=[
            ("fbx", "FBX", "FBX format"),
            ("obj", "OBJ", "OBJ format"),
            ("gltf", "glTF", "glTF/GLB format"),
            ("stl", "STL", "STL format"),
        ],
        default="fbx",
    )

    def execute(self, context):
        props = context.scene.ama_props
        export_path = bpy.path.abspath(props.export_path)
        targets = context.selected_objects if context.selected_objects else context.scene.objects

        count = 0
        for obj in targets:
            if obj.type != 'MESH':
                continue
            filepath = f"{export_path}{obj.name}.{self.format.lower()}"

            # Select only this object
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            try:
                if self.format == "fbx":
                    bpy.ops.export_scene.fbx(filepath=filepath, use_selection=True)
                elif self.format == "obj":
                    bpy.ops.wm.obj_export(filepath=filepath, export_selected_objects=True)
                elif self.format == "gltf":
                    bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True)
                elif self.format == "stl":
                    bpy.ops.wm.stl_export(filepath=filepath, export_selected_objects=True)
                count += 1
            except RuntimeError as e:
                logger.warning("Export failed for %s: %s", obj.name, e)

        # Restore selection
        for obj in targets:
            obj.select_set(True)

        self.report({'INFO'}, f"Exported {count} objects")
        return {'FINISHED'}


class AMA_OT_EngineExport(Operator):
    """Export scene for a game engine"""
    bl_idname = "ama.engine_export"
    bl_label = "Engine Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.ama_props
        preset = ENGINE_EXPORT_PRESETS.get(props.export_engine)
        if not preset:
            self.report({'WARNING'}, "Unknown engine")
            return {'CANCELLED'}

        export_path = bpy.path.abspath(props.export_path)

        # Apply modifiers if needed
        if preset.get("apply_modifiers"):
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    context.view_layer.objects.active = obj
                    for mod in obj.modifiers:
                        try:
                            bpy.ops.object.modifier_apply(modifier=mod.name)
                        except RuntimeError:
                            pass

        # Triangulate if needed
        if preset.get("triangulate"):
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    context.view_layer.objects.active = obj
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.quads_convert_to_tris()
                    bpy.ops.object.mode_set(mode='OBJECT')

        # Apply scale
        scale = preset.get("scale", 1.0)
        if scale != 1.0:
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    obj.scale = (scale, scale, scale)
                    bpy.ops.object.transform_apply(scale=True)

        fmt = preset.get("format", "fbx")
        filepath = f"{export_path}scene_export.{fmt}"

        try:
            if fmt == "fbx":
                bpy.ops.export_scene.fbx(filepath=filepath)
            elif fmt == "glb":
                bpy.ops.export_scene.gltf(filepath=filepath, export_format='GLB')
            self.report({'INFO'}, f"Exported for {props.export_engine}: {filepath}")
        except RuntimeError as e:
            self.report({'ERROR'}, f"Export failed: {e}")

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


class AMA_OT_ApplyTemplate(Operator):
    """Apply a parameterized template"""
    bl_idname = "ama.apply_template"
    bl_label = "Apply Template"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ama_props
        template_key = props.active_template
        template = TEMPLATES.get(template_key)
        if not template:
            self.report({'WARNING'}, "Unknown template")
            return {'CANCELLED'}

        # Parse stored params
        try:
            params = json.loads(props.template_params_json)
        except (json.JSONDecodeError, TypeError):
            params = {}

        # Fill defaults
        for key, cfg in template["params"].items():
            if key not in params:
                params[key] = cfg["default"]

        # Build prompt from template
        lang = "zh" if getattr(get_prefs(), "language", "en") == "zh" else "en"
        prompt_key = f"prompt_{lang}"
        prompt_template = template.get(prompt_key, template.get("prompt_en", ""))
        try:
            prompt = prompt_template.format(**params)
        except KeyError:
            prompt = prompt_template

        # Set as prompt and send to AI
        props.prompt = prompt
        bpy.ops.ama.send_to_ai()

        self.report({'INFO'}, f"Template '{template_key}' applied")
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


class AMA_OT_RefineObject(Operator):
    """Iteratively refine selected objects with AI guidance"""
    bl_idname = "ama.refine_object"
    bl_label = "AI Refine"
    bl_description = "Use AI to improve existing selected objects (not create new ones)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ama_props

        if not props.prompt.strip():
            self.report({'WARNING'}, "Describe how to improve the selected object(s)")
            return {'CANCELLED'}

        selected = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected:
            self.report({'WARNING'}, "Select mesh objects to refine")
            return {'CANCELLED'}

        # Build refinement prompt
        refinement_prompt = RefinementEngine.build_refinement_prompt(props.prompt)

        if props.show_scene_context:
            ctx = SceneContextGenerator.generate()
            refinement_prompt += f"\n\n{ctx}"

        api = get_api_engine()
        conv = get_conversation()

        if props.include_history:
            conv.add("user", refinement_prompt)
            messages = conv.get_messages()
        else:
            messages = [{"role": "user", "content": refinement_prompt}]

        props.status_message = "Refining..."
        context.area.tag_redraw()

        result = api.chat(messages, system_prompt=SYSTEM_PROMPT)

        if result["error"]:
            props.status_message = f"Error: {result['error'][:100]}"
            self.report({'ERROR'}, result["error"][:200])
            return {'CANCELLED'}

        raw = result["content"]
        code = SecurityValidator.clean_response(raw)

        # Extract THINK
        for line in raw.split("\n"):
            if line.strip().startswith("# THINK:"):
                props.last_think = line.strip()[8:].strip()
                break

        props.last_code = code
        if props.include_history:
            conv.add("assistant", raw)

        # Execute immediately for refinement
        is_safe, reason = SecurityValidator.validate(code)
        if not is_safe:
            props.status_message = f"Security: {reason}"
            self.report({'ERROR'}, f"Security: {reason}")
            return {'CANCELLED'}

        success, output = CodeExecutor.execute(code)
        if success:
            props.status_message = f"Refined: {output[:80]}"
            self.report({'INFO'}, output[:200])
        else:
            props.status_message = f"Refine failed: {output[:80]}"
            self.report({'ERROR'}, output[:200])

            # Auto-fix
            if props.auto_fix:
                fixed, final_code, attempts = AutoFixEngine.fix_and_retry(
                    props.prompt, code, output, api, conv
                )
                if fixed:
                    props.last_code = final_code
                    props.status_message = f"Auto-fixed ({attempts} attempts)"

        stats = _cost_tracker.get_totals()
        logger.info("Refined objects: %s", [o.name for o in selected])
        return {'FINISHED'}


class AMA_OT_MultiPassGenerate(Operator):
    """Generate a complex model in multiple AI passes (base → detail → material)"""
    bl_idname = "ama.multi_pass_generate"
    bl_label = "Multi-Pass Generate"
    bl_description = "Generate high-quality model with 3 AI passes: base shape, detail, material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ama_props

        if not props.prompt.strip():
            self.report({'WARNING'}, "Enter a prompt first")
            return {'CANCELLED'}

        api = get_api_engine()
        conv = get_conversation()

        passes = [
            ("BASE SHAPE", "Create the base geometry with correct proportions. Focus on the overall form. Use simple primitives and extrude. Don't add detail yet — just get the shape right."),
            ("DETAIL", "Now add geometric detail: bevels, insets, extrusions, decorative elements. Use bmesh to add edge loops and refine the shape. Add any secondary parts (rivets, trim, ornaments)."),
            ("MATERIAL & POLISH", "Assign proper PBR materials to each part. Add surface detail via noise→bump nodes. Apply smooth shading to organic parts. Recalculate normals. Remove doubles. Final quality pass."),
        ]

        for pass_name, pass_instruction in passes:
            pass_prompt = f"""
===== MULTI-PASS GENERATION — {pass_name} =====
Original request: {props.prompt}

This is pass {passes.index((pass_name, pass_instruction)) + 1} of 3.
{pass_instruction}

Existing scene objects:
{SceneContextGenerator.generate()}

IMPORTANT: Build on what already exists. If objects are already in the scene, modify them.
Do NOT create duplicate objects. Use bmesh to edit existing meshes when possible.
"""

            conv.add("user", pass_prompt)
            result = api.chat(conv.get_messages(), system_prompt=SYSTEM_PROMPT)

            if result["error"]:
                props.status_message = f"Pass '{pass_name}' failed: {result['error'][:80]}"
                self.report({'ERROR'}, result["error"][:200])
                return {'CANCELLED'}

            raw = result["content"]
            code = SecurityValidator.clean_response(raw)
            conv.add("assistant", raw)

            # Execute
            is_safe, reason = SecurityValidator.validate(code)
            if not is_safe:
                props.status_message = f"Security blocked at {pass_name}"
                self.report({'ERROR'}, f"Security: {reason}")
                return {'CANCELLED'}

            success, output = CodeExecutor.execute(code)
            if not success:
                logger.warning("Multi-pass '%s' error: %s", pass_name, output[:200])
                # Continue to next pass even if this one partially failed
                conv.add("system", f"Pass '{pass_name}' had error: {output[:200]}. Continue with next pass.")

            props.status_message = f"Pass {passes.index((pass_name, pass_instruction)) + 1}/3: {pass_name} done"
            context.area.tag_redraw()

        # Final post-processing
        PostProcessor.process_all()

        props.status_message = "Multi-pass generation complete!"
        self.report({'INFO'}, "3-pass generation complete")
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
        bpy.ops.mesh.normals_make_consistent(inside=False)
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
            bpy.ops.mesh.normals_make_consistent(inside=False)
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


# ============================================================================
#  UI Panels
# ============================================================================

class AMA_PT_MainPanel(Panel):
    """Main sidebar panel"""
    bl_label = "AI Modeling Assistant"
    bl_idname = "AMA_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        # Prompt
        layout.prop(props, "prompt", text="", icon='OUTLINER_OB_FONT')

        # AI generation buttons
        row = layout.row(align=True)
        row.operator("ama.send_to_ai", text=t("send"), icon='PLAY')
        row.scale_y = 1.2

        row2 = layout.row(align=True)
        row2.operator("ama.execute_code", text=t("execute"), icon='CHECKMARK')
        row2.operator("ama.refine_object", text=t("refine"), icon='MODIFIER')

        row3 = layout.row(align=True)
        row3.operator("ama.multi_pass_generate", text=t("multi_pass"), icon='MESH_DATA')
        row3.operator("ama.post_process", text=t("post_process"), icon='BRUSH_DATA')

        # Status
        if props.status_message:
            box = layout.box()
            box.label(text=props.status_message[:80], icon='INFO')

        # Think
        if props.last_think:
            box = layout.box()
            box.label(text="AI Thinking:", icon='LIGHT')
            for line in props.last_think[:200].split("|"):
                if line.strip():
                    box.label(text=line.strip()[:60])

        # Options
        row = layout.row()
        row.prop(props, "auto_fix")
        row.prop(props, "show_scene_context")

        # Cost info
        stats = _cost_tracker.get_totals()
        row = layout.row()
        row.label(text=f"Tokens: {stats['total_tokens']} | ${stats['cost']:.4f}", icon='SCRIPTPLUGINS')


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


class AMA_PT_CodeEditorPanel(Panel):
    """Code editor panel - view, edit, and run AI-generated code"""
    bl_label = "Code Editor"
    bl_idname = "AMA_PT_code_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        if props.last_code:
            lines = props.last_code.strip().split('\n')
            box = layout.box()
            box.label(text=f"{len(lines)} lines | {len(props.last_code)} chars", icon='TEXT')

            # Preview first 10 lines
            for i, line in enumerate(lines[:10]):
                row = box.row()
                row.scale_y = 0.7
                row.label(text=f"{i+1:3d}│ {line[:50]}")
            if len(lines) > 10:
                box.label(text=f"    ... +{len(lines)-10} more lines")

            # Editable code box
            layout.prop(props, "last_code", text="")

            row = layout.row(align=True)
            row.operator("ama.code_edit_execute", text="Run Code", icon='PLAY')
            row.operator("ama.execute_code", text="Run Original", icon='PLAY')
        else:
            layout.label(text="No code yet. Use Quick Build or send a prompt.", icon='INFO')


class AMA_PT_APISettingsPanel(Panel):
    """API Settings panel"""
    bl_label = "API Settings"
    bl_idname = "AMA_PT_api_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Model"
    bl_parent_id = "AMA_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ama_props

        layout.prop(props, "api_preset")

        if props.api_preset == "custom":
            layout.prop(props, "api_url")
            layout.prop(props, "api_key")
            layout.prop(props, "model")
        else:
            layout.label(text=f"URL: {props.api_url[:50]}", icon='URL')
            layout.label(text=f"Model: {props.model}", icon='MESH_MONKEY')

        layout.prop(props, "temperature")
        layout.prop(props, "max_tokens")
        layout.prop(props, "include_history")
        layout.prop(props, "max_history_tokens")

        # Cost
        stats = _cost_tracker.get_totals()
        box = layout.box()
        box.label(text=f"Prompt tokens: {stats['prompt_tokens']}")
        box.label(text=f"Completion tokens: {stats['completion_tokens']}")
        box.label(text=f"Total cost: ${stats['cost']:.6f}")
        box.label(text=f"Requests: {stats['requests']}")
        layout.operator("ama.reset_cost", text="Reset Cost", icon='LOOP_BACK')


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
            icon = 'USER' if role == 'user' else 'ROBOT' if role == 'assistant' else 'SETTINGS'
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
        col.operator("ama.extrude_selected", icon='EXTRUDE_REGION')
        col.operator("ama.bevel_selected", icon='MOD_BEVEL')
        col.operator("ama.inset_selected", icon='FACESEL')
        col.operator("ama.loop_cut", icon='KNIFE')
        col.operator("ama.subdivide_mesh", icon='SUBDIVIDE_EDGES')
        col.operator("ama.merge_by_distance", icon='AUTOMERGE_ON')

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Shading & Normals:", icon='SHADING_RENDERED')
        col.operator("ama.recalculate_normals", icon='NORMALS_FACE')
        col.operator("ama.smooth_shading", icon='SHADING_SMOOTH')
        col.operator("ama.flat_shading", icon='SHADING_FLAT')

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


# ============================================================================
#  Class Registration
# ============================================================================

ALL_CLASSES = [
    # Properties
    AMA_Properties,
    AMA_AddonPreferences,

    # Operators
    AMA_OT_SendToAI,
    AMA_OT_QuickBuild,
    AMA_OT_CodeEditExecute,
    AMA_OT_ExecuteCode,
    AMA_OT_ClearHistory,
    AMA_OT_ResetCost,
    AMA_OT_ApplyMaterial,
    AMA_OT_ApplyModifier,
    AMA_OT_GenerateLOD,
    AMA_OT_AnalyzeMesh,
    AMA_OT_QualityCheck,
    AMA_OT_FixObject,
    AMA_OT_CreateRig,
    AMA_OT_UVUnwrap,
    AMA_OT_BakeNormals,
    AMA_OT_WalkCycle,
    AMA_OT_BreathingAnim,
    AMA_OT_CameraOrbit,
    AMA_OT_GenerateTerrain,
    AMA_OT_GenerateTree,
    AMA_OT_ScatterObjects,
    AMA_OT_BatchRename,
    AMA_OT_BatchExport,
    AMA_OT_EngineExport,
    AMA_OT_SceneSnapshot,
    AMA_OT_SceneVersionsList,
    AMA_OT_SelectByMaterial,
    AMA_OT_SelectNonManifold,
    AMA_OT_SelectLoose,
    AMA_OT_CleanupEmpty,
    AMA_OT_RegisterAsset,
    AMA_OT_SearchAssets,
    AMA_OT_ApplyTemplate,
    AMA_OT_AssemblyLayout,
    AMA_OT_AssemblyAlign,
    AMA_OT_RefineObject,
    AMA_OT_MultiPassGenerate,
    AMA_OT_PostProcess,
    AMA_OT_ExtrudeSelected,
    AMA_OT_BevelSelected,
    AMA_OT_InsetSelected,
    AMA_OT_LoopCut,
    AMA_OT_SubdivideMesh,
    AMA_OT_MergeByDistance,
    AMA_OT_RecalculateNormals,
    AMA_OT_SmoothShading,
    AMA_OT_FlatShading,
    AMA_OT_ApplyAllModifiers,
    AMA_OT_DuplicateSymmetry,

    # Panels
    AMA_PT_MainPanel,
    AMA_PT_QuickBuildPanel,
    AMA_PT_CodeEditorPanel,
    AMA_PT_APISettingsPanel,
    AMA_PT_HistoryPanel,
    AMA_PT_MaterialsPanel,
    AMA_PT_ModifiersPanel,
    AMA_PT_MeshEditPanel,
    AMA_PT_TemplatesPanel,
    AMA_PT_LODPanel,
    AMA_PT_MeshAnalysisPanel,
    AMA_PT_RiggingPanel,
    AMA_PT_UVPanel,
    AMA_PT_BakePanel,
    AMA_PT_AnimationPanel,
    AMA_PT_ProceduralPanel,
    AMA_PT_BatchPanel,
    AMA_PT_ScenePanel,
    AMA_PT_VersionsPanel,
    AMA_PT_SelectPanel,
    AMA_PT_CleanupPanel,
    AMA_PT_ExportPanel,
    AMA_PT_AssetsPanel,
]


def register():
    for cls in ALL_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            logger.warning("Failed to register %s: %s", cls.__name__, e)

    bpy.types.Scene.ama_props = PointerProperty(type=AMA_Properties)
    logger.info("AI Modeling Assistant registered successfully")


def unregister():
    del bpy.types.Scene.ama_props

    for cls in reversed(ALL_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning("Failed to unregister %s: %s", cls.__name__, e)

    logger.info("AI Modeling Assistant unregistered")


if __name__ == "__main__":
    register()
