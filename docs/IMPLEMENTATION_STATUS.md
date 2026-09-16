# Implementation state

## Completed baseline: Expert Studio 3.0

The original repository was cloned at `3e0e01f` into the current workspace. Work is
on `codex/studio-refactor`; no GitHub publication has been performed. The monolith is
replaced by 41 Python modules, asynchronous provider processes, typed expert plans,
review/repair/failure states, media import and source-preserving export. Model APIs
are exercised with loopback fixtures, not paid credentials. The installed host is
Windows / Blender 5.1.1. Legacy and real extension installation smoke tests pass.
The HELIO offline example, render, animated GLB and .blend are in `artifacts/demo`.

Core/protocol/package tests: 38 passed before the platform expansion. Blender suite
has since gained provider routing coverage; rerun it after subsequent changes.
Old-version downloads failed (403/TLS/redirect errors), so 3.6/4.x remain unverified
compatibility paths, with a future CI matrix. Original single-file add-on was removed.

## User's expanded acceptance requirements

No further clarification questions: the one permitted question round was completed.
The new scope is a real persistent agent platform, including multi-turn conversation,
semantic context compression, short/long/project memory and intelligent versioned
memory evolution, personalization, proactive assistance, multimodal inputs and
outputs, complex hierarchical multi-agent planning, multiple concurrent workflows,
mandatory evidence-based quality checks, sketch input and precise human editing.

## Implemented platform expansion: 3.1

The expansion now includes core/memory.py, context.py and attachments.py; persistent
Blender dialogue and memory review UI; native sketch and region capture; SceneJob and
scene_worker.py isolated execution; native quality contracts and rendered previews;
parallel independent task lanes and multiple production workflows; local proactive
checks; source-bound memory evolution; Bridge v2 uploads; backup/erasure and explicit
checkpoint recovery. Detailed operating behavior is in PLATFORM_GUIDE.md.

Blender integration reached 32 passing tests before final packaging. The final counts,
artifact/install checks and verification boundaries are maintained in VALIDATION.md.
No real paid model credentials, other Blender versions or actual freehand viewport
capture have been validated. Complex external datablock conflict detection, final PBR
visual scoring, arbitrary vendor adapters and an OS-level sandbox are not claimed.

## Original expansion sequence (now implemented within documented bounds)

1. Specify memory provenance, scope isolation, conflict resolution and evolution;
   implement persistent conversations and a tested SQLite memory service.
2. Integrate asynchronous semantic compression/extraction and retrieval into actual
   multi-turn model requests; expose chat, project identity and memory inspection.
3. Add multimodal attachments and native sketch/viewport capture, with explicit
   provider capabilities and bridge upload contracts.
4. Introduce task contracts, project/asset revisions and isolated Blender execution
   workspaces; validate human-edit conflicts before committing generated changes.
5. Enforce native and model/human quality gates, repair loops and evidence-backed
   export decisions; store gate outcomes in run and memory provenance.
6. Support bounded independent tasks/workflows with serialized scene commits,
   resource budgets and cancellation, plus non-destructive proactive suggestions.
7. Verify failure/repair/conflict/memory/concurrency workflows; rebuild installers,
   documentation, examples and final validation records.

Do not claim universal model availability, expert-level visual quality, transactional
rollback of unrestricted Python, or cross-version compatibility without evidence.
Do not spawn development sub-agents: the user's agent-cluster requirements refer to
the product. Persistent Python threads remain prohibited inside the Blender process.
