# Review of Codex's HMatrix production integration (commit 0be5dc3)

Reviewed: the production change to `tools/GHOST/ghost_backend/compressed/`
(`hmatrix.py`, new `hmatrix_build.py`, `hmatrix_factor.py`) and
`audits/codex-2026-11-17/hmatrix-production-integration/REVIEW_AND_HANDOFF.md`
on `codex/hmatrix-production-integration-2026-11-17`.

I changed no production file. `INDEPENDENT_CHECK_PLAN.md` was written after
reading the production diff and before opening Codex's report, tests or
results. Every run below loads the integrated production tree directly, with
no research hook altering behaviour, and compares it with its parent tree
(`c536f7e`).

## Summary

**I found no defect and support accepting this change.** All six hypotheses in
my plan held.

| Hypothesis | Result |
|---|---|
| H1. Bit-identical results where no storage cap bites | Held on 6 geometries, including 3 material types new to this series |
| H2. Accounted inverse high-water equals final inverse size | Held on all 6 and at 32k |
| H3. No allocation-guard shortfall above 1 MiB | Held: 0 of 3,891 guard entries in 3 audited builds |
| H4. Clean build where the parent retries or fails under a cap | Held at 690 and 650 MiB, and at 32k with 2,900 MiB |
| H5. Threads and cancellation | Held: 24 cancellations, 1/2/4 threads |
| H6. Process peak not meaningfully changed | Held: within 2% in every uncapped pair |

## Evidence labels

Fresh solve (FS), fresh allocation audit (FA), fresh unit test (FU), source
inspection (SI), saved-array replay (RP).

## 1. Scope and code review (SI)

- The commit touches three production files: 100 lines added, none removed.
  Codex's `production-change.patch` matches the tree exactly.
- `HMatrixSystem.build` is overridden; `CompressedSystem.build` and its
  ACA/randomized builders are untouched. No Dense, FMM, tolerance, gate or
  option change. `factor.py` (the lifecycle repair) is byte-identical to the
  parent.
- Compared line by line with the base build:
  - `u` and `v` are reserved at compression, `e` overwrites `u`, and there is
    no later subtraction, so the final charge is `v12 + v21 + e1 + e2` as
    before.
  - The correction matrix is carried as live through the second child solve
    and the second correction step. The in-place solve keeps the base
    allowance `8·u.nbytes + 1 MiB`.
  - Small nodes keep the base order, so a rejected compression still falls
    back to a dense leaf. The fallback rollback is unchanged.
  - One behavioural difference I noted: a large node whose compression is
    rejected now raises after its children are built, where the base raised
    before. Same exception, more wasted work on a path that abandons the
    build anyway. Not a defect.

## 2. Old tree against new tree (FS)

Production solver, condition estimation and strict quality gates on, 180
angles, one thread. Dense anchors are fresh full solves.

| Case | Unknowns | Density and field, old vs new | Condition estimate | Corrections per call | Final inverse MiB | Accounted high-water MiB old → new | Peak GiB old → new | New vs Dense (density / field) |
|---|---:|---|---|---|---:|---|---|---|
| Multilayer TM (2 dielectrics, PEC core) | 9,478 | bit-identical | identical | identical | 198.32 | 234.04 → 198.32 | 0.996 → 0.986 | 5.4e-10 / 6.1e-10 |
| Partial coating TE (junctions) | 4,146 | bit-identical | identical | identical | 43.20 | 48.96 → 43.20 | 0.341 → 0.343 | 5.7e-11 / 8.3e-12 |
| Partial coating TM | 4,146 | bit-identical | identical | identical | 41.32 | 46.67 → 41.32 | 0.339 → 0.338 | 9.3e-11 / 2.1e-12 |
| **PEC circle TE**, 50 wavelengths | 3,144 | bit-identical | identical | identical | 27.71 | 33.90 → 27.71 | 0.255 → 0.260 | 2.7e-12 / 5.8e-12 |
| **PEC concave cavity TM** | 2,898 | bit-identical | identical | identical | 25.07 | 27.77 → 25.07 | 0.278 → 0.275 | 5.2e-12 / 1.7e-13 |
| **Coated PEC TE**, ε = 12 − 0.01i | 5,883 | bit-identical | identical | identical | 82.91 | 96.73 → 82.91 | 0.525 → 0.517 | 3.7e-10 / 2.4e-10 |

- The three bold cases are new to this series and go through the production
  geometry path, which for PEC is the combined formulation the GUI uses.
  Codex's PEC coverage was a native single-layer path, so these extend it.
- This answers my open question (c) from the plan: `e` now has the memory
  layout of `u`, and that does not change a single bit of any result here.
- Condition estimates exercise normal and adjoint solves in every run.

## 3. Storage caps (FS)

Multilayer TM, `compressed_storage_mib` set as shown:

| Cap MiB | Tree | Builds | Final inverse MiB | Field corrections | Outcome |
|---:|---|---:|---:|---:|---|
| 690 | old | 2 | 170.69 | 5 | passes with the weaker retry inverse |
| 690 | new | 1 | 198.32 | 2 | passes; **bit-identical to its uncapped solution** |
| 650 | old | 2 | — | — | rejected |
| 650 | new | 2 | 170.69 | 5 | passes with the retry inverse |

32,768-unknown dielectric star, factor storage budget 2,900 MiB, new tree:

| Quantity | Result |
|---|---|
| Builds / storage rejections | 1 / 0 |
| Final inverse, accounted high-water | 929.62 MiB, 929.62 MiB |
| GMRES columns / corrections | 0 / 3 |
| Density and field vs my 32k reference | bit-identical |
| Exact-row backward error | 1.1e-15 |
| Process peak | 3.675 GiB |

These match what the research builder gave in earlier rounds, now from the
integrated code. I did not rerun the old tree at 32k; it was measured twice
last round (two builds, 641 MiB inverse, 180 GMRES columns, 761–779 s).

## 4. Allocation audit of the integrated build (FA)

My tracer, as in earlier rounds, now with no pricing hook: the guard values
are the production ones.

| Build | Guard entries | Shortfalls above 1 MiB | Leaf query: growth vs declared MiB | In-place child solve: growth vs declared MiB |
|---|---:|---:|---|---|
| Multilayer TM | 2,075 | 0 | 1.19 vs 2.36 | 10.6 vs 143.9 |
| Partial TE | 941 | 0 | 0.92 vs 2.03 | 1.8 vs 24.0 |
| PEC circle TE | 875 | 0 | 0.61 vs 1.60 | 1.9 vs 25.8 |

- The leaf-query under-declaration I reported in the parent (5.4 MiB against
  0.68 MiB declared, 64 times per build on the multilayer) is gone.
- Aligned diagonal queries on three real operators, using the production
  gather: 70 queries, largest 3.16q, none above `4q + 1 MiB`, no low-rank
  contribution at any ordinary leaf.
- As before, the tracer sees NumPy buffers only.

## 5. Gather method and copy path (FU)

- The actual production `BlockRow.values` against the parent tree's method,
  loaded from its source: 20,700 cases, zero mismatches in bytes, dtype, shape
  or exception type. Includes empty-with-invalid selectors, NaN payloads,
  signed zeros, 2-D and scalar selectors, and the low-rank path.
- `_solve_in_place` with a stub system (`claude_copy_path_test.py`), nine
  cases: writable complex128 is solved in place with no storage check;
  read-only, complex64 and real inputs are copied, the growth is checked
  against the cap before the copy, the copy is charged as live during the
  solve, and reserved bytes afterwards equal the returned array's bytes; with
  no room for the growth it raises `MemoryError` and leaves the reserved count
  unchanged. This settles my question (a).

## 6. Threads and cancellation on the integrated code (FS)

My harness from the readiness round, with no research hook.

| Run | Product task threads | Control density | Cancellations | Workers alive after | Inverses alive after | Recoveries bit-identical |
|---|---:|---|---:|---:|---:|---:|
| Star 8,192, 1 thread | 0 | reference | 6 | 0 | 0 | 6 / 6 |
| Star 8,192, 2 threads | 2 | bit-identical | 6 | 0 | 0 | 6 / 6 |
| Star 8,192, 4 threads | 4 | bit-identical | 6 | 0 | 0 | 6 / 6 |
| Slot 2,048, 2 threads | 2 | reference (slot) | 6 | 0 | 0 | 6 / 6 |

- Phases: threaded range products (one task in flight at cancellation in each
  threaded run), leaf query, projected QR, Woodbury correction, the in-place
  child solve, and an in-object rebuild.
- The star control equals the control from the readiness round, which used the
  old tree with research hooks. The integrated code reproduces the prototype.
- The slot's in-object rebuild now recovers bit-identically. Last round it did
  not; that was the lifecycle defect, which this tree includes the repair for.
- Not checked by my harness: pending construction bytes (it runs without a
  memory ledger). Codex's suite checks that.

## 7. Replay of Codex's evidence (RP, FU)

- `unpack_evidence.py`: 22 array files, 88 records, all hashes verified.
- `analyze.py` on the restored arrays equals `replayed-analysis.json`.
- `test_build.py`: 9 tests pass. `test_gather.py` passes once
  `BASE_GRIM_ROOT` points at the parent tree; without it the script stops on a
  missing environment variable, which the README should mention.

## 8. On Codex's performance figures

- I did not time anything this round, by plan.
- Codex's medium pair (4.65% lower median from two samples each) is small
  against the run-to-run spread I have seen on this host; I would not quote it.
  Codex already labels it indicative.
- Codex's 32k capped figure (21% lower) is consistent in direction with my two
  pairs last round (33%). Both are single-geometry results at a cap chosen
  between the thresholds; the mechanism (one build, stronger inverse, no
  GMRES) is the same.
- One line in Codex's user-facing section deserves emphasis because it cuts
  the other way: the corrected leaf-query estimate is larger than the old one,
  so a build with very little headroom could now be refused earlier. I did not
  construct such a case. The amounts are a few MiB per leaf query.

## 9. Disclosures

- The suites reuse Codex's geometry generator and my instrumentation wrapper,
  which records accounting and per-call corrections without changing them.
- The gather test, the copy-path test and reading Codex's report took place
  while the old/new suite was running. Nothing in that suite is timed.
- Wall times in the JSON records are single runs and are not used.
- All 23 solve processes, 4 cancellation processes and the diagonal-query
  process returned 0, except the old tree's 650 MiB case, whose rejection is
  the expected result.
- Published: all JSON records, fields for every case, densities for the three
  new geometries (new tree and Dense), fields and exact-row data for the 32k
  run, and `array_hashes.json` with SHA-256 of every density, RHS and control
  array from both trees.

## 10. Position and what remains

Accept the production change. It is numerically neutral in every comparison
either of us has run, its accounting is tighter and better declared than the
parent's, and its benefit under a storage cap is reproduced.

Not covered by this acceptance, and still open:

- 64k and larger threaded builds;
- real memory pressure on a 32 GB machine;
- Windows native library and BLAS;
- GUI abort propagation and stalled native calls;
- the operator's own memory (1.9 GiB of 3.7 GiB at 32k), which neither change
  reduces;
- the Dense F-order output candidate, still unintegrated.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_M_old.json`, `claude_M_new.json`, logs, `run_M.sh`
- `claude_audit.py`, `claude_builder.py`, `claude_run_geometry3.py`,
  `claude_run_star_capped.py`, `claude_run_suite.py`
- `claude_copy_path_test.py`, `.json`, `.log`
- `claude_production_gather_test.py`, `.json`
- `claude_cancel_production.py`, `run_N.sh`, `run_N.log`, `out/`
- `claude_diagonal_queries_production.py`, `.json`, `.log`
- `results/`, `array_hashes.json`
