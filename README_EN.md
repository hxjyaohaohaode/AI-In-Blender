> [中文](README.md) | English

# AI in Blender · Agent Platform 3.1

A persistent Blender agent platform with multi-turn dialogue, source-backed memory,
multimodal references, concurrent independent experts and checked scene branches.
Architect agents plan assembly contracts; specialist models produce parts and media;
the host validates outputs and protects human edits before serial scene commits.
It provides measurable production controls, not guaranteed aesthetic quality or
native integration with every vendor.

## Features

- Planner, modeling, material, rigging, animation and review roles, geometry inspection and export.
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

- `dist/ai-in-blender-3.1.0-extension.zip`: Blender 4.2+, Get Extensions → Install from Disk.
- `dist/ai-in-blender-3.1.0-legacy.zip`: Blender 3.6+, Add-ons → Install / Install from Disk.

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

Windows/Blender 5.1.1 is actually tested. Blender 3.6 and 4.x compatibility branches
and a Linux CI matrix are included; unexecuted matrix entries are not proof of support.
Versions before 3.6 are unsupported. See [validation](docs/VALIDATION.md).

No paid live model calls were used. Native adapters use local HTTP fixtures for
verification; real service availability and generation quality require credentials
and service-level validation. Video/world engines require a server implementing the
[bridge contract](docs/PROVIDERS.md). World outputs are imported assets, not a generic
world simulation runtime. A Vision reviewer receives a real Workbench geometry preview;
a text-only reviewer does not claim image inspection. Workbench evidence does not prove
final PBR lighting, texture fidelity or every animation frame. Bridge v2 uploads actual
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
