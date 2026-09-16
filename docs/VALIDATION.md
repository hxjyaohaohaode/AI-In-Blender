# Local validation evidence

Version under validation: **3.1.0**. Original repository baseline: `3e0e01f`.
Working branch: `codex/studio-refactor`. Local refactor; no GitHub publication.

## Environment

- Windows, Blender **5.1.1**, build `b70da489d7f4`.
- Executable: `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`.
- Bundled Python 3.13: `C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe`.
- SQLite 3.50.4 available in Blender's bundled Python; no runtime third-party packages.
- The machine's unrelated Python 3.12 installation lacks `_sqlite3`; tests use Blender's bundled interpreter.

## Checks

Final results are recorded in `artifacts/validation/final-results.json` and the associated logs.
The completed local suites contain **53 pure/protocol/package tests** and **33 real
Blender integration tests**. The final result file also records lint, manifest,
installation and Python 3.10 syntax checks, with installer hashes.
Run this validation from the repository root with a normal Python including SQLite:

```text
python -m unittest discover -s tests -p test_*.py -v
blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py
python tools/build.py
blender --background --factory-startup --command extension validate dist/ai-in-blender-3.1.0-extension.zip
```

Pure tests cover guarded code, bounded context, source-backed memory, scope isolation,
conflicts, optimistic revision updates, expiry, forgetting/backup, immutable attachments,
real HTTP subprocesses, conditioned upload, cancellation, errors and package layout.

The Blender suite covers the 16 quick builds, 30 material presets, every panel draw,
legacy key migration, provider routing, four export formats, safe code failure,
planning through export, bounded repair, real media imports and UI registration.
Platform cases cover persistent multi-turn dialogue, actual model-based compression,
parallel part assembly, two simultaneous workflows, retained successful checkpoints,
human edit conflicts, edit-mode deferral, out-of-region edits, native bounds/anchor
gates, process deadlines, Grease Pencil creation, image-backed review and invalidation
of visual approval after an edit. Model responses come from a loopback fixture server.

Legacy and extension installation tests run against project-local isolated Blender
configuration/scripts/extension directories under `artifacts/`; they do not change the
user's normal installation. The extension smoke test also exercises its packaged HTTP
worker and isolated scene worker from the actual installed extension namespace.

## Inspectable artifacts

- `dist/ai-in-blender-3.1.0-extension.zip`, `dist/ai-in-blender-3.1.0-legacy.zip`.
- `dist/SHA256SUMS.txt` contains deterministic package checksums.
- `artifacts/demo/HELIO.blend`, `HELIO.glb`, `HELIO.png`, `run.json`: real procedural
  scene, materials, armature-driven animation, rendered preview and export.
- `artifacts/validation/`: unit, host integration, install and manifest validation logs.
- `artifacts/extension-smoke-3.1/runs/`: actual installed-extension branch output and preview.

The HELIO example is an offline procedural asset, not the output of a paid AI service.
The test server is not a production model bridge.

## What these results do not establish

Blender 3.6/4.x code paths and a Linux matrix are provided but have not been executed
locally. Attempts to fetch older releases failed; no cross-version pass is claimed.
The CI workflow is not run until the repository is published/executed on GitHub.
Grease Pencil object creation is tested in Blender; actual interactive drawing and
OpenGL viewport screenshot experience are not tested by the headless suite.

No live paid LLM, Meshy, video, voice or world service was invoked. Actual credentials,
provider availability and generation quality need service-level validation. Bridge v2
requires a real adapter implementation for the chosen model. Automated checks establish
specified structural invariants and workflow behavior, not universal expert artistry.
Complex Geometry Nodes/external image/driver changes are not claimed perfectly
fingerprinted. The process boundary is not an operating-system security sandbox.
