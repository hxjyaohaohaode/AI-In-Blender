"""data / catalog — extracted from the original add-on."""

from typing import Any
from typing import Dict
from typing import List
from typing import Tuple


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


LOD_LEVELS: List[Tuple[str, float]] = [
    ("LOD0_Full", 1.0),
    ("LOD1_High", 0.5),
    ("LOD2_Medium", 0.25),
    ("LOD3_Low", 0.1),
    ("LOD4_Billboard", 0.05),
]


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
