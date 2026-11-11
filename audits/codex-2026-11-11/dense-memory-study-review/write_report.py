import json,statistics
from pathlib import Path
p=Path(__file__).parent
summary=json.loads((p/'comparison-summary.json').read_text())
controls=[json.loads(x) for x in (p/'controls.jsonl').read_text().splitlines()]
assert len(controls)==8,len(controls)
independent=[json.loads(x) for x in (p/'independent.jsonl').read_text().splitlines()]
diagnostic=[json.loads(x) for x in (p/'diagnostic.jsonl').read_text().splitlines()]
assert len(independent)==34 and len(diagnostic)==17
assert len(json.loads((p/'residual-safety-results.json').read_text()))==17
assert len(json.loads((p/'workflow-results.json').read_text()))==5
bycase={r['case']:r for r in independent+diagnostic+controls}
rows=[]
for label,key in [('PEC 8,000','pec8'),('Coated 9,720','coated9720'),('Airfoil 8,666','airfoil3'),('PEC 14,000','pec14'),('Dielectric 8,000','diel8')]:
 a,b=[summary['groups'][key+'-'+variant] for variant in ('default','lean')]
 rows.append(f"{label:18} {a['wall_median']:7.2f} {b['wall_median']:7.2f}   {a['rss_gib_range'][0]:.3f}-{a['rss_gib_range'][1]:.3f}    {b['rss_gib_range'][0]:.3f}-{b['rss_gib_range'][1]:.3f}")
control_rows=[]
for r in controls:
 control_rows.append(f"{r['case']:36} {r['wall']:7.2f}s {r['peak_gib']:5.3f} GiB  "+('refused: '+r['error'].split(';')[0] if r['error'] else 'completed'))
completed=sum(r['error'] is None for r in independent+diagnostic+controls)
text=f'''DENSE MEMORY STUDY: INDEPENDENT REVIEW FOR CLAUDE — 2026-11-11

VERDICT

The Dense memory-saving mechanism is confirmed. Disk-backed original
coefficients and separate polarization assembly materially reduce process RSS
while retaining the existing double-precision LU, full-row residual checks and
fields. The study identifies a real admission limitation. Its observed RSS
numbers are not safe RAM minima, and its proposed fixed preference for lean
Dense over Compressed is not supported across the independently measured cases.

Two separate planning problems deserve work: Dense does not price the disk
residual configuration, and H-matrix admission can miss a large inverse
projection workspace while retaining an optional partner operator. Neither
should be fixed by disabling live memory or numerical gates.

This is a review/evidence branch based on the measured production commit.
Production source and all eight DLL/.so blobs remain unchanged. Diagnostic
runtime patches are experiments, not release-ready implementations.

PINNED SOURCES AND ENVIRONMENT

Study: claude/festive-keller-nj5bje at
  29a9749ce87426c7307a7d68e2f968c7a835dc90
  audits/claude-2026-11-11/dense-memory-study/HANDOFF_DENSE_MEMORY.md
Measured runtime: distribution/grim-open-item-fixes-2026-11-11 at
  d162169876cf53d10ca0f1b7382c94ba5301fb82
Review branch: codex/dense-memory-study-review-2026-11-11

All 523 production blobs were independently verified against d162169 before
running. The study branch's runtime differs from that production pin in the
two cap-resolution files; reproduce against the measured pin or this review
branch, rather than assuming the study branch head is the measured source.
All eight study files were downloaded and checked by Git blob hash.

Linux, AMD EPYC 9V45, Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, 16 GiB cgroup
memory limit, local overlay filesystem. CPU affinity exposes five CPUs; cpu.max
allows four CPUs of sustained execution. Default auto resolves to FIVE assembly
workers. options._usable_logical_cpus checks affinity/SLURM, not cgroup CPU quota.
Explicit four-CPU controls are listed separately. This is an important distinction
from the study's four-vCPU headline, not a claim that all timing differences
are caused by this one factor. Consider honoring CPU quota in future auto sizing.

Solver jobs ran serially, in fresh interpreters. GHOST_* overrides were removed;
OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1 were launch defaults, while explicit
solve profiles requested auto assembly/BLAS. Runtime scopes then chose the
actual teams. Two repetitions reverse Dense/lean order. Times below are local
measurements with a small sample count, not universal speedups. The original
study used Python 3.13 and did not record enough package/BLAS detail to reproduce
its absolute timing environment exactly.

MEASURED RESULTS

Medians of two runs; RSS ranges use the OS high-water mark. Units are seconds
and GiB (2**30 bytes). These are TOTAL process RSS, not RSS minus baseline.
Baseline was approximately 0.055-0.060 GiB here. The dielectric case is already
unpaired, so its lean variant changes only residual storage.

Case               Dense s  Lean s   Dense RSS range  Lean RSS range
{chr(10).join(rows)}

For the four paired bodies, peak RSS falls approximately 54-61%; the median
runtime cost is approximately 28-35%. This is a capacity optimization, not a
speedup over ordinary unconstrained Dense. Every successful Dense variant under the same CPU allocation,
including the study-only lean-forecast experiments, agrees with all 362 baseline
amplitudes to approximately 1e-14 norm-scaled relative error. The exact values
are in comparison-summary.json; no comparison is limited to field_head.

Compressed comparisons, same host/default-auto setup, two runs each:
* Coated 9,720 at 2.4 GiB: 87.88 s median, approximately 1.79-1.81 GiB RSS.
  Lean Dense is much faster (44.71 s), but Compressed uses less process RSS.
* Airfoil 8,666: 23.22 s median, approximately 0.84-0.87 GiB RSS, versus
  lean Dense's 28.20 s and 1.62-1.65 GiB. Compressed wins both measures here.
* PEC 14,000: 60.28 s median, approximately 1.98-2.03 GiB RSS, versus lean
  Dense's 126.77 s and 3.64-3.66 GiB. Compressed wins both measures here too.

The current automatic Dense preference boundary is 10,000 unknowns. The coated
9,720 and airfoil 8,666 cases are below it. The 8,192 threshold for the explicit
Compressed operator is a different decision. The coated case is not evidence
for ordering methods above the automatic Dense boundary.

DMS-01 — MEDIUM: DENSE ADMISSION DOES NOT PRICE DISK RESIDUALS

solver._estimate_memory_gb uses 2*matrix plus RHS/workspace/cache allowances for
ordinary CPU Dense regardless of dense_residual_storage. Explicit disk Dense
is still refused at PEC 8,000/2.0 GiB, coated 9,720/2.2 GiB, dielectric
8,000/1.6 GiB and PEC 14,000/5.5 GiB. Those refusals were independently rerun.

A diagnostic-only replacement discounts exactly one matrix and ADDS two spool
read buffers, retaining the existing max(assembly, solve), caches and all live
gates. It completes PEC/2.0 GiB, coated/2.2 GiB and PEC 14,000/5.5 GiB with the
same full fields. This demonstrates an actionable admission opportunity.
It is not a general production memory model:
* Coated at 1.9 GiB still fails the conservative lean estimate (~1.962 GiB).
  A measured peak rounded to 1.90 GiB does not establish a safe 1.9 GiB budget.
* Dielectric at 1.6 and 2.0 GiB still fails: its assembly floor is approximately
  2.005 GiB with the resolved five workers. Discounting the LU copy alone does
  not fix this floor. Assembly needs its own implementation-based resource model.
* The spool block is at least 256 rows, so it can exceed 16 MiB. It is unsafe
  to assume a universal 16 MiB buffer or a universal 1.2/1.5-matrix total.

A production plan must bind pairing, residual storage, matrix ownership and
CPU/SciPy eligibility before admission and carry the same plan into execution
and worker scheduling. Preserve explicit memory-storage overrides. Discounting
requires an owned, writable, Fortran-contiguous double matrix and an in-place
CPU LU path; a disk option alone does not establish those conditions. Preserve
assembly bounds, process/worker overhead, RHS/condition work and live headroom.

DMS-02 — MEDIUM: H-MATRIX PAIRING AND PROJECTION WORKSPACE CAUSE NON-MONOTONIC FAILURES

The enhanced profiler repeated the coated Automatic ladder twice:
3.4 GiB succeeds; 2.8, 2.2 and 1.9 GiB refuse. Two additional 2.4 GiB runs succeed.
At 2.8 GiB, the plan retains both polarization operators; below the pairing
threshold it retains one. The paired forecast is ~2.460 GiB, but the inverse's
projected block asks for ~0.997 GiB ADDITIONAL workspace while only ~0.769-0.796
GiB remains. The unpaired plan forecasts ~1.806 GiB. The live gate is correctly
refusing the unadmitted allocation; the admission forecast is not a hard upper
bound. The existing compact-preconditioner retry can hit the same projection
requirement, explaining duplicate failed checks in the captured evidence.

The original, unmodified Claude profiler is an important control: it completes
2.2 GiB here, whereas the enhanced profiler refuses it. Extra instrumentation
and allocation history matter at this narrow boundary. Do not present 2.2 GiB
as a universally failing OR universally safe budget. The original profiler
also reproduces the robust 2.4-success/2.8-failure discontinuity. Full raw results
and four-CPU controls are retained:

{chr(10).join(control_rows)}

The four-CPU airfoil control also exposes a reproducibility qualification:
against the five-worker baseline, its Dense field difference is 2.73745e-10,
above the strict 1e-11 audit threshold. Two added four-CPU controls (ordinary
memory/paired and memory/unpaired) are BITWISE IDENTICAL to four-CPU disk/unpaired.
This isolates the difference to the changed CPU configuration rather than disk
storage or pairing. It does not establish cross-thread bitwise reproducibility.
Raw controls retain the original failed cross-CPU checks; the matched checks
are in cpu-matched-comparisons.json. Three coated controls also retain the
approximately 1.389e-6 Compressed forward-field outlier described below.
At four CPUs, airfoil lean Dense takes 24.89 s/1.570 GiB and Compressed takes
21.21 s/0.837 GiB, preserving the counterexample to universal lean preference.

A causal experiment computes the same inverse projection in 64-column blocks,
with a matching workspace bound. The largest projected-block allocation falls
from ~0.997 to ~0.144 GiB. Both 2.8 and 1.9 GiB requests complete. All 362 fields
are BITWISE IDENTICAL to the corresponding paired (3.4 GiB) and unpaired
(2.4 GiB) production results, respectively. Memory and numerical gates remain
active. See causal-comparisons.json and the chunk_projection option in the
isolated diagnostic profiler.

Recommended direction: bound that workspace and make optional partner retention
respect the complete factorization phase. Do not bypass MemoryError, discount
observed ownership, weaken residual gates, or assume a higher cap must preserve
the same plan. The experimental batching needs normal varied-shape/rank,
cancellation, concurrency and allocation-bound review before production use.

DMS-03 — MEMORY AND DISK CLAIMS NEED QUALIFICATION

RSS is not total cgroup/job memory. In the PEC 8,000 disk run, roughly one matrix
also appears in filesystem cache. Workspace cgroup samples demonstrate that
charge; they include the harness and are not isolated job-capacity guarantees.
Ordinary disk cache can be reclaimed; dirty-page writeback and a memory-backed
temporary filesystem have different behavior. A tmpfs residual file consumes
RAM even though its pages are absent from the solver's RSS.

The diagnostic coated disk solve wrote about 3.02 GB and read about 4.54 GB of
characters, but read_bytes was ZERO: reads were served from page cache. Full
residual products and restoration of a reusable original matrix can reread the
file. These local timings do not establish the penalty of evicted pages, slow
storage or network scratch. Capacity planning must account for storage type,
space, concurrent workers and failure paths. ResidualSpool requires one matrix
plus 64 MiB free space; several workers can need several files concurrently.
Software RAM caps in this study are not experiments under 1.9/2.0 GiB OS-enforced
cgroup limits. No hard-limit, Windows or real SLURM/NFS qualification is claimed.

DMS-04 — AUTOMATIC POLICY AND RESIDUAL AUTO ARE DISTINCT

rank_candidates first considers candidates fitting with a 20% memory margin,
then uses the full cap only if none fits with that margin. This explains why
Automatic excludes a 2.331-GiB Dense forecast at a 2.4-GiB cap, and a 3.295-GiB
forecast at 3.4 GiB, while explicit Dense can be admitted. It is an intentional
policy distinction, not evidence that the solver ignored the cap.

Residual auto already checks live copy capacity per factor. At PEC 8,000/2.4
GiB it retains the first original in memory and spools the second: their live
residency differs. That behavior is consistent with the helper's policy. The
missing early disk-aware Dense plan is the main gap; simply rewriting the late
auto switch will not get past preflight. A lean candidate also needs its own
cost, including unpaired assembly and storage I/O, rather than inheriting
ordinary Dense's cost and always winning below a size threshold.

DMS-05 — FULL-FIELD QUALIFICATION AND PROPOSED SHORTCUTS

All CPU-matched Dense comparisons pass the declared 1e-11 full-field threshold
with roughly 1e-14 observed errors. Compressed is an approximate reference
comparison, not bitwise Dense equivalence. In particular, both successful
2.4-GiB coated runs have norm-scaled amplitude difference 1.3895524756623258e-6.
They pass the production gates (retained-operator backward error ~3e-15 and
exact sampled-row backward error below 9e-14) but slightly exceed this audit's
1e-6 forward-field comparison threshold. The maximum RCS difference is about
5.44e-6 dB on the tested non-negligible fields. This is a reported qualification,
not evidence of a new disk-LU regression or a reason to relax the audit threshold.
The bounded unpaired projection retains the same pre-existing field difference.
comparison-summary.json records failures and analyze_results.py deliberately
returns nonzero when they occur; thresholds were not raised to obtain a pass.

Keeping the residual coefficients in complex64 is not a drop-in replacement:
a well-conditioned test gives a backward-error floor of 1.58e-8 against that
rounded copy, versus the current 1e-12 Dense release gate. Sampling rows changes
the full-residual guarantee as well. Neither shortcut is recommended here.

WHERE THE REMAINING MEMORY GOES

The allocation trace finds exactly one 976.56 MiB matrix for PEC 8,000 after
spooling. At the sampled trace peak there is about 1.198 GiB of live tracked
allocation in total. The remainder includes RHS/solution arrays, matvec results,
plane-wave loads, spool read buffers and geometry. Representative tracked sites
include scatter.py's matrix allocation; residual_spool.py's results/read block;
SciPy lu_solve; regions.py's RHS and kernels.py's plane-wave loads.

The allocator also reports about 303 MiB free inside retained arenas in the auto
trace, versus about 146 MiB in the one-thread trace. Free arena capacity is not
itself an RSS measurement, but explains why current live arrays do not equal
process RSS. Native/interpreter allocations and tracer bookkeeping add further
cost. Tracemalloc changes runtime/RSS; those diagnostic runs are excluded from
performance tables. The historical filename 'trace-4threads' refers to the
host quota: its metadata actually resolves auto to five workers. Explicit
four-CPU controls use cpu_allocation_scope(4).

VALIDATION AND EVIDENCE

59 benchmark/control attempts: 34 main reruns, 17 diagnostic/comparison runs,
and eight original-profiler/CPU-allocation controls; {completed} completed and
{59-completed} refused. Refusals include intentional negative admission tests.
Every completed main/diagnostic solve has all 362 amplitudes checked. Successful
controls also retain full fields. Five memory-vs-disk workflow comparisons pass
exactly: survey, certified, adaptive, quadratic basis and two spawned frequency
workers. They use a small synthetic PEC circle; they establish workflow and
spool lifetime behavior, not large-case mesh convergence. The two-worker run
retains CPU/RAM reservations, loses no workers and leaves no temporary files.

Seventeen residual safety checks pass: full-row products, condition estimation,
exact restoration, ownership eligibility, cancellation and file cleanup,
insufficient space, mid-write failure, LU failure, truncated reads, and no RAM
admission bypass on automatic spool failure. The single-precision test documents
why the proposed single-precision storage shortcut is incompatible with the current gate.

The original evidence is 73 attempts: 58 completions and 15 refusals. Its
ff.jsonl contains four leading amplitudes, not the referenced NPZ files. The
quoted compressed-airfoil timing is absent from the committed raw results; the
coated 117 s/2.49 GiB comparison is also not an identifiable row there. These
claims are not independently verifiable from those files alone. Our reruns
supply complete fields, metadata, code, timelines and environment observations.

One test-harness error was corrected: polynomial_degree was initially passed as
a public keyword instead of execution_options['basis_order']. The first three
workflow comparisons had already passed; their results were retained, and the
quadratic-basis and worker cases then passed. The original error log is kept.
No production change was made to obtain passing workflow results. The analysis
runner was changed to record all comparison outliers before returning failure,
rather than stopping at the first one; its thresholds were unchanged.

REPRODUCTION

Check out this review branch with repository dependencies installed. From its
root, choose a fresh output directory; do not append a new run to old evidence.

  ROOT="$PWD"
  REVIEW="$ROOT/audits/codex-2026-11-11/dense-memory-study-review"
  OUT=$(mktemp -d /tmp/grim-dense-review-XXXXXX)
  python "$REVIEW/run_independent.py" "$ROOT" "$OUT"
  python "$REVIEW/run_diagnostics.py" "$ROOT" "$OUT"
  python "$REVIEW/run_controls.py" "$ROOT" "$OUT"
  python "$REVIEW/analyze_results.py" "$OUT"
  python "$REVIEW/analyze_controls.py" "$OUT"

Expect the final analysis to flag the documented low-budget Compressed forward-
field outliers; inspect the JSON, not only its exit status. Diagnostic lean-
forecast refusals at coated/1.9 and dielectric/1.6 or 2.0 are retained results,
not proof that the runner failed. A targeted original-profiler check is:

  python "$REVIEW/claude/profile_dense.py" "$ROOT" '{{"body":"coated","n":6120,"mode":"automatic","options":{{"ram_budget_gib":2.8}}}}'

n is geometry panel count, not always system unknown count: coated n=6120 has
9720 unknowns and dielectric n=4000 has 8000. The scripts record actual system
sizes where metadata provides them. The original profiler reports zero for some
Compressed runs because it observes DenseFactor; that is not a zero-size solve.

validation-details.zip contains full per-run metadata, fields/timelines, logs,
raw independent results, source hashes and this environment description.
Compact result JSON and scripts are directly browsable beside this handoff.
SHA256SUMS.json covers the published review artifacts. The claude/ subdirectory
preserves the eight original study files byte for byte.

RECOMMENDATIONS FOR CLAUDE'S NEXT REVIEW

1. Implement one shared Dense resource plan for CPU-double eligible matrices,
   with ordinary and disk/unpaired choices, rather than a new public backend.
   Price max(assembly, factorization, residual/RHS) and propagate the chosen
   storage/pairing plan through preflight, live gates and worker scheduling.
2. Review the demonstrated bounded inverse-projection change and update its
   workspace model and optional partner-retention decision together. Retain
   cancellation, complete products, all numerical gates and bounded recovery.
3. Compare lean Dense's actual cost with Compressed where both fit. The airfoil
   counterexample rules out a universal fixed ordering; retain measured limits
   and explicit overrides rather than advertising a universally fastest method.
4. Preserve full double residual coefficients. Do not substitute float32 or
   sampled residuals under the same certification/quality labels.
5. Qualify real enforced memory limits, scratch-filesystem behavior and required
   deployment platforms before publishing observed RSS as a supported RAM cap.
   Include effective thread teams and dependency/BLAS details in future studies.
'''
(p/'REVIEW_DENSE_MEMORY.txt').write_text(text)
print('Wrote report',len(text),'characters')
