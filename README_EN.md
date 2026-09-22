> [中文](README.md) | English

# AI in Blender · Agent Platform 3.3

A persistent Blender agent platform with multi-turn dialogue, source-backed memory,
multimodal references, concurrent independent experts and checked scene branches.
Architect agents plan assembly contracts; specialist models produce parts and media;
the host validates outputs and protects human edits before serial scene commits.
It provides measurable production controls, not guaranteed aesthetic quality or
native integration with every vendor.

## Features

Version 3.3 targets official Blender 5.2.2 LTS while retaining the legacy 3.6 package.
It adapts Geometry Nodes RNA inputs, checks collapsed UVs/material dependencies and
bound animation channels, samples animated geometry, and adds real Cycles CPU material
evidence. Explicit lighting tasks can commit world/camera/presentation settings.
GLB output is checked before replacement, with a native scene delivered alongside it.
Memory v3 retains execution event history, rejects stale compression after memory
edits, and handles conversations exceeding 10,000 turns without skipping the oldest
uncompressed prefix. Terrain resolution and surface scatter now follow their actual
parameters and target geometry. See the [3.3 audit](docs/QUALITY_AUDIT_3_3.md).
See [workflow lifecycles](docs/WORKFLOW_LIFECYCLES.md) and
[validation](docs/VALIDATION.md) for implementation details and evidence boundaries.

- Planner, modeling, material, rigging, animation, lighting/camera and review roles, geometry inspection and export.
- Capability-based routing to different providers and models.
- SQLite projects, multiple persistent conversations, versioned session/project/personal memories.
- Automatic source-linked semantic compression with explicit extractive fallback; raw turns remain intact.
- Model-proposed memory candidates, user-reviewed promotion, conflicts, expiry, provenance, backups and erasure.
- Actual vision image inputs, native Grease Pencil sketches, viewport references and constrained vertex-region editing.
- Up to 24 tasks per workflow, 1–4 independent part lanes and two concurrent workflows.
- Isolated Blender execution with process deadlines, content conflict checks, native gates and preview evidence.
- Mandatory structural checks; default human visual approval bound to the current content revision.
- Read-only proactive local suggestions, explicit checkpoint recovery and model-call budgets.
- Chat Completions, image generation, speech, audio transcription and Meshy text-to-3D adapters.
- An asynchronous jobs bridge for video, world assets and other generation engines.
- Cancellable HTTP workers and independent Blender branch processes; live scene commits stay on the main thread.
- Editable plans, per-script review, bounded code repair, retry of unfinished tasks and run reports.
- Existing quick builds, materials, modifiers, rigging, UV, animation and procedural tools.
- Source-preserving GLB/FBX/OBJ/STL exports and session/environment-based credentials.

## Install

Run `python tools/build.py` and install one ZIP:

- `dist/ai-in-blender-3.3.0-extension.zip`: Blender 4.2+, Get Extensions → Install from Disk.
- `dist/ai-in-blender-3.3.0-legacy.zip`: Blender 3.6+, Add-ons → Install / Install from Disk.

Disable the old single-file add-on before upgrading. No runtime pip dependencies.
Open the **AI Model** sidebar and try **Offline Demo** to create a mechanical asset
with PBR materials, a rigid armature, animation and GLB export. It is a deterministic
bundled example, not a live AI-generated asset.

## Workflow

Configure **Models & Settings** with actual model IDs, URLs and credentials. Profiles
may be assigned to specific experts; otherwise they are capability defaults. Remote
HTTPS is verified, loopback HTTP is supported, and remote services require Blender
Online Access. Keys are kept in memory or a named environment variable. Entered keys
are cleared on file load/disable; legacy stored keys are migrated out of properties.

Enter a brief → **Plan** → review instructions → **Run**. Code review is on by default.
Alternatively, discuss the project in **Conversation & Memory**, then use **Plan from
Conversation**. Memory candidates need review before they influence durable personalization.
Use **Open in Text Editor / Run Edited Code** to edit generated scripts. Use **Edit
Plan / Use Edited Plan** to change the graph. Failures block dependent tasks, and
retry preserves successful work. Generated media appear in the scene or VSE.

Independent root parts with distinct `contract.part_id` use separate branches.
Bounds, anchor positions/tolerances, topology and material/UV requirements can be
checked as task contracts. Inspect the live scene and **View Latest Preview**, then
approve visual quality when requested. Editing content invalidates old approval.

Memory lives in DATAFILES/AIInBlender/platform.sqlite3 or the path selected through
`AI_IN_BLENDER_MEMORY_DB`. It uses scoped lexical retrieval, not an advertised vector
store. Semantic summaries and extraction consume model calls and have separate
switches. Current instructions take precedence over memory. Backups are ordinary
SQLite files; stop the add-on before restoring a backup copy. No application-level
database encryption is claimed. See the detailed [platform guide](docs/PLATFORM_GUIDE.md)
and [design](docs/PLATFORM_DESIGN.md) (Chinese).

## Validation and limits

Local Windows baselines are Blender 3.6.23, 5.1.1 and 5.2.2 LTS. CI covers Linux
3.6.23, 4.2.23, 4.5.14, 5.1.2 and 5.2.2, plus macOS Apple silicon 5.2.2.
Core tests run on Windows, Linux and macOS with Python 3.10/3.13.
Consult the exact commit's Actions results; an unexecuted matrix is not proof of support.
Versions before 3.6 are unsupported. See [validation](docs/VALIDATION.md).

No paid live model calls were used. Native adapters use local HTTP fixtures for
verification; real service availability and generation quality require credentials
and service-level validation. Video/world engines require a server implementing the
[bridge contract](docs/PROVIDERS.md). World outputs are imported assets, not a generic
world simulation runtime. Vision review receives budgeted real previews, with Cycles
studio material views for material contracts and labeled frame samples for animation.
Text-only review does not claim image inspection. Finite samples do not prove final
lighting, artistic fidelity or every animation frame. Native `.blend` delivery retains
procedural data that GLB cannot express; unpacked textures/caches remain file references.
Bridge v2 uploads actual
conditioning bytes; native text-only adapters reject unsupported binary attachments.

The Python guard and separate Blender process are **not an OS sandbox**. The process
deadline can terminate stalled native operations without applying a partial branch.
Generated scripts do not receive provider keys. Common mesh/material/animation changes
are fingerprinted; arbitrary complex nodes, external dependencies and third-party
datablocks are not claimed perfectly covered. Precise regions preserve topology and
reject out-of-region vertex changes; they are not a general pixel/video mask editor.
Use trusted providers, inspect results and keep saved scene versions. Local cancellation may not cancel/refund an
accepted remote job. POST requests are not automatically retried. No stale pricing
table is presented as current billing.

## Development

```shell
python -m unittest discover -s tests -v
blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py
python tools/build.py
blender --background --factory-startup --python-exit-code 1 --python tools/render_demo.py
```

The core imports without `bpy`. See [architecture decisions](docs/adr/0002-persistent-agent-platform.md).
License: [GPL-3.0](LICENSE).
