# ADR 0004: Evidence-bound delivery on Blender 5.2

Status: accepted for 3.3.0. Supersedes implementation details, not the invariants, of ADR 0003.

## Problem

An object-only revision misses timeline and presentation changes. A successful script
can change global settings that never return from an isolated process. Existing UV
layers, action containers and material slots are insufficient quality evidence. A GLB
file may exist while losing native Blender shading, and latest-result memory can erase
the reason a repair was needed. Limited history queries must not define summary coverage.

## Decision

1. Keep object revisions and add a delivery revision covering scene settings. Bind
   approvals and cold recovery to this revision. Fingerprint nested GN RNA, color ramps,
   curve mappings and loaded image pixels. This costs proportional time and memory for
   large textures; it avoids caching stale mutable image state.
2. Introduce explicit serialized scene-setting ownership. Part tasks cannot own global
   settings. Transfer the supported whitelist plus world/camera references, validate in
   a disposable scene, then commit after source conflict checks. Library input paths are
   made absolute so moving a branch does not reinterpret relative texture paths.
3. Separate native geometry/material/animation gates from visual evidence. Check actual
   action slots and evaluate bounded frame samples. Require finite, noncollapsed UVs and
   usable material dependencies when contracted. Return measured failures, not scores
   invented by the language model.
4. Produce CPU Cycles studio evidence for material contracts and labeled animation
   samples. Keep Workbench geometry views. These are bounded diagnostic renders, not final
   beauty renders. Preserve evidence type and actual number of images sent to a reviewer.
5. Validate the generated GLB before atomic replacement and preserve a native `.blend`
   alongside it. Native external dependencies are references unless already packed.
   A failed exporter leaves an existing delivery file intact.
6. Transactionally migrate memory to schema 3, retaining append-only episode events.
   Explicit memory edits advance an epoch that invalidates in-flight compaction. Retrieve
   required pinned constraints completely or stop on budget failure. Store coverage IDs
   locally, transmit only actual source references, and compact the oldest uncovered
   prefix independently of the recent dialogue window. Full project exports are not
   bounded by retrieval limits.
7. Test official 5.2.2 builds, active LTS patches and historical compatibility baselines.
   Include Windows local tests, Linux version-matrix CI and macOS Apple silicon CI. Build
   independent installation artifacts per validator so concurrent validation cannot race.

## Consequences and boundaries

Structural enforcement, process isolation and evidence provenance improve reliability;
they do not provide an OS sandbox or a guarantee of arbitrary model quality. Finite
temporal samples can miss between-sample defects. Complex shader fidelity in GLB needs
baking outside this change. The scene whitelist excludes compositor/VSE/custom renderer
settings and simulation caches. Future Blender releases still need version-specific
verification. Older v3.2 checkpoints without a delivery revision require fresh validation;
newer memory databases are refused by older add-ons rather than silently downgraded.
