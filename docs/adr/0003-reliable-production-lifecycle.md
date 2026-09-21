# ADR 0003: Enforce production invariants at execution boundaries

Status: accepted for implementation under the user's request to optimize and submit.

## Problem and evidence

The first GitHub matrix failed seven Blender 3.6 preset subtests: compatibility
fallbacks caught KeyError, which was missing from the restricted builtins. Local
5.1 tests had never exercised those branches. The broader audit also found that
summary input budgets, recovery integrity, independent failure scheduling and
inherited acceptance criteria were not enforced consistently.

## Decisions

1. Keep a modular local application, SQLite and external provider/Blender processes.
   Avoid a distributed service dependency for a single-user desktop plugin.
2. Treat conversation originals, compressed coverage, verified memory, conflicting
   proposals and execution episodes as separate records. A compression checkpoint
   may advance only over complete supplied turns. Every model request, including
   maintenance, planning, repairs and images, must pass the same input budget gate.
3. Memory retrieval resolves scope precedence (session, project, personal), includes
   relevant constraints, explains selection and surfaces unresolved corrections.
   Repeated evidence is consolidated without silently verifying a model proposal.
   Forget/reject suppresses exact automatic re-proposals; project erasure cascades.
4. Schedule by dependency readiness and write ownership. Failures block descendants,
   not unrelated branches. Persist calls before dispatch and remote job receipts
   before polling. Recovery validates saved artifacts and refuses ambiguous replay.
5. Quality contracts are checked on evaluated candidate geometry and again on the
   final version before export. Part contracts apply to their own stable asset IDs.
   A dependency change invalidates all dependent outputs. Acceptance is evidence,
   not the model's self-reported completion flag.
6. Human edits win conflicts. Protect timeline, units, topology, materials, weights,
   UVs and object references, including unselected regions. Scene copies are process
   isolation, not an OS security sandbox. Unsupported external object dependencies
   must be brought into the explicit scope before editing.
7. CI validates actual install packages and source on every supported Blender series.
   Publish only after the candidate commit has passed the remote matrix. Preserve
   failures and reports; never turn failing checks into unconditional success.

## Trade-offs and limits

Strict budget and scope checks may stop a task and ask for a smaller input; silently
dropping a requirement would be worse. Lexical multilingual retrieval is auditable
and works offline; it is not an embedding model. Native checks cannot establish
artistic correctness, so render evidence and explicit visual review remain separate.
No exactly-once guarantee is claimed across a remote service that lacks idempotency:
an uncertain submission is visible and blocked from blind replay. Provider protocols
are integration contracts, not a claim that every vendor or world model is tested.

## Acceptance

Regression tests cover the reported 3.6 exception fallback, multilingual long context,
oversized maintenance calls, correction/expiry/forget cycles, cross-project isolation,
independent failures, invalid and contradictory contracts, stale inputs, artifact
tampering, uncertain recovery and scene edit conflicts. Installation, lint, package
reproducibility and the Blender version matrix are release gates. See VALIDATION.md
for measured results and the distinction between fixture and live-provider evidence.
