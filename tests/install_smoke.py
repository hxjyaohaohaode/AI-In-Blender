"""Legacy ZIP installation smoke test with explicitly isolated Blender user paths."""

from pathlib import Path
import os
import sys
import bpy
import addon_utils

root = Path(__file__).resolve().parents[1]
expected = Path(os.environ["BLENDER_USER_SCRIPTS"]).resolve()
assert root / "artifacts" in expected.parents, "Installer test must use project-local user paths"
actual = Path(bpy.utils.user_resource("SCRIPTS")).resolve()
assert actual == expected, (actual, expected)
sys.path[:] = [entry for entry in sys.path if Path(entry or Path.cwd()).resolve() != root]
import ast

tree = ast.parse((root / "ai_modeling_assistant/__init__.py").read_text(encoding="utf-8"))
info = next(
    ast.literal_eval(n.value)
    for n in tree.body
    if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == "bl_info" for t in n.targets)
)
version = ".".join(map(str, info["version"]))
archive = root / "dist" / f"ai-in-blender-{version}-legacy.zip"
assert "FINISHED" in bpy.ops.preferences.addon_install(filepath=str(archive), overwrite=True)
addon_utils.enable("ai_modeling_assistant", default_set=True)
import ai_modeling_assistant

assert expected in Path(ai_modeling_assistant.__file__).resolve().parents
from ai_modeling_assistant.blender.state import preferences
from ai_modeling_assistant.core.process import python_executable

assert preferences() is not None
assert Path(python_executable()).is_file()
assert hasattr(bpy.context.scene, "ama_props")
assert "FINISHED" in bpy.ops.ama.quick_build(preset_key="sword")
addon_utils.disable("ai_modeling_assistant", default_set=True)
assert not hasattr(bpy.types.Scene, "ama_props")
print("INSTALL_SMOKE_OK", ai_modeling_assistant.__file__)
