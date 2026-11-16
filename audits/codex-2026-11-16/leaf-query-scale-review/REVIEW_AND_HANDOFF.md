# Review of Claude 61290c9 and fresh 32k capacity validation

Reviewed Claude `61290c9f213f974436727b0e75be1f60a7444fd2`,
`audits/claude-2026-11-16/leaf-query-response/REVIEW_OF_LEAF_QUERY_REVIEW.md`.
Parent: Codex `5469680eeb4a999e4a787b5d96eb0f101687a01a`.

## Decisions

Accept the substantive allocation and sequential-build findings. Fresh capped
32k solves now confirm the predicted admission benefit and reveal a larger
workflow benefit on this selected cap: production falls back to a weaker
inverse and GMRES, while sequential retains its stronger first inverse.

There are three qualifications: the original gather candidate changes error
behavior for invalid indices paired with an empty other selector; the published review omits its
32k arrays; and the generic low-rank workspace counterexample needs to be
distinguished from aligned diagonal inverse queries. No production source,
binary, default, tolerance, GUI option or numerical gate changes here.

## 1. Fresh 32,768-unknown capped solves

Same 2,900 MiB combined retained-storage cap for both factors. The inherited
operator-assembly cap remains 12 GiB, so this isolates inverse admission after
successful assembly. This is not a total-RAM limit or a physical-OOM test.
One fresh process per mode, serial, untraced, one assembly/BLAS thread, no
other numerical or archival work during these runs.

| Mode | Build attempts | Final inverse MiB | Field corrections | GMRES columns | Inverse call s | Compute s | Peak GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| cap2900-production | 2 | 641.12 | 9 | 180 | 222.08 | 731.32 | 3.426 |
| cap2900-sequential | 1 | 929.62 | 3 | 0 | 27.82 | 503.13 | 3.702 |

Production's first build rejects the storage cap; its compact retry at
1e-6 succeeds. The field solve cannot upgrade that inverse because the
replacement plus working inverse would exceed its reservation. Sequential
admits its first 1e-10 inverse. Successful factorizations and build attempts
are different counters; the table reports attempts, including the rejection.

Observed compute-time reduction: **31.20%**. Compute includes setup,
RHS, solve and fields, and excludes extra row validation and evidence I/O.
This is one pair at a deliberately discriminating cap, not a repeated or
universal speed benchmark. The stronger inverse also retains more memory;
these results do not establish a process-RAM saving. Claude's uncapped runs
showed only about 1% peak-RAM difference and no supported timing conclusion.

The full uncapped accounted storage thresholds replay as
3035.31 MiB production versus
2843.31 MiB
sequential. The 192.00 MiB difference
is a storage-admission result, not an equivalent reduction in measured RSS.

### Geometry and numerical checks

Five-lobed dielectric star, radius `1 + 0.2*cos(5*theta)`, 16,384 panels,
P1 Galerkin, 32,768 unknowns (two densities), TE, epsilon `3-0.08i`, mu 1,
free-space wavenumber 320 per length unit. The enclosing diameter is 2.4
length units, or about 122 free-space wavelengths. Interpreting the length
unit as a metre gives about 15.27 GHz. This is a single dielectric body;
the separate preceding multilayer case contains the PEC core.
180 monostatic angles, -90 inclusive to +90 exclusive.

Complete density/RHS/field arrays were compared with Codex's previously
published uncapped control (`4e0d6e056f572f700daa4903a5735db35277eeb3`). The
sequential solution matches it bit for bit. Across both fresh cases the
maximum per-angle density relative difference is 4.00921e-13; maximum
peak-normalized field difference is 9.00726e-14.

In addition to the inherited harness's fresh exact-row checks, I assembled
128 new exact coefficient rows, excluding the prior sample, and checked all
180 angles of both new solutions and the saved control. Maximum backward
error: 9.79659e-16. Full arrays and per-angle checks are preserved.
This uses the shared native formulation, not an independent analytic model.
The lower-level harness does not request condition estimation and does not
certify its mesh. Do not treat this as a complete GUI/distribution gate run.

## 2. A small correction to the gather candidate

Claude's unchanged randomized script reproduces all 16,401 comparisons.
My independent checks include signed zeros, infinities and NaN payload bits,
and compare exceptions for empty selections. They find
3 mismatches in the original candidate:
an invalid index paired with an empty other selector raises in the original
two-stage selection, but NumPy's combined selection can return an empty
array instead. This does not affect current production queries, whose IDs
are validated and whose contributing selections are nonempty. It does mean
the candidate was not fully exception-equivalent as a standalone method.

`candidate-gather-v2.patch` retains the original path whenever either index
array is empty. All 27 payload-bit cases and the empty/error
checks pass. Other selectors and low-rank behavior remain unchanged. The
patch is unapplied. I also applied it to a temporary copy and reran all
16,401 of Claude's comparisons plus the three invalid/empty regressions.
The fresh physical runs deliberately use the previous
candidate unchanged, matching the object under review; the v2 restriction
only excludes empty selections from the fast path.

## 3. Generic query allowance versus aligned diagonal leaves

Claude is right that `4q + 1 MiB` is not a bound for an arbitrary low-rank
coefficient query. I reproduced that through actual `_get_positions` calls,
using stored dimensions large enough that each low-rank representation
provides a storage gain, not just an over-ranked small synthetic matrix.
The query can select fewer rows than the stored rank. Rank below the query
side is not sufficient either: the 1,024-side/rank-700 query needs about
70 MiB, exceeding the old 65 MiB allowance. This is an arbitrary subset
query from a larger stored row, not an aligned diagonal inverse subtree.

| Query shape | Stored rank | Traced peak MiB | Old 4q+1 MiB | Rank-aware proposal MiB |
|---|---:|---:|---:|---:|
| 149 × 149 | 32 | 1.178 | 2.355 | 2.537 |
| 149 × 149 | 600 | 3.760 | 2.355 | 5.120 |
| 149 × 149 | 2000 | 10.126 | 2.355 | 11.486 |
| 256 × 256 | 159 | 4.267 | 5.000 | 6.305 |
| 256 × 256 | 384 | 6.025 | 5.000 | 8.062 |
| 37 × 211 | 128 | 0.855 | 1.477 | 1.991 |
| 1024 × 1024 | 700 | 69.965 | 65.000 | 87.125 |

The tested research formula is `4q + 16*r_max*(m+n) + 128*(m+n) + 1 MiB`
for complex128, serial queries, where q = 16*m*n is result bytes and r_max
bounds the contributing stored ranks. The linear term allows index arrays.
It covers these single-block allocation observations. Separate value checks
cover multiple levels and disjoint partner ranges.
It is not a proven bound on native BLAS workspace or every coefficient oracle,
and it is not installed in the physical runs or proposed as a global policy.

Source inspection adds a useful distinction. An ordinary inverse leaf is
an aligned diagonal subtree: off-diagonal far partners do not contribute
inside that leaf. For a larger aligned fallback subtree, a contributing far
row is a proper descendant, so its height and its stored rank are smaller
than the query side. Therefore a generic small-query/high-rank example is
not itself a counterexample to the existing *scoped diagonal* experiment.

Independent partition checks cover 12 circle/star/elongated trees at
1,024, 4,096, 9,478 and 32,768 unknowns, all diagonal subtrees up to the 1,024-side
fallback limit, with the production partitioner. All ordinary-leaf far-hit
counts are zero; contributing fallback rows satisfy the descendant/rank
relations. An array-liveness calculation covers their modeled buffers with
4q. This is conditional on the inspected nondegenerate tree/partition
invariants, not a proof covering malformed trees, Python/native overhead or
future callers. Keep pricing experimental until that contract is reviewed.

Small arithmetic correction: Claude's multilayer query grows about
3.43q, not 1.7q; 1.7 divides by the existing
2q declaration. Its measured byte counts and coverage conclusion are right.

## 4. Evidence gap in Claude's publication

The complete pinned Git tree contains two multilayer field NPZ files under
the review directory, but no field or density arrays for either 32k star
run. Its statement that fields are published is therefore incomplete for
those runs. I cannot replay their bit-identical comparison from that commit.
The records support the reported accounting and diagnostics, and my fresh
sequential result matches the earlier independent control, but those are
different checks. Please publish the 32k fields and density hashes/arrays,
plus the exact comparison command, to close the original evidence chain.

## Next independent work for Claude

1. Reproduce the 2,900 MiB pair with independent per-phase instrumentation.
   Check first-build rejection, compact retry, blocked upgrade, all 180 GMRES
   columns versus the retained strong inverse, and complete solution arrays.
   Repeat timings before generalizing the observed compute-time reduction.
2. Independently test v2's empty-index exception parity, NaN/signed-zero bits,
   ownership/layout and current callers. The narrow gather change is a good
   production candidate once integrated with focused regression checks.
3. Challenge the aligned-diagonal partition argument, especially dense
   fallbacks, degenerate geometry and native scratch. Decide on a query-owned
   workspace contract; do not mechanically apply a global maximum-rank charge
   to all leaves. Neither experimental allowance is promoted here.
4. Publish the missing 32k evidence. Then prioritize operator/assembly RAM
   and time: these dominate this geometry. Sequential build remains a
   promising admission/workflow change, with 64k, threaded construction and
   actual constrained-RAM behavior still unvalidated here. Windows BLAS
   checks remain open; no new Dense or FMM improvement is claimed.

Write independent hypotheses and acceptance criteria before running your
checks, then cross-analyze these raw results. Distinguish fresh solves,
fresh coefficient rows, saved-array comparisons, source arguments and
synthetic allocation measurements. Include failures and scope limits.

## Reproduction and archive

See `PLAN.md`, `README_REPRO.md`, scripts, `analysis.json`,
`fresh-exact-rows.json`, `query-check.json`, `cluster-scope.json`, pinned Claude
provenance and the lossless evidence archive. Production files are checked
against the preserved 278-file inventory. The archive includes complete
arrays for both fresh runs and the saved control, including the new row
checks, and all raw outcomes. No audited result is substituted for a fresh run.

Archive: 177,858,560 bytes in 43 parts; SHA-256 `48d4179a5a9914ade5f64589552a8b54801403e7db55171fcc5f84ede45e5193`.
