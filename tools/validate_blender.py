"""Run source, ZIP installation and manifest checks with isolated Blender profiles.

Usage: python tools/validate_blender.py --blender /path/to/blender
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build import build
from ai_modeling_assistant.core.artifacts import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", required=True, type=Path)
    args = parser.parse_args()
    blender = args.blender.resolve()
    archive = build(ROOT / "dist")[1]
    profile = ROOT / "artifacts" / "validation" / ("install-" + uuid.uuid4().hex[:8])
    profile.mkdir(parents=True)
    env = dict(
        os.environ,
        BLENDER_USER_CONFIG=str(profile / "config"),
        BLENDER_USER_SCRIPTS=str(profile / "scripts"),
        BLENDER_USER_EXTENSIONS=str(profile / "extensions"),
        AI_IN_BLENDER_MEMORY_DB=str(profile / "memory.sqlite3"),
        PYTHONIOENCODING="utf-8",
    )
    steps = []

    def run(name, arguments):
        log = profile / (name + ".log")
        with log.open("wb") as output:
            result = subprocess.run(
                [str(blender), "--background", "--factory-startup", *arguments],
                cwd=ROOT,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=600,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        steps.append({"name": name, "returncode": result.returncode, "log": str(log)})
        atomic_json(profile / "checks.json", steps)
        if result.returncode:
            print(log.read_text(encoding="utf-8", errors="replace")[-10000:])
            raise RuntimeError(name + " failed; see " + str(log))
        print(name + ": passed", flush=True)

    run("integration", ["--python-exit-code", "1", "--python", "tests/blender_integration.py"])
    run("legacy-install", ["--python-exit-code", "1", "--python", "tests/install_smoke.py"])
    run("extension-install", ["--python-exit-code", "1", "--python", "tests/extension_install.py"])
    metadata = json.loads((profile / "version.json").read_text())
    if tuple(metadata["version"]) >= (4, 2, 0):
        run("manifest", ["--command", "extension", "validate", str(archive)])
    print("VALIDATION_OK", profile)


if __name__ == "__main__":
    main()
