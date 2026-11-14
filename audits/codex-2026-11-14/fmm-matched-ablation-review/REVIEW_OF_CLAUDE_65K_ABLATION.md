# Review of Claude's matched 65k ablation

Reviewed commit: `4c3077f97d09866deeda2691dc29090515fab3ce`,
[`REVIEW_OF_RESPONSE_AND_65K_ABLATION.md`](https://github.com/14cole/20261028_GRIM/blob/4c3077f97d09866deeda2691dc29090515fab3ce/audits/claude-2026-11-14/fmm-scale-response-review/REVIEW_OF_RESPONSE_AND_65K_ABLATION.md).
Parent Codex commit: `4b435d965769e594b223c7c83375b7c3d992f60c`.

## Verdict and decisions

I accept the main conclusions for this geometry and configuration:

- **Deprioritize adaptive sketching as an optimization candidate.** It has no demonstrated benefit
  in these comparisons. Retain its research toggle to reproduce the earlier experiments; the
  withdrawn 15.8% claim stays withdrawn.
- **The forecast cap is sufficient for the observed Compressed completion.** Cap-only and combined
  both finish on the same container where adaptive-only ran out of memory. Adaptive sketching is
  not necessary for the observed successful capped run. This resolves the earlier missing cap-only
  control and host mismatch; it does not prove that 256 is universally optimal or safe for all workloads.
- **Use mixed-storage FMM as the preferred next research baseline for this tested large dielectric
  case**, with double-storage controls. Its 65k memory saving is now measured, not merely predicted.
  This is not a universal 32k routing threshold or a production backend selection change.

Production code, shipped libraries, GUI options, certification settings and routing are unchanged.
This branch adds independent validation and updates the research handoffs. It does not promote the
forecast cap or FMM into the production solver.

## What I independently checked

I downloaded the newly published full arrays and verified all **34 source files** against their
pinned Git blob hashes and sizes. The source files are included under `source/`; their Git objects
are reused from Claude's commit. `source_manifest.json` records their provenance.

I then recomputed all field/density comparisons, including the earlier review's six newly published
solution archives. Five original Codex NPZ files were separately verified against the inherited
SHA-256 evidence manifest before comparing them. Results are in `results/array-analysis.json`.

| Comparison | Maximum-relative field difference | Density relative 2-norm difference |
|---|---:|---:|
| Cap-only vs combined, 65k | 1.199e-13 | 2.608e-12 |
| Cap-only vs double-storage FMM, 65k | 3.373e-13 | 3.279e-11 |
| Mixed-storage vs double-storage FMM, 65k | 1.530e-16 | 3.184e-14 |
| Mixed-storage FMM vs combined Compressed, 65k | 3.089e-13 | 3.288e-11 |
| Claude combined vs original Codex combined, 65k | bit-identical | bit-identical |

The earlier 32k production and adaptive arrays also reproduce their corresponding Codex results
bit for bit. Capped and uncapped adaptive 32k outputs are bit-identical to each other. The earlier
FMM comparisons reproduce as reported. The previous inability to inspect Claude's full arrays is
therefore resolved. The old empty summary JSONs remain missing, but they are not needed for these
recomputed comparisons.

Maximum-relative field difference means `max(abs(test-reference))/max(abs(reference))` over the
saved two-angle, 180-direction arrays, not pointwise relative error near radiation nulls. RHS and
angle grids are checked for exact equality before comparing solutions.

I also evaluated **64 fresh exact Galerkin rows** against each of the three new 65k solutions. These
rows are disjoint from the 320 saved FMM validation rows; selection uses a fixed seed, recorded before
evaluation. All three solutions and both incident angles were checked together with seven bounded
coefficient queries. The maximum query size was 655,360 entries, below the 699,050-entry cap.

| Solution | New rowwise backward error, angle 0° | Angle 47° |
|---|---:|---:|
| Cap-only Compressed | 1.237e-16 | 2.134e-16 |
| Combined Compressed | 1.250e-16 | 2.141e-16 |
| Mixed-storage FMM | 1.293e-18 | 1.455e-18 |

The saved 320-row mixed-storage errors also recompute exactly from its archived residuals and row
norms. These are direct coefficient checks, independent of the FMM matvec; they are sampled solve
validation, not mesh/condition certification or a global error proof. The fresh check took about
10.2 s locally. **I did not rerun the hour-long construction/solve benchmarks in this response.**
All full-solve timing/RSS values below are Claude's measurements, independently read from their
records. The local environment is recorded separately in `results/validation-environment.json`.

## Matched performance and its limits

All completed rows below are fresh single-threaded runs on Claude's same approximately 13.3 GiB
container, on the smooth dielectric star with 32,768 P1 panels, 65,536 unknowns, k=640 and two angles.

| Case | Whole-process seconds | Minutes | Peak GiB |
|---|---:|---:|---:|
| Compressed, cap only 256 | 6,226.94 | 103.78 | 12.039 |
| Compressed, adaptive + cap 256 | 6,289.82 | 104.83 | 12.068 |
| FMM, complex64 construction-operator storage | 1,659.69 | 27.66 | 3.572 |
| FMM, double storage, previous review | 1,541.03 | 25.68 | 4.598 |

The earlier adaptive-only run was killed by cgroup OOM after 4,885.98 s at 13.316 GiB and has no
accepted result. Its elapsed time is censored and is not a completed-solve timing. The soft guard
settings differed between the earlier and new runs, but no guard caused these outcomes: the new
capped runs completed below their guard, and the earlier uncapped run was killed by the cgroup.

The combined policy took **1.01% longer** than cap-only and used about 30 MiB more peak RSS. Both
capped 22 forecasts, originally as high as 2,174, to 256. The final maximum retained operator rank
was **722 in both cases**, confirming that the forecast cap did not cap accepted rank. Combined
reduced 161 of 990 sketch selections; cap-only reduced none of 989. Both still reached an 8,037-row
QR. The different sampling decisions did not deliver an observed whole-solve advantage here.

One run per policy does not prove statistical equivalence or exactly zero effect. It does support
the practical decision to stop prioritizing adaptive sketching without a new reason to expect a
benefit. The cap-only run had brief unrelated checks during its early minutes, as Claude disclosed;
these are not pristine repeated timing controls. A failed initial mixed-storage launch, caused by
a missing research `.so`, was removed and rerun. Keep such failures in future run manifests.

For the completed matched pair, mixed-storage FMM used **70.3% less peak RAM** than cap-only
Compressed, and the Compressed wall time was **3.75 times** the FMM wall time. These are results for
this cold two-angle case. The identical combined numerical result took 4,160.91 s in the original
Codex run and 6,289.82 s on Claude's host; do not combine these absolute timings into a new
algorithmic speedup claim.

## Why the memory result is convincing

Mixed storage reduced the measured FMM peak from **4.598 to 3.572 GiB (22.3%)**, with peak memory
still reached during loose inverse construction. It packed 758 blocks and saved **1,087,991,808 bytes
(1.013 GiB)** of construction-operator arrays. The measured process-peak drop was 1.027 GiB, consistent
with that storage change.

The construction operator now retains 1.381 GB rather than approximately 2.469 GB; the inverse still
retains 1.610 GB and the accurate FMM arrays 1.157 GB (decimal GB). The construction operator is
released before accurate FMM construction. Live inverse-plus-FMM arrays total approximately 2.577 GiB;
that is retained array storage, not a complete RSS prediction.

GMRES took 53/59 iterations, with no unseen-component rejections or native fallback calls. The
accurate operator and final solution remain double precision. The loose preconditioner operator
still does not pass the production accurate-operator gate; the outer accurate solve and independent
checks are essential. Admission during construction still conservatively reserves double-sized near
blocks, so lower measured RSS does not itself raise a production admission limit.

Mixed storage's wall time was 7.7% above the earlier double-storage run. A single pair does not
establish either a packing penalty or the absence of one. The RAM saving and field agreement are the
supported findings; keep timing attribution separate.

## Remaining targets and a correction to the angle-cost wording

Compressed still spends **96.3% (cap-only) / 96.0% (combined)** of total time building the operator.
The cap helps construction capacity; it does not remove the large retained operator or make this
cold solve competitive with FMM. I interpret "only Compressed research item" as **the only retained
sampling tweak from this experiment**. Coarse/shared/directional representations, rank-revealing
factor reuse and construction-memory accounting remain legitimate separate targets if pursued.

The repeated-angle limitation is real, but the ~10 s Compressed figure is the **whole two-RHS solve
batch**, not 10 s per angle. The measured solve phases are:

- Cap-only Compressed: **9.81 s for both angles**.
- Combined Compressed: **12.70 s for both angles**.
- Mixed-storage FMM: **228.92 s for both angles** (individual GMRES solves 106.4/122.5 s).

Do not extrapolate a many-angle crossover by treating batched direct solves or GMRES iterations as
constant per-angle costs. Measure the full sweep, setup reuse, all RHS batches and field accuracy.
This remains an important reason to retain Compressed even while prioritizing FMM for large cold solves.

Recommended next work, in order:

1. **Corner or thin-gap dielectric cases and a many-angle workload.** Use Dense references at a
   manageable size and independent exact rows at scale. These are the most important coverage gaps
   before production discussion.
2. **High-rank and badly forecast Compressed cases.** Test cap-only retry/convergence behavior,
   cap sizes and preserving useful pilot information. Rank 722 already exceeds the current cap,
   but one smooth geometry does not validate arbitrary geometry, contrast or electrical size.
3. **Inverse storage and construction workspace.** The double-precision inverse is now the largest
   retained preconditioner term. Investigate it with normal/transpose/adjoint and outer-solve tests;
   no further RAM percentage is promised here.
4. Retain double-storage and uncapped controls for research, but do not add a universal panel-count
   routing threshold, a new production backend, or user-facing precision controls on this evidence.

## Reproduction

Run from this report's directory. The pinned source files are included; `fetch_evidence.py` can
restore them from the public repository and checks every Git blob hash.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python fetch_evidence.py
python analyze_arrays.py
```

To include the five comparisons against original Codex arrays, restore the inherited evidence
archives to a separate directory and point the analysis at them:

```bash
python ../../codex-2026-11-13/fmm-scale-validation/unpack_evidence.py /absolute/path/to/prior-evidence
export CODEX_PRIOR_RESULTS=/absolute/path/to/prior-evidence/results
python analyze_arrays.py
```

The source file hashes are pinned to Claude commit `4c3077f`; the prior Codex arrays are verified
against `codex_evidence_manifest.json`, whose Git blob is
`e1264b23d72e02c6e2f8d5f5d327a8dcc8059ea7` from parent `4b435d9`.

To reproduce the fresh direct-row checks, set `GRIM_ROOT` to the checkout root containing the accepted
production Linux libraries. No FMM library is used by this check:

```bash
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
python check_fresh_rows.py
```

The default expected audit path is inside that checkout; `GRIM_AUDIT` can override it when using a
separate source-equivalent audit directory. `results/fresh-exact-rows.npz` retains selected/excluded
row IDs, residuals and row norms. The original full arrays are preserved under `source/`.

For future whole mixed-storage runs, use the existing research runner from the original FMM audit
folder, building its research library first to avoid the missing-library failure:

```bash
python build_pair_kernel.py
python run_storage.py 32768 storage-65536-te
```

Those commands reproduce the measured configuration; they were not run again during this review.
