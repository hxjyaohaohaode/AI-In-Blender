# Implementation status: Agent Platform 3.2

The original single-file add-on was replaced on `codex/studio-refactor`. The first
published candidate was `207cfc8`, reviewed in PR #1. Its GitHub Blender 3.6 job failed
seven preset subtests because `KeyError` was missing from restricted builtins.
Version 3.2 fixes that regression and strengthens production lifecycle enforcement.
The expanded 3.6 tests also led to independent UV rollback buffers and a real
isolated-process region regression instead of a UV-sharing in-process mesh copy.

## Implemented and regression-tested mechanisms

- Persistent multi-turn conversations, scoped source-backed memory and SQLite v2
  migration; review/expiry/conflict/forget workflows and execution episodes.
- Complete-turn bounded compaction, source coverage validation, fixed user
  constraints and accounting of maintenance/planning/repair/vision requests.
- Dependency readiness independent of unrelated failures, isolated part lanes,
  per-run call journals, retained successful tasks and checked checkpoint recovery.
- Hashed assets, verified Bridge uploads and GET recovery for known remote jobs;
  ambiguous POST submissions are not blindly replayed.
- Isolated code execution, evaluated candidate validation, inherited contracts,
  region protection for geometry/UV/weights and scene/unit/timeline conflicts.
- Bounded review-repair-review cycles; quality gates and default human approval.
- Media decode/import compensation, traditional and extension package installation,
  normalized deterministic ZIP output, Windows/Linux core and Blender CI matrices.

Full behavior and failure transitions: [WORKFLOW_LIFECYCLES.md](WORKFLOW_LIFECYCLES.md).
Commands and evidence: [VALIDATION.md](VALIDATION.md). Live run status is on the
[repository Actions page](https://github.com/hxjyaohaohaode/AI-In-Blender/actions).

## Verification boundaries

Provider protocols are tested with local HTTP fixtures and real subprocesses. No
claim is made that paid LLM/Meshy/video/voice/world accounts, arbitrary vendor APIs,
or expert artistic quality were validated. Third-party world models need an actual
Bridge implementation. Grease Pencil creation is automated; interactive freehand
drawing and viewport capture still require a GUI acceptance session. Workbench
evidence is geometry preview, not a complete PBR or animation quality assessment.

Compatibility is measured for the versions in CI, not all historical/future Blender
versions. Complex external texture/driver/third-party data semantics are not a
perfectly fingerprinted graph. Generated Python runs in a separate Blender process,
which protects the editing session but is not an operating-system security sandbox.
