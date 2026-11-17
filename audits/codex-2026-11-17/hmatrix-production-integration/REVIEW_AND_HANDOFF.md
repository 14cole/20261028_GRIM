# HMatrix gather and sequential-build production integration

The reviewed gather-v2 and sequential-construction prototypes are now applied
as actual production code in an isolated candidate. The complete validation
suite passes. This is a production change, unlike the preceding closure reports.
Publication branch: `codex/hmatrix-production-integration-2026-11-17`.
Parent: `c536f7e7ab5dc12692e02c0035d3ad653299905f`, whose production code matches
`5fec63200d48d6dd7536221d992b3e1836a1647c`.

Claude's `1ccbe6db5854e95833dc4c21d9b3b09a3361955b` closes the preceding
operator-identity/lifecycle discussion and explicitly identifies this production
integration as the next task. Its tile-policy counterfactual reinforces the
need to compare operator actions, densities and fields beyond stored hashes.
No further unchanged closure handoff or rerun was needed before this work.

## Change and scope

Three production paths change:

- `compressed/hmatrix.py`: the validated dense `BlockRow.values` fast path
  selects both nonempty one-dimensional integer index arrays at once. It
  avoids copying the full dense partner row. Empty, generic and low-rank
  selections retain the original path and exception-type behavior.
- `compressed/hmatrix_factor.py`: `HMatrixSystem.build` delegates to its own
  builder. The generic `CompressedSystem` ACA/randomized builders are untouched.
- New `compressed/hmatrix_build.py`: preserves small-node compression-before-
  children so dense fallback still works; large nodes build children first,
  then consume the off-diagonal factors sequentially. Writable complex128
  factors are overwritten by child inverse products rather than retaining a
  separate destination. The correction matrix is explicitly charged while
  live across the second child solve, with the reviewed conservative scratch
  allowance. Aligned diagonal queries charge `4q + 1 MiB` within the checked
  HMatrix dense-fallback-size contract. No generic rectangular query receives
  this bound.

The new module is the production form of the reviewed corrected builder,
without research packing, mixed precision or leaf equilibration. Its defensive
copy path also accounts for dtype-size growth and keeps the replacement live
through the child solve. Focused tests exercise that path; normal compression
returns writable complex128 factors and does not need it.

No solve tolerance, residual/condition gate, storage-cap value, backend-choice
policy, UI option or native binary changes. The accepted inverse-upgrade
lifecycle fix is preserved. No Dense or FMM algorithm changes. This branch is
not merged to main and is not a general distribution/platform certification.

## Validation of integrated code

All runs load the candidate production files directly. No gather or sequential
builder research hook is installed. Test wrappers observe execution or inject
explicitly disclosed failure/cancellation conditions.

The selector and diagonal-allocation scripts adapt Claude's independently
authored tests from `audits/codex-2026-11-16/sequential-readiness-review/claude/`
to call the actual candidate implementation. These are fresh executions of
those tests, not a claim that their test design is newly independent. The
focused builder tests and integrated solve harness provide additional coverage.

- 17,700 gather cases versus the original method: zero mismatches in returned
  bytes, dtype, shape or exception type. Includes empty/out-of-range selectors,
  duplicates, negative indices, unsigned indices, strided layouts, signed zero,
  NaN payloads and generic/low-rank selectors.
- Nine focused builder tests: dense algebraic checks for normal, transpose and
  adjoint action, aliased RHS/output, zero and unequal ranks, retained-byte
  accounting, small dense fallback, large rejection propagation, storage
  rejection, correction liveness, copy-path dtype growth and base-builder scope.
- 70 real aligned diagonal-query allocation measurements across star, slot
  and square operators: all fit `4q + 1 MiB`. These are Python/NumPy allocation
  measurements, not a blanket bound for every native allocator or arbitrary query.
- 22 fresh completed field solves, each with 180 monostatic angles from -90
  inclusive to +90 exclusive and 96 independently evaluated exact coefficient
  rows. Full densities, RHS, fields, angles, sampled indices, norms and residuals
  are archived. All actual process return codes are checked.

The physical suite includes 4,096-unknown dielectric star and 2,048-unknown
upgrading dielectric slot systems, Dense references, one/two-thread builds,
condition estimation, real dense fallback after an injected small-node
compression rejection, and cancellation/recovery. It also includes a
1,024-unknown PEC TM native single-layer path with Dense reference; this is
backend algebra/field coverage, not an end-to-end test of the GUI's combined
closed-PEC formulation.

Candidate/baseline density, RHS and field arrays match bit for bit on all
matched-policy comparisons asserted in `analyze.py`, including the medium
performance cases and forced fallback. Candidate threaded/recovered cases match
the ordinary candidate. Dense comparisons pass the recorded relative-density
and peak-normalized-field bounds. Maximum fresh sampled-row backward error:
**1.62885e-13**, below the unchanged 1e-12 gate.
This establishes algebraic agreement on these meshes, not mesh convergence or
independent physical validation of their shared native formulation.

## Cancellation disclosure

The first product cancellation case fired after workers were idle. Its cleanup
and recovery passed, but it is retained as an idle-point check rather than
represented as active-worker evidence. A separate stricter case requires an
active product task before raising; it observed **1** active task(s).
Additional cases cancel inside the in-place child solve and Woodbury correction.

All cases return pending construction bytes to zero, collect failed inverses,
join workers, reset the executor context, and recover to the same complete
solution/field arrays. The failure injections do not change acceptance gates.
These are cooperative backend tests; stalled native calls, GUI abort propagation,
forced process termination and overlapping independent requests are not certified.

## Fresh performance and RAM measurements

Fresh serial processes, assembly one thread and BLAS one thread; two repetitions
per version at 8,192 unknowns, with reversed second-pair order, and one pair at
32,768 unknowns. All performance cases use 180 monostatic angles, no condition
estimation, and identical geometry/material/precision parameters between versions.
No timing conclusion is drawn from instrumented cancellation/fallback cases.

Compute time sums assembly, factorization, solve and far field; it excludes
RHS generation, independent row validation and archive writing. Peak RSS is
read before those validation/archive steps; total process peak is also recorded.

| Case | Compute seconds | Compute peak GiB | Build tolerances | Refinement steps | GMRES columns |
|---|---:|---:|---|---:|---:|
| medium-baseline-1 | 46.15 | 0.701 | [1e-10] | 2 | 0 |
| medium-baseline-2 | 48.37 | 0.701 | [1e-10] | 2 | 0 |
| medium-candidate-1 | 45.46 | 0.687 | [1e-10] | 2 | 0 |
| medium-candidate-2 | 44.65 | 0.687 | [1e-10] | 2 | 0 |
| cap32k-baseline | 717.40 | 3.427 | [1e-10, 1e-06] | 9 | 180 |
| cap32k-candidate | 566.04 | 3.614 | [1e-10] | 3 | 0 |

The medium matched-policy median changed from 47.26 to
45.06 seconds (4.65% lower in these
two samples). Treat this small sample as indicative, not a universal speed claim.

At the 2,900 MiB retained-storage allowance, the 32k case changed from
717.40 to 566.04 compute seconds
(21.10% lower in this fresh pair). Read the build tolerances,
corrections and RSS together: a change in admitted inverse policy is a workflow
benefit under that storage restriction, not a matched-policy kernel speedup or
proof of lower whole-process RAM. The arrays may differ when final inverse
policies differ; their full comparisons and exact-row checks are in `analysis.json`.

In this pair the baseline/candidate stage times were assembly
411.92/493.78 s,
factor 63.77/47.22 s,
and solve 241.14/24.52 s.
Assembly was slower for the candidate in this single pair; the much smaller
solve cost dominates the total improvement. This experiment does not isolate
the cause of that assembly variation. Candidate compute peak RSS changed by
5.47%
relative to baseline. The dominant measured benefit is avoiding the compact
inverse fallback, not a claim of lower peak memory for this large case.

The native star geometries are five-lobed, one homogeneous dielectric,
epsilon=3-0.08j, mu=1, P1 TE. The medium case uses 4,096 panels at k=80; the
large case uses 16,384 panels at k=320, giving 8,192/32,768 unknowns. Radius is
`1+0.2*cos(5*theta)` in arbitrary length units. An enclosing diameter of 2.4
corresponds to at most about 31/122 free-space wavelengths. These are not
layered 20-foot model certification runs.

The host has a 16 GiB cgroup limit and four-CPU quota. Performance runs request
a 12 GiB ledger budget; ordinary physical runs request 8 GiB. Storage allowances
and RAM ledger budgets are different controls. This is not a real-pressure
32 GiB desktop experiment, and does not close the 64k/Windows/GUI open items.

## Isolated gather allocation

`check_gather_allocation.py` measures the actual old/new methods with the input
matrix allocated before tracing. This isolates temporary allocation, not process
RSS or solver throughput. Peak bytes:

| Dense source shape | Selected square | Baseline | Candidate |
|---|---:|---:|---:|
| 256 x 8192 | 149 | 19,888,464 | 487,560 |
| 512 x 16384 | 256 | 68,160,896 | 1,183,256 |
| 1024 x 32768 | 1024 | 553,651,584 | 16,911,896 |

## User-facing consequences

There are no new controls or setup requirements. HMatrix inverse construction
uses the integrated path automatically. Some retained-storage-limited cases
can keep a stronger inverse and finish with less correction work. That stronger
inverse can increase retained and peak RAM relative to a compact fallback;
existing memory admission still applies. The corrected diagonal-workspace
estimate can also reject insufficient headroom earlier than the former
underestimate. It does not add a new arbitrary user RAM limit.

## Handoff for independent Claude review

Please form independent expectations and tests before relying on our harness,
then cross-analyze complete arrays and measurements from the exact production
commit. Focus on:

1. Scope: no accidental change to generic ACA/randomized builders, Dense, FMM,
   precision or numerical gates. Check the aligned-diagonal/fallback contract.
2. Accounting: overwritten U factors, the live correction matrix, copy-path
   dtype changes, fallback rollback and rejected/cancelled build cleanup. Try
   low headroom and a naturally challenging geometry independently.
3. Selector compatibility: challenge empty/invalid/generic indices and special
   payload bits using the actual production method.
4. Numerical checks: normal/transpose/adjoint, condition estimation, forced and
   natural fallback, 180+ monostatic angles, and a different material/geometry.
   Compare densities/fields and operator actions as well as internal hashes.
5. Reproduce the capped workflow result while measuring peak RAM and final
   inverse policy. Do not equate a retained-storage cap with total memory, or
   infer general speedups from the single large pair.
6. Review the concrete production diff for acceptance separately from remaining
   64k, real-pressure, Windows, full GUI/combined-PEC and larger threaded work.

See `README_REPRO.md` for commands and the evidence manifest for lossless
reconstruction. No other message to Claude is sent automatically.
