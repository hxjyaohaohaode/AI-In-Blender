"""Build reproducible legacy and extension ZIPs without bundling tests or secrets."""

import argparse
import ast
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "ai_modeling_assistant"


def version():
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    assignment = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "bl_info" for t in n.targets)
    )
    return ".".join(map(str, ast.literal_eval(assignment.value)["version"]))


def build(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    outputs = []
    for kind in ("legacy", "extension"):
        path = destination / f"ai-in-blender-{version()}-{kind}.zip"
        with zipfile.ZipFile(
            path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            files = [
                p
                for p in PACKAGE.rglob("*")
                if p.is_file() and p.suffix == ".py" and "__pycache__" not in p.parts
            ]
            if kind == "extension":
                files.append(PACKAGE / "blender_manifest.toml")
            for file in sorted(files):
                name = file.relative_to(PACKAGE).as_posix()
                if kind == "legacy":
                    name = "ai_modeling_assistant/" + name
                info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, file.read_text(encoding="utf-8").encode("utf-8"))
            extras = ["README.md", "README_EN.md", "LICENSE"]
            extras += [
                p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs").rglob("*.md"))
            ]
            for filename in extras:
                if (ROOT / filename).is_file():
                    name = ("ai_modeling_assistant/" if kind == "legacy" else "") + filename
                    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    archive.writestr(
                        info, (ROOT / filename).read_text(encoding="utf-8").encode("utf-8")
                    )
        outputs.append(path)
    (destination / "SHA256SUMS.txt").write_text(
        "".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in outputs),
        encoding="ascii",
        newline="\n",
    )
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    for artifact in build(args.output):
        print(artifact)
