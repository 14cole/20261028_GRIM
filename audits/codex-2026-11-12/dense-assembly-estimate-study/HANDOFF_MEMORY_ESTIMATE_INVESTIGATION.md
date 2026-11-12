# Dense dielectric assembly forecast investigation

Date: 2026-11-12. Runtime examined: `ae08d66dc309c393ce62cc76bacd510a150ebf33`.
Review branch: `codex/dense-memory-review-response-2026-11-12`.

## Outcome and scope

The conservative single-dielectric assembly floor has two identifiable causes:
an operator-matrix allowance that the normal fused path no longer needs, and a
generic workspace allowance that does not price its actual tile/near-pair plan.
A research-only replacement admitted an 8,000-unknown solve at 1.6 GiB and a
12,000-unknown solve at 2.8 GiB. Both completed below those budgets and matched
the full reference field arrays bitwise when tile and angle-batch settings were
matched. A 1.3 GiB attempt was rejected before assembly.

**This commit changes audit files only. No production forecast, numerical
kernel, tolerance, UI option, DLL or `.so` is changed.** `study_wrapper.py`
monkey-patches the forecast only inside explicitly requested research processes.
Its workspace coefficients are provisional allowances, not established all-path
bounds. It must not be imported into a distributed solver.

The previously requested evidence archive was published in commit
`ce9b3780d6788449fb029ab0674adde170b584e9`, under
`audits/codex-2026-11-12/dense-memory-review-response/`. This investigation has
its own evidence archive beside this handoff; the earlier archive is unchanged.

## Findings traced to allocations

### 1. The extra full operator is obsolete only on the fused path

[`dielectric.assemble_system`](../../../tools/GHOST/ghost_backend/twod/formulations/dielectric.py)
allocates one Fortran-order `(2*n,2*n)` complex128 system matrix. When observer
and source quadrature orders match, the exterior S/K'/D/W operators scatter
directly into that matrix. Interior S and K' also use matrix-block destinations.
Native far-kernel availability does not change that destination ownership.

The current [`_estimate_memory_gb`](../../../tools/GHOST/ghost_backend/twod/solver.py)
still adds `16*n*n` bytes for one retained operator in `single_dielectric`.
For n=4,000 this is 256,000,000 bytes, or 0.238419 GiB. Removing **only** this
term would reduce the observed assembly floor from 2.004551 to 1.766132 GiB;
it would still refuse a 1.6 GiB budget.

The unequal-order path really does allocate an additional `(n,n)` S matrix.
The small allocation probe recorded `(512,512)` alone for fused assembly,
versus `(512,512)` plus `(256,256)` for orders 8/7. The probe observes large
`np.zeros` allocations, not every NumPy allocation; the ownership conclusion
also follows from tracing the destination code. Both probe solves passed their
discrete-system gates. The unequal-order run is an allocation-path test, not
a numerical equivalence test against equal orders.

**Recommendation:** attach an explicit assembly-storage qualification to the
actual formulation/rule plan. Remove the extra matrix only when the selected
path has direct destinations. Do not infer this for arbitrary private callers
from the string `single_dielectric` alone.

### 2. Price the execution plan, including queued tiles

The generic assembly workspace is currently
`(64 + 128*assembly_threads) MiB + 8192*n bytes`. At four threads and n=4,000
this is **636,747,776 bytes**, or **0.593018 GiB**. Its fixed/per-thread portion
alone is 576 MiB.

The constrained Dense plan can choose tile edge 128, but leaves this original
assembly forecast in place. The two real dielectric traversals have different
tile-byte estimates: 536 bytes per entry for fused exterior S/K'/D/W and 408
for interior S/K'. A replacement must price both, respecting a user's explicit
tile setting. It cannot assume that admission will later shrink a tile while
pricing an unrelated earlier plan.

[`operators.py`](../../../tools/GHOST/ghost_backend/twod/operators.py) contains
two relevant scheduler bounds:

- `_run_dependent_tiles`: up to **3*workers** submitted but not committed.
  Completed parked tiles retain accumulators and scales while active tiles
  also own quadrature scratch.
- Ordered scheduling and `polynomial_quadrature.map_checked` use different
  bounded queues. Their consumers and temporary results must be counted too.

Counting only one output tile per worker is insufficient. NumPy quadrature,
native quadrature, fallback scatter, and the W transformation also have
different temporary-array lifetimes. Native far quadrature currently runs one
whole tile per scheduler task; its old split-output-copy branch is not active
for that normal call.

### 3. Geometry is useful for near interactions, not for eliminating A

`regions.mesh_near_pair_count(mesh)` supplies a geometry-only count without
assembling a dense kernel. It can qualify near-pair integer storage and bounded
near blocks for the dielectric model as well. On the 4,000-panel circle it
predicted 28,000 ordered pairs and assembly recorded exactly 28,000. On the comb
it predicted 96,413 while assembly recorded 96,087: the slightly higher estimate
is consistent with an inclusive geometric boundary versus the far classifier.

The comb has 739 actual panels and 1,478 unknowns, with about 130 near pairs
per panel. Its S/K'/D records exceed NearStore's 16 MiB in-RAM threshold, so this
test exercises near-block spilling. A thin ellipse alone was not a sufficient
stress case: it had only about seven near pairs per panel.

NearStore bounds coefficient residency, but near-pair index arrays, sorting,
tile records, and geometric metadata still need explicit pricing. Their cost
does not disappear when coefficients spill. P2/P3 add basis-width-dependent
blocks and a separately bounded moment cache. The prototype deliberately leaves
P2/P3 forecasts unchanged; their passing control runs do not qualify tighter
polynomial estimates.

Geometry does **not** change the dense system matrix's `16*d*d` storage. This
work improves admission accuracy, not dense asymptotic memory scaling.

## Experimental model, reproducible rather than fitted to RSS

The candidate is limited to single dielectric, P1, with **explicit tile 128**.
All existing Dense scratch checks, process/cache allowance, factorization and
solve forecasts, RHS recovery, live allocation checks and numerical gates run
unchanged. Experiments use disk residual storage; the negative admission test
uses auto storage. Ordinary automatic backend selection is not qualified here.

Let n=mesh nodes, d=2*n, Q=geometry near-pair count, w=2, T=min(panel count,128),
and W=assembly workers. The trial assembly expression is:

```
A = 16*d*d
fixed = 64 MiB
linear = 8192*n
near_metadata = 128*Q
near_store = min(16 MiB, 3*16*w*w*Q)
far = W*T*T * (3*(64*w*w + 64) + (1024 + 64*w*w))
near = 256 * min(1,000,000, 256*Q)
assembly = A + fixed + linear + near_metadata + near_store + max(far, near)
```

The far expression separately allows three retained tiles per worker and active
scratch. The near allowance starts from the existing regional model's sample
allowance. These are conservative hypotheses, not a formal maximum for every
quadrature/material/path. The model does not explicitly price every Python tile
record. No coefficient was adjusted after seeing a case's RSS.

For n=4,000, d=8,000, Q=28,000, W=4, the exact trial assembly components in bytes
are: A=1,024,000,000; fixed=67,108,864; linear=32,768,000;
near_metadata=3,584,000; near_store=5,376,000; far=146,800,640;
near=256,000,000. The existing process/cache/sample allowance is then added by
`dense_memory.forecast`, yielding an assembly forecast of **1.512896 GiB**.
Factorization/solve becomes the limiting phase at **1.517609 GiB**, with all
181 angles in the original batch. This is why cap 1.6 admits it and cap 1.3
still refuses even after shrinking the batch to one.

This expression is not uniformly smaller: on the one-thread 4,000-unknown
control its near allowance makes it more conservative than the old estimate.
That is another reason to qualify per-phase allocation lifetimes rather than
ship a universal percentage reduction.

## Independent validation

28 recorded fresh-process cases: 27 successful survey solves and one expected
pre-assembly refusal. All successful solves passed unchanged discrete-system
quality gates. These are one-shot/survey runs, **not mesh-convergence
certification**. Every run records the same production Python digest:
`20dcfd39928d69775da0bc57d9a509c8cc649e9a70d2e3034fe9ffbcd0f022fb`.

Linux, Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, explicit allocation of four
CPUs, one-thread control included. Scratch is disk-backed overlay. There is no
Windows execution evidence in this study. RSS is sampled at 10 ms, with the
OS high-water value also saved; RSS is not total machine memory or filesystem
page-cache usage. Raw metadata includes cgroup samples/peaks from the profiler.

| Case | Production forecast GiB | Trial forecast GiB | Trial peak RSS GiB | Trial seconds |
| --- | ---: | ---: | ---: | ---: |
| Dielectric 8,000 unknowns, 181-angle batch | 2.004551 | 1.517609 | 1.190 | 16.95 |
| Dielectric 12,000 unknowns, batch recovers 181→64 | 3.509926 | 2.724420 | 2.361 | 45.29 |

The corresponding explicit-tile-128 references took 18.10 s / 1.188 GiB and
45.27 s / 2.489 GiB. These are single measurements, not evidence of a speedup.
The 12,000-unknown matched-batch-64 reference used 2.360 GiB and took 47.65 s.
The improved forecast primarily allows a feasible run; it does not itself
remove numerical allocations.

Field comparison uses `max(abs(candidate-reference))/max(abs(reference))` over
**every complex field value**, not just dB samples or a few printed values:

- 8,000 unknowns: all 362 fields bitwise equal at matched tile/batch settings.
- 12,000 unknowns: all 362 fields bitwise equal to the batch-64 reference.
  Against the batch-181 reference, difference is `6.3263e-11`.
- Stock automatic tile choice versus explicit tile 128 at 8,000 unknowns:
  `3.4214e-11`. These are existing tile/batch rounding effects; they exceed a
  blanket `1e-11` cross-configuration threshold and are not hidden.
- One-thread control, ellipse, comb, lossless material, and both fallback sizes:
  matched candidate/reference fields are bitwise equal.
- Far quadrature and scatter native entry points forced unavailable: exercised
  at 256 and 2,000 unknowns; medium case recorded 72 attempted native far calls.
  Small native-versus-NumPy comparison was bitwise equal.
- Assembly kernel tables also bypassed in a separate 2,000-unknown case,
  exercising SciPy Bessel/scaled-Hankel evaluation. Candidate versus its matching
  reference is bitwise equal; difference versus table-enabled evaluation is
  `2.2760e-12`. Projection and unrelated native facilities were not globally
  disabled. This is not a claim that every native module was tested unavailable.
- P2/P3 controls retain the original forecast and have bitwise equal fields.

`analyze.py` checks every successful result's high-water RSS against its test
budget, all quality gates, source hashes, complete field arrays, fallback
invocation, the near-spill threshold, the allocation probes and expected refusal.
Full case details and all comparisons are in `VALIDATION_SUMMARY.json`.

## Recommended production sequence

1. Give the formulation resource plan explicit matrix ownership/rule metadata.
   Qualify the normal fused path and preserve the unequal-order allowance.
   This is the smallest well-supported correction, but alone does not unlock
   the reported 1.6 GiB case.
2. Make constrained tile selection and its forecast one coherent plan. Price
   the selected tiles, parked outputs, active scratch, near-store/index peaks,
   and basis width. Preserve explicit tile overrides. Do not shrink a forecast
   without making execution use the priced plan.
3. Replace provisional workspace coefficients with allocation-derived bounds
   or enforceable workspace budgets shared by planner and allocator. Start with
   P1; keep conservative fallback for unsupported paths. Do not copy this study's
   coefficients directly into production.
4. Before distribution, qualify Automatic selection, submission estimates,
   concurrent workers, certification P2/P3 transitions and retained caches, and
   Windows scratch/fallback behavior with the same shared plan. Keep existing
   RAM limits, live checks, disk-space checks and numerical tolerances.

The regional estimator has a similar need for scheduler-lifetime accounting:
its `threads*tile^2*pair_bytes` heuristic is not an explicit three-window-plus-
scratch derivation. This study does not establish a regional underprediction or
change that estimator; other regional allowances can cover the difference.

## Four questions for Claude

1. Can you confirm the direct-destination ownership qualification for every
   public dielectric route, and identify where quadrature-order metadata should
   enter the resource plan so unequal-order/private callers remain conservative?
2. Please derive/check the maximum live P1 buffers for native, NumPy scatter,
   table-free kernels, touching/acute/adaptive near rules and queued tiles.
   Which provisional allowances above can be replaced by actual shared constants
   or runtime-enforced budgets? Include index sorting and tile-record lifetimes.
3. How should the planner choose and record a smaller tile before admission,
   while preserving explicit overrides, cache keys, angle-batch recovery,
   submission conservatism and concurrent reservations? Review the default-versus-
   forced-tile rounding evidence rather than assuming bitwise equivalence.
4. Do you agree to land matrix-ownership correction first and qualify a tighter
   P1 workspace plan separately, with P2/P3/Windows/Automatic coverage required
   before expanding its scope? Please distinguish proved bounds from measured
   examples when reviewing this prototype.

## Reproduction

Use a checkout of the review branch: its production files are still ae08d66's.
Set `ROOT` to that checkout and `STUDY` to this directory. With NumPy, SciPy and
psutil installed in the Python environment:

```bash
export ROOT=/path/to/20261028_GRIM
export STUDY="$ROOT/audits/codex-2026-11-12/dense-assembly-estimate-study"
cd "$STUDY"
python -m zipfile -e evidence.zip .
python analyze.py

# Re-run the two key admissions and negative control (overwrites these results):
python run_study.py "$ROOT" d8000-reference d8000-candidate d8000-refuse-1.3
python run_study.py "$ROOT" d12000-reference d12000-candidate d12000-matched-batch

# All 28 cases, sequential fresh processes:
python run_study.py "$ROOT"
python analyze.py
```

`evidence-manifest.json` gives archive and member hashes/sizes. The archive
contains only this study's synthetic-run results; scripts and summary are also
available directly beside this handoff. Test output is not installed into GHOST.
