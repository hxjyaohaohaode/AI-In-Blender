"""Create a reviewable .blend, animated .glb and still preview in artifacts/demo."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bpy
import ai_modeling_assistant
from ai_modeling_assistant.blender.demo import build_demo, setup_presentation

ai_modeling_assistant.register()
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
folder = ROOT / 'artifacts/demo'
collection, _ = build_demo(bpy.context.scene, folder)
setup_presentation(bpy.context.scene)
bpy.context.scene.render.filepath = str(folder / 'HELIO.png')
bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'HELIO.blend'))
bpy.ops.render.render(write_still=True)
print('DEMO_OUTPUT', folder)
