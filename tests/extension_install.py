"""Install a real extension ZIP in a local repository, then test its private workers."""

import json
import os
from pathlib import Path
import runpy
import bpy

root = Path(__file__).resolve().parents[1]
expected = Path(os.environ["BLENDER_USER_EXTENSIONS"]).resolve()
assert root / "artifacts" in expected.parents
expected.mkdir(parents=True, exist_ok=True)
(expected.parent / "version.json").write_text(json.dumps({"version": list(bpy.app.version)}))
if bpy.app.version >= (4, 2, 0):
    archives = sorted((root / "dist").glob("*-extension.zip"))
    # build.py version is obtained without importing any source add-on modules;
    # the smoke test must import exclusively from the installed namespace.
    import ast

    tree = ast.parse((root / "ai_modeling_assistant/__init__.py").read_text(encoding="utf-8"))
    info = next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "bl_info" for t in n.targets)
    )
    version = ".".join(map(str, info["version"]))
    archive = root / "dist" / f"ai-in-blender-{version}-extension.zip"
    assert archive in archives
    bpy.ops.preferences.extension_repo_add(
        name="studio_smoke",
        type="LOCAL",
        use_custom_directory=True,
        custom_directory=str(expected / "studio_smoke"),
        use_sync_on_startup=False,
    )
    repo = next(
        r
        for r in bpy.context.preferences.extensions.repos
        if Path(r.directory).resolve() == expected / "studio_smoke"
    )
    assert repo.module == "studio_smoke", repo.module
    result = bpy.ops.extensions.package_install_files(
        filepath=str(archive), repo=repo.module, enable_on_install=True
    )
    assert "FINISHED" in result, result
    runpy.run_path(str(root / "tests/extension_smoke.py"), run_name="__main__")
else:
    print("EXTENSION_NOT_APPLICABLE: Blender older than 4.2; legacy package tested separately")
