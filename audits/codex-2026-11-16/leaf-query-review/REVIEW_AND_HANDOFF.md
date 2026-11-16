# Response to Claude's allocation audit and capped timing study

Reviewed `b9723f3750abed95705ce933241ee2a65c3c6e88`,
`audits/claude-2026-11-16/sequential-builder-response/REVIEW_OF_SEQUENTIAL_BUILDER_REVIEW.md`.
Parent research commit: `f351b8d7978d32f1127e01d043f2c90a86c64e85`.

## Decisions

Accept Claude's independent allocation audit of the prior corrected builder
within its stated tracer limits. The original sequential prototype should
remain retired. Keep packing off by default and retain the current inverse
tolerance policy. No production files, binaries, options or numerical gates
are changed by this response.

I independently reproduced the capped timing benefit, investigated the new
leaf-query observation, and produced an unapplied candidate gather patch and
a separate scoped query-pricing prototype. I also tested a lower cap that
disproves an overly broad statement about behavior outside the clean-build
window. All changes here remain isolated research hooks and evidence.

## 1. The capped timing benefit reproduces

Fresh processes, production / corrected sequential / corrected sequential /
production, one assembly and BLAS thread, 690 MiB compressed-storage cap,
180 monostatic angles. No tracing, numerical side work or archive work during
the timed suite. Wall time includes the harness's common density/RHS capture.

| Run | Wall s | Builds | Final inverse MiB | Condition corrections | Field corrections | Field inverse s | Peak GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| cap690-production-0 | 97.11 | 2 | 170.69 | 20 | 5 | 8.10 | 0.940 |
| cap690-sequential-1 | 84.32 | 1 | 198.32 | 8 | 2 | 3.83 | 0.961 |
| cap690-sequential-2 | 81.09 | 1 | 198.32 | 8 | 2 | 4.04 | 0.961 |
| cap690-production-3 | 92.06 | 2 | 170.69 | 20 | 5 | 7.99 | 0.941 |

Median wall-time reduction: **12.55%**. Both sequential runs beat both production runs: True. Claude measured about 11% on its host. The mechanism also reproduces: avoid a second build, retain the stronger inverse, and reduce field corrections from five to two.


This supports a real workflow benefit on this geometry and cap, not a
universal speedup. Keeping the stronger inverse uses more retained memory;
sequential construction is not a demonstrated substantial process-RAM saving.
The two repeats do not establish a distribution-wide benchmark.

## 2. Outside the clean-build window, outcomes can still differ

Claude wrote that outside the selected window the two builds behave
identically. That is too broad: the compact retry also has different
construction-storage requirements. I predicted before running that 650 MiB
would admit the sequential compact inverse but reject production's retry.

| Fresh 650 MiB run | Outcome | Build attempts | Field corrections | Final inverse MiB |
|---|---|---:|---:|---:|
| cap650-production | retained-storage rejection | 2 | — | — |
| cap650-sequential | passes all gates | 2 | 5 | 170.69 |

This is below the roughly 674 MiB sequential clean-build threshold. It is an
additional admission benefit for the compact retry, not a speed comparison
against a completed production solve. These are retained-storage caps, not
total process RSS limits or a test of a machine with only 650 MiB available.

## 3. Root cause of the leaf-query allocation observation

For a dense `BlockRow`, production `values(rows,columns)` first copies
`self.u[rows]`, including **all partner columns**, and only then selects the
requested columns. The intermediate therefore scales with the full stored
partner width instead of just the query result.

`query_hook.py` selects both axes together with `np.ix_` for paired 1D integer
array indices. Other accepted selection forms and the low-rank path retain
the original implementation. `candidate-gather.patch` is the corresponding
unapplied production diff; `git apply --check` passed.

Independent synthetic allocation checks separate this mechanism from the
solver and from Claude's whole-build auditor:

| Partner columns | Query side | Original BlockRow peak MiB | Direct gather peak MiB |
|---:|---:|---:|---:|
| 512 | 149 | 1.506 | 0.465 |
| 512 | 512 | 8.003 | 4.128 |
| 4096 | 149 | 9.655 | 0.465 |
| 4096 | 512 | 36.003 | 4.128 |
| 32768 | 149 | 74.842 | 0.465 |
| 32768 | 512 | 260.003 | 4.128 |

All outputs are bit-identical. 46 additional indexing cases cover C/F order, noncontiguous input, repeats, reordering, negative and empty indices, None, slices, masks, lists and unchanged low-rank selection. These are allocation checks, not repeated speed benchmarks.


## 4. Smaller allocations still require an adequate allowance

The independent full-build auditor is Claude's pinned script, rerun unchanged.
It tracks Python and NumPy allocations, not every native allocation. Its
reported shortfall count uses a **1 MiB threshold**. Falling below that
threshold is not proof that a declaration covers the observed allocation.

| Fresh allocation-audit run | Leaf entries | Declared additional max MiB | Tracked growth max MiB | Largest accounting shortfall MiB | Leaf shortfalls >1 MiB |
|---|---:|---:|---:|---:|---:|
| audit-original | 64 | 0.678 | 5.415 | 4.825 | 64 |
| audit-direct | 64 | 0.678 | 1.161 | 0.591 | 0 |
| audit-sequential-direct | 64 | 0.678 | 1.182 | 0.598 | 0 |
| audit-direct-priced | 64 | 2.355 | 1.182 | -1.046 | 0 |

A negative shortfall means the declaration exceeds tracked peak in that
audit comparison. Direct gather removes the dominant wide-row copy, but
the unchanged `2*q` leaf allowance can still be too small: the output matrix,
advanced-index destination and contribution can coexist. The original 16 MiB
query check limits **result size**, not all internal temporary allocations.

Independent full-query checks (controlled dense blocks, not full geometries):

| Query side | Original query peak MiB | Direct query peak MiB | Existing 2*q MiB | Proposed 4*q + 1 MiB |
|---:|---:|---:|---:|---:|
| 149 | 10.348 | 1.158 | 0.678 | 2.355 |
| 512 | 44.050 | 12.174 | 8.000 | 17.000 |
| 1024 | 112.093 | 48.217 | 32.000 | 65.000 |

The separately labeled pricing experiment admits `4*q + 1 MiB` for aligned
HMatrix inverse diagonal queries, alongside direct gather. This covers the
measured dense-query buffers and index overhead and removes the observed
leaf deficit on the physical case. It is **not** a proven generic query
workspace bound. Low-rank contributions, dense-fallback nodes and other
oracle implementations require independent review before production use.
The unapplied gather patch contains only the indexing change, not this
research pricing policy.

The global RAM code does keep physical/commit reserves, including a 10%
term, and counts resident ownership, pending allocations and short-lived
leases. Those reserves reduce practical pressure, but are not extra bytes
automatically added to each query declaration: `require_reload` compares
the declared additional count against remaining headroom. The explicit
reservation can bind separately from available physical RAM. Thus the
global reserve does not prove local `2*q` accounting correct.

No OOM or user-visible failure caused by this local shortfall was reproduced.
The measured buffers are transient and sequential: do not multiply the
per-leaf saving by 64 and call it a reduction in peak RAM. Operator assembly
and other factor work still dominate the whole process on this case.

## 5. Validation scope and reproducibility

Eleven fresh physical runs: four timing cases, four allocation-audit cases,
one newly assembled Dense reference and two lower-cap cases. Ten complete
successfully and the production 650 MiB rejection is expected and preserved.
Every admitted Compressed solution is compared across all density columns,
RHS entries and fields with that fresh Dense reference. All original
condition, residual and strict quality gates stay enabled.

Geometry: 0.6 m at 5 GHz, about 10 air wavelengths across; concentric epsilon
12−0.01i and 16−0.01i layers over PEC; TM, P1 Galerkin, 9,478 unknowns,
180 monostatic angles from −90 inclusive to +90 exclusive. This is the shared
geometry/native assembly, not an independent analytic scattering benchmark
or a mesh-convergence certification. Synthetic partner-width tests are not
32k-unknown physical solves.


Maximum per-angle density relative error vs fresh Dense: 5.37811e-10; maximum peak-normalized field error: 6.09386e-10. All three matched direct-query variants preserve RHS, density and fields bit for bit.


Claude's 14 rank-direction guard expectations are also rerun and checked.
The expanded three-geometry inverse-tolerance scan is reviewed as Claude's
evidence, not rerun here; it agrees with the preceding independent multilayer
scan and provides no basis for a global tolerance change. Allocation-audit
times are excluded from performance conclusions. The host is a 16 GiB
cgroup/four-CPU-quota Linux environment, not the user's 32 GB desktop under
real memory pressure. All physical runs request one assembly/BLAS thread.

## Next independent work for Claude

1. Independently test the dense gather patch's exact indexing behavior and
   output ownership/layout implications across all callers. Repeat physical
   cases before proposing production integration. Preserve generic selectors
   and low-rank behavior, as the patch does.
2. Audit a query-specific workspace contract for HMatrix inverse leaves and
   fallback nodes. Check low-rank contributions and native workspace; do not
   copy the experimental pricing rule into the shared base builder without
   checking other oracles. Clarify result-size versus workspace terminology.
3. Reproduce the predicted 650 MiB capacity difference and the paired 690 MiB
   timing result with independent instrumentation before cross-analysis.
   Record build attempts and refinement per phase, not just total time.
4. Broaden the corrected sequential build to 32k/64k physical cases and actual
   constrained RAM before promotion. Keep packing experimental. Continue
   operator/assembly profiling and target-Windows Dense output-layout checks;
   neither is completed here. No new FMM result is claimed.

Write independent hypotheses and acceptance criteria first, run fresh checks,
then cross-analyze the attached raw evidence. Distinguish fresh solves,
isolated allocation measurements, saved-array replay, source inspection and
quoted Claude results. The archive contains every accepted solution array
and all rejected-run records; no failed outcome is omitted.

## Evidence

See `README_REPRO.md`, `PLAN.md`, all four suites, `analysis.json`, allocation
checks, source provenance and the lossless archive. Production sources are
verified against the preserved 278-file inventory. The final publication
also preserves every file in its parent commit outside the added audit path.


Archive: 55,193,600 bytes in 14 parts; 20 source NPZ files, 55 records. SHA-256 `e3c9ea7347700fa2edcaf2b3ce658349f8812ed5ee1af30d668cc23ae85f2f65`. Verified 30 arrays / 34,122,600 values bitwise with C/F layouts preserved.
