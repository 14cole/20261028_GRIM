"""Build the handoff from completed checks; no numerical computations."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
a=json.loads((P/'analysis.json').read_text());rows={x['case']:x for x in a['summary']}
scratch=json.loads((P/'scratch-guard-check.json').read_text())
archive=json.loads((P/'evidence/MANIFEST.json').read_text())
verification=json.loads((P/'evidence-verification.json').read_text())
hashes=json.loads((P/'claude-array-comparison.json').read_text())
text=['''# Review of Claude's sequential inverse builder

Reviewed Claude `b0e2ba064d6b6d02d6682fac9f35947d3d2fcb38`,
`audits/claude-2026-11-16/packing-builder-review/REVIEW_OF_PACKING_RESPONSE.md`.
Parent Codex commit: `79618d58db7351fac5580c5c6bd5529d0e91eb4e`.

## Decision

The sequential order is a useful research candidate for admitting the
original inverse under a tighter **retained-storage cap** and avoiding a
slower compact retry. Claude's numerical results reproduce. It is not a
demonstrated substantial process-RAM reduction or a production-ready patch.

I found and corrected two live-allocation accounting gaps in the research
copy. I also added a rank-direction packing guard, tested tighter inverse
tolerances, and corrected our interpretation of the refinement counter.
Production code, binaries, user options and all acceptance gates are unchanged.

## Findings that require corrections

### 1. In-place output does not eliminate solve scratch

`claude_builder.py:solve_in_place` admits only 1 MiB before invoking
`child.solve_into(u,u)`. The production method still allocates leaf LAPACK
outputs, stacked small RHS arrays, corrections and matrix-product results.
Input/output aliasing removes a destination allocation, not these temporaries.
''']
s=scratch['aliased_node_solve']
text.append(f"A fresh, independently constructed 1,024-row tree with 512 RHS columns used **{s['tracked_peak_scratch_bytes']/2**20:.3f} MiB of tracked scratch**, with bit-identical aliased and separate-destination answers, versus the prototype's 1 MiB admission. NumPy tracemalloc is a lower bound on total native scratch; this is already enough to disprove that allowance.\n")
text.append('''
The corrected research copy restores the existing conservative production
allowance `8*u.nbytes + 1 MiB`. Its exceptional read-only/non-double input-copy
path also moves allocation inside a guard and charges the copied buffer
while the original remains live. This is conservative reservation, not a
claim that all of that memory is actually allocated.

### 2. The Woodbury matrix outlives its first allocation step

The sequential builder creates `small`, then packs factors, solves for e2,
and forms the other correction block before factoring `small`. In the
original prototype these intervening guards neither include `small` as a
live array nor charge it through the owner's retained byte count.
''')
o=rows['original-cap640'];c=rows['corrected-cap640']
text.append(f"In the fresh multilayer run I observed {o['uncharged_correction_checks']} such guard entries, with a largest omitted correction matrix of {o['largest_uncharged_correction']/2**20:.3f} MiB. The corrected copy passes `small` explicitly to every intervening construction step; the matched fresh run has {c['uncharged_correction_checks']} observed omissions.\n")
text.append('''
Keeping the production guard function in use does not establish correct
accounting if its allocation-size and live-array arguments omit buffers.
These two issues do not invalidate the reported **retained-storage**
thresholds, but they invalidate an unconditional claim that the prototype
already preserves honest live-RAM admission. The corrected guard retains the
same cap result and numerical arrays in the matched test. Corrections and
validation cover the sequential path with leaf scaling disabled. The copied
leaf-scaling code is retained for source comparison only, not accepted or
validated as part of this corrected candidate.

### 3. “9–10 refinement steps” was an aggregate, not one difficult field solve

Both earlier handoffs used this number too loosely. `refinement_steps` sums
corrections across condition-estimation calls and field solves. The prior raw
records already report `max_refinements=2` unpacked and 3 packed on this
multilayer case. New instrumentation records each call, its transpose mode,
RHS width, phase and tolerance.

| Fresh variant | Initial inverse tolerance | Condition corrections, total | Field corrections (180 columns) | Total corrections | Final inverse MiB | Peak GiB |
|---|---:|---:|---:|---:|---:|---:|''')
for name in ('corrected-none-cap676','corrected-cap640','corrected-cap626-retry','tolerance-1e-10','tolerance-1e-12'):
    r=rows[name]
    text.append(f"| {name} | {r['initial_tolerance']:.0e} | {r['condition_refinements']} | {r['field_refinements']} | {r['refinement_total']} | {r['inverse_bytes']/2**20:.3f} | {r['peak_gib']:.3f} |")
text.append('''
The 626 MiB case retries at 1e−6; its initial setting remains 1e−8 in the
table. Each recorded call states the actual tolerance used. Avoiding this
retry reduces field corrections, a real potential benefit of admission
improvements. It is not evidence that ordinary hard-geometry field batches
require 9–10 corrections.

On this case 1e−10 reduces field corrections from two to one but grows the
inverse from 198.32 to 225.13 MiB (+13.5%). Tightening again to 1e−12 grows it
to 257.00 MiB (+29.6% over baseline) with no further reduction in corrections.
A tighter default could therefore lose the clean admission at a fixed cap;
that policy tradeoff must be tested rather than inferred from the iteration
count alone.

Tighter tolerance is a tradeoff: compare corrections **and** retained
memory. These are single runs on one multilayer; times in the raw records
are descriptive, not an established speedup. Tolerance controls the inverse
approximation used for refinement, not the unchanged final accuracy gates.
I do not recommend a blanket default change from these measurements.

### 4. Two conclusions in Claude's report need narrower wording

- Failure of this leaf-equilibration treatment to reduce the aggregate
  count does not prove leaf conditioning makes no contribution. It supports
  declining that particular optimization on the tested cases. Tolerance
  sensitivity supplies additional evidence, not an exclusive causal diagnosis.
- The production condition estimate invokes normal and **adjoint** inverse
  products (`trans=0,2`), not ordinary transpose (`trans=1`). It therefore
  did not independently exercise all three modes as claimed. Explicit fresh
  tests in this response cover 0, 1 and 2 separately on complex nonsymmetric
  exact matrices, including aliasing, zero and duplicate RHS.

## Packing guard follow-up

Claude's 17 adversarial guard expectations reproduce. Its compensated-factor
counterexample is valid: the original global-array bound can hide an erased
rank direction. My independently generated examples lose about half the
product while satisfying that original storage-conversion bound.

`rank_guard.py` adds the same bound for each **rank direction**: columns for
e1/e2, rows for v12/v21. A per-column rule applied indiscriminately to all four
arrays would not address both roles. Unsafe conversion retains the entire
array in double. This closes the demonstrated scaling counterexamples; it
does not establish a product-relative error bound under arbitrary
cancellation, or a physical accuracy theorem. Production residual and
condition gates remain essential and unchanged.
''')
for r in scratch['rank_checks']:
    text.append(f"- Synthetic `{r['key']}` case: global-guard product relative error {r['global_guard_product_error']:.3f}; rank guard retains double and the error is {r['rank_guard_product_error']:.1f}.")
r=rows['rank-guard-cap640']
text.append(f"\nThe physical multilayer case remains admitted at 640 MiB with {r['double_fallback_arrays']} fallback arrays. A partial-coating TM case also exercises the corrected packed/rank-guard path with a four-thread request and a fresh matched Dense reference.\n")
text.append('''
## Fresh validation and admission results

Ten fresh physical solves, serial fresh processes, all 180 monostatic angles
from −90 inclusive to +90 exclusive. Eight Compressed cases and two freshly
assembled Dense anchors. Original condition estimates and strict discrete
quality gates remain enabled. No archival or other numerical checks overlap
the physical suites.

The geometries reuse Claude's builder: 0.6 m, 5 GHz (about 10 air wavelengths
across). Multilayer TM: 9,478 unknowns, epsilon 12−0.01i outer layer,
16−0.01i inner layer and PEC core. Partial coating TM: 4,146 unknowns, epsilon
12−0.01i with PEC junctions. P1 Galerkin. Multilayer runs request one thread;
the matched partial Compressed and Dense runs request four.

| Fresh variant | Storage cap MiB | Build attempts | Accepted final inverse MiB | Accounted high-water MiB |
|---|---:|---:|---:|---:|''')
for name,cap in (('original-cap640',640),('corrected-cap640',640),('corrected-none-cap676',676),('corrected-cap626-retry',626),('rank-guard-cap640',640)):
    r=rows[name];text.append(f"| {name} | {cap} | {r['builds']} | {r['inverse_bytes']/2**20:.3f} | {r['accounted_high_water']/2**20:.3f} |")
text.append('''
Claude's larger cap sweep is consistent with these results: first-attempt
multilayer thresholds about 709.94 MiB (production/unpacked), 663.27
(production/packed), 674.22 (sequential/unpacked), 627.55
(sequential/packed). The 35.72 MiB order improvement and combined 82.39 MiB
reduction are **cap improvements**, not process-RSS savings. The full sweep
was not rerun here; fresh tests cover the cap cases in the table.

The reported small process-peak change remains a single-case observation.
The operator/assembly is the largest measured remaining memory target, not
a proof that no other substantial optimization is possible.

All eight Compressed solutions are compared across every density column and
field sample with the fresh Dense anchors. Comparisons use per-column
density norm error and peak-normalized field error, not dB subtraction near
nulls. `analyze.py` performs saved-array replay, not new equation evaluations.
''')
text.append(f"\nMaximum density relative error: {max(x['density_relative'] for x in a['comparisons']):.6g}; maximum peak-normalized field error: {max(x['field_peak_normalized'] for x in a['comparisons']):.6g}. The matched accounting-only correction is bit-identical in RHS, density and field to the original sequential builder. {sum(x['matches'] for x in hashes['records'])} of {len(hashes['records'])} fresh RHS/density hashes match Claude's published counterparts; see `claude-array-comparison.json` for individual cases.\n")
text.append('''
Separate fresh synthetic checks cover normal/transpose/adjoint accuracy,
aliased destinations, zero/duplicate RHS, exactly zero off-diagonal rank,
forced dense fallback, a forced read-only input-copy path, injected
cancellation and injected allocation rejection. Weak references verify
builder-owner release after exceptions. Both packed and unpacked variants
are checked. This is fault injection, not actual machine memory exhaustion.

## Limits and decisions for the next handoff

1. Carry the sequential **unpacked** candidate forward only with corrected
   live-allocation accounting. Before promotion, obtain an independent audit
   of these corrections, broader geometries, a large 32k/64k case, and tests
   under actual constrained RAM. Base randomized/ACA CompressedSystem builders
   are unchanged and not validated by these HMatrix-only hooks.
2. Keep packing experimental and disabled by default. Review rank-direction
   fallback, memory accounting, extreme factor scalings and correction
   cancellation independently. No physical case here needed the new fallback;
   the fallback policy is exercised by synthetic tests.
3. Do not infer a new default from the tolerance scan. Repeat paired runs on
   multiple materials, workloads and caps, measuring assembly, factor,
   condition probes and field solves separately. Include the memory cost of
   tighter ranks and the chance of triggering a compact retry.
4. Reject the tested leaf scaling as an optimization with no measured benefit;
   do not declare leaf conditioning eliminated as a contributing mechanism.
5. Continue operator/assembly profiling and target-Windows BLAS validation of
   Dense F-output. Neither is completed by this review, and no new FMM result
   is claimed.

Claude should write independent hypotheses and acceptance criteria, run its
own fresh checks first, then cross-analyze this archive. Priority questions:
Are the live correction and child scratch charges now conservative on all
supported paths? Does rank-direction fallback preserve intended packing
benefits? Do per-call counts and tolerance tradeoffs reproduce? Is there a
measured end-to-end benefit before recommending a production policy change?

The shared geometry/native assembly does not provide independent physical
model validation or mesh convergence certification. This is a 16 GiB cgroup,
four-CPU-quota Linux environment, not the user's 32 GB desktop under pressure.
Source provenance, exact run specifications and failed-attempt observations
are preserved. No performance conclusion is drawn from cross-session clocks.

## Reproduction and complete evidence

See `README_REPRO.md`, `PLAN.md`, both suites, `analysis.json`, checks,
source inventories and `evidence/MANIFEST.json`. Raw records preserve every
run, including the deliberately triggered first-build rejection and retry.
Replayed analysis values match exactly on this host; JSON key ordering
differs because restored NPZ keys are ordered differently. See
`final-verification.json`; all numerical arrays retain their exact bits.
''')
text.append(f"\nArchive: {archive['archive_bytes']:,} bytes, {len(archive['parts'])} parts, {archive['array_files']} source NPZ files and {archive['records']} raw records. SHA-256 `{archive['archive_sha256']}`. All {verification['array_count']} arrays / {verification['array_values']:,} values restored bitwise with C/F layouts preserved.\n")
(P/'REVIEW_AND_HANDOFF.md').write_text('\n'.join(text));print('Wrote REVIEW_AND_HANDOFF.md')
