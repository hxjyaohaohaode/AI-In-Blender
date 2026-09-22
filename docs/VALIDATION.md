# Reproducible validation: 3.3.0

Original baseline: `3e0e01f`. First published candidate: `207cfc8`. The initial
GitHub failure was seven Blender 3.6 material-preset fallbacks raising `NameError`
for an unavailable `KeyError`. The regression test now explicitly exercises that
fallback on every version, and the preset suite still exercises the actual nodes.

The expanded matrix also exposed Blender 3.6's shared UV storage after `Mesh.copy()`.
The region regression now uses a real isolated candidate and asserts that the source
UVs remain unchanged. Direct execution rollback keeps independent UV value buffers.
Both cases were reproduced and passed on the official Windows 3.6.23 portable build.

## Run all checks

Use a Python installation that includes SQLite. On the development Windows host,
Blender 5.1's bundled Python works; the unrelated system Python lacks `_sqlite3`.

```sh
python -m pip install ruff==0.16.7
ruff check ai_modeling_assistant tests tools
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/validate_blender.py --blender /absolute/path/to/blender
```

`validate_blender.py` builds both ZIPs, runs the source integration suite, installs
the legacy ZIP, installs and exercises the actual extension namespace on Blender
4.2+, and validates the manifest. It creates isolated configuration, scripts and
extensions and independently built packages under `artifacts/validation/install-<id>`.
Concurrent version validators never overwrite a shared package. Its `checks.json` records each
exit code and log. The integration suite writes `blender-<version>.json` with test
counts, exceptions and success. A failing test or installation fails the command.

## CI matrix and evidence

- Core: Windows, Ubuntu and macOS Apple silicon, Python 3.10 and 3.13, pinned Ruff.
- Blender: Linux 3.6.23, 4.2.23, 4.5.14, 5.1.2 and 5.2.2; verified official download hashes.
- Blender: macOS Apple silicon 5.2.2, official DMG and verified SHA-256.
- Legacy installation: every Blender matrix entry.
- Real extension installation and packaged workers: every Blender matrix entry from 4.2 onward.
- Host baselines: Windows Blender 3.6.23 (`e467db79ca8c`), 5.1.1 (`b70da489d7f4`)
  and 5.2.2 (`d13f752e3b9c`), with real legacy installs and extension installs where applicable.
- Blender suite: 67 integration cases plus the quick-build/material subcases.
- Core suite: 85 tests covering memory, execution contracts, network protocols, GLB and packages.

Use [Actions](https://github.com/hxjyaohaohaode/AI-In-Blender/actions) for the result
of a specific commit. Matrix logs and package archives are uploaded as artifacts.
The 3.3 local audit is `artifacts/validation/audit-3.3-results.json`; ignored artifacts
are not source-controlled. A matrix definition by itself is not a pass certificate.

## Failure cases covered

- Guarded imports, exception fallbacks, timeout, cancellation and secret redaction.
- Real multi-turn history, Chinese budget pressure, complete-turn source coverage,
  image/output reservations and explicit omission reporting.
- Memory isolation, scope precedence, candidate authority, conflict resolution,
  revision races, evidence consolidation, expiry, suppression after forgetting,
  historical episode retrieval and project erasure.
- Dependency errors, contradictory bounds, independent branch failure, retained
  successful steps, derived-result invalidation and remote GET-only recovery.
- All quick builds and material presets, panel/operator registration, four export
  formats, actual image/video/audio/model imports and import compensation.
- Evaluated modifier geometry, required-object contracts, inherited export gates,
  asset tampering, frame/unit conflicts, weights/attributes, scoped UV edits,
  explicit external object dependencies and stale visual approval.
- Parallel parts, separate workflows, bounded repair followed by independent
  re-review, persistent call budgets, scene process deadlines and checkpoint recovery.
- Reproducible package layouts and actual installed-worker execution.
- Blender 5.2 Geometry Nodes inputs; camera focus dependencies; color ramps and
  repeated image painting; protected generic attributes; source-frozen audio input.
- Material output/texture dependencies, collapsed UVs, real Cycles evidence, bound
  action/shape-key animation, temporal bounds and restoration of the active subframe.
- Explicit world/camera/scene setting commits and refusal to silently lose unsupported
  render/compositor/sequencer changes; native `.blend` scene delivery.
- GLB structure/embedded dependencies, buffer/accessor bounds and preservation of an
  existing delivery after validation failure.
- Transactional v2-to-v3 memory migration, stale compaction after forgetting, immutable
  execution event history, full history export and 10,012-turn context/compaction.
- Terrain resolution, evaluated sloped-surface scatter and local random-state isolation.

## Limits of this evidence

Local HTTP fixtures exercise network protocols and byte transfers; they do not
measure paid model availability or generated artistic quality. Evidence includes
Workbench geometry, bounded Cycles CPU studio material previews and finite animation
samples, not final lighting or exhaustive animation quality. Interactive drawing/capture
needs manual GUI verification. Unlisted Blender versions/platforms are not claimed
tested. A declared matrix must have a successful run on the exact commit before it
counts as verification. The process boundary is not an OS security sandbox. See
[workflow contracts](WORKFLOW_LIFECYCLES.md) for recovery limits and invariants.
