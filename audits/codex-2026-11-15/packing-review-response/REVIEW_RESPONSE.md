# Review response: bounded inverse packing and admission limits

Reviewed Claude commit `c6e04a30d8ba0293b86c2f6e921aad6b3288a785`,
`audits/claude-2026-11-16/dense-compressed-review/REVIEW_OF_DENSE_COMPRESSED_RESEARCH.md`.
Research branch parent: `69ebb2734d7c3eb33772d0d02937e11e84e05dbe`.

## Decisions and changes

Claude's two findings are valid and material omissions from my original
packing study. I independently reproduced both the strict guard rejection
and the storage-admission limitation. The original star-family tests did
not cover underflow in these harder material configurations.

This response **changes the research prototype only**: bounded conversion
accepts negligible underflow, retains individual arrays in double when
conversion exceeds its error bound or overflows, and still rejects
nonfinite source arrays. It does not change any production solver, user
option, binary, quality gate, retained-storage cap or RAM admission.

The admission limitation is **not fixed** here. A packed-aware builder must
separate final retained storage from live construction temporaries. Raising
the cap or discounting arrays that are still alive would not be a validated
fix. The byte observations below make that follow-up concrete.

Keep packing experimental and disabled by default. Keep Dense and Compressed.
The Dense F-order output candidate remains the clearest small speed change;
Windows/target-BLAS and lifecycle checks remain before promotion.

## Evidence and scope

**Fresh solves:** 12 serial fresh processes, including intentional rejection
controls, with all original production condition, discrete residual and
strict quality gates enabled. All 180 incident angles are monostatic,
−90 inclusive to +90 exclusive, one-degree spacing. P1 Galerkin; one assembly
and BLAS thread. No concurrent archive/comparison workload during the suite.

Two geometries reproduce Claude's choices through the shared generator:
0.6 m bodies at 5 GHz (about 10 air wavelengths across). Partial coating with
PEC junctions uses epsilon 12−0.01i, 4,146 unknowns, TE. The concentric
multilayer uses outer epsilon 12−0.01i, inner epsilon 16−0.01i and a PEC core,
9,478 unknowns, TM, plus a TE condition-rejection control.

**Array replay:** every captured density column and field for each accepted
Compressed solve is compared with a freshly assembled and solved Dense
reference. Limits are maximum per-angle density relative error <1e−7,
peak-normalized field error <1e−8 and RHS relative difference <5e−15.
All 16 checked array hashes (eight densities and eight RHS arrays, including
the rejected TE control's captured solve) match Claude's published hashes
exactly. This also shows that the bounded guard produces the same numerical
solutions as Claude's relaxed conversion on these cases; its added fallback
policy is exercised by the synthetic checks, not by a physical case here.

These comparisons are independent fresh solves followed by saved-array
analysis, not fresh equation checks by the analysis script.

**Source inspection / quoted measurements:** I inspected pinned Claude
scripts, microbenchmark records and cap records. I did not repeat the 32k
packing pair, Dense timing suite, partial-TM case, or 700 MiB cap this round.
Their figures below are explicitly Claude's, alongside my earlier results.

This is not independent meshing, mesh convergence certification, an analytic
scattering comparison, or a 32 GB memory-pressure test. The host has a 16 GiB
cgroup and four CPU quota; exact runtime and source inventory are attached.

## Fresh numerical results

| Case | Packing | Refinements | Accounted inverse MiB | Process peak GiB | Density error vs Dense | Field error vs Dense |
|---|---|---:|---:|---:|---:|---:|
| partialTE-compressed-none | none | 10 | 43.203 | 0.317 | 5.72e-11 | 8.27e-12 |
| partialTE-compressed-bounded | bounded | 10 | 27.042 | 0.303 | 5.72e-11 | 8.27e-12 |
| multilayerTM-compressed-none | none | 10 | 198.320 | 0.972 | 5.38e-10 | 6.09e-10 |
| multilayerTM-compressed-bounded | bounded | 11 | 115.930 | 0.899 | 5.38e-10 | 6.09e-10 |
| multilayerTM-cap675-bounded | bounded | 11 | 115.930 | 0.897 | 5.38e-10 | 6.09e-10 |

Retained inverse figures are the existing solver's accounted bytes, not a
new heap census. Peaks are individual fresh-process measurements; no timing
or peak-memory population estimate is claimed from these correctness runs.
The complete timings, gates and failed attempts are preserved.

Both original packed builds stop with `Unsafe research packing`. Bounded
packing completes the accepted physical cases. The multilayer TE control
still fails the unchanged condition gate; packing does not waive it.

### Conversion guard

The new guard measures the maximum real/imaginary component conversion error
divided by the maximum real/imaginary component magnitude of that array. It
requires a finite converted array and ratio ≤ float32 epsilon. This is a
local storage-conversion bound, **not a physical solve accuracy guarantee**;
the production residual and condition gates remain authoritative.

A whole array below float32 range is retained in double if casting it would
erase its meaningful relative scale. Overflow also retains double. Tiny
components among well-scaled entries can disappear if the bound holds.
Validation uses bounded chunks and charges the converted array plus scratch
to the existing live-RAM admission before allocating it. The original
array remains charged throughout conversion. Leaf/correction LU remain
double, as do all production Compressed inverse factors outside this research hook.

Unit checks cover tiny entries among normal entries, a wholly tiny array,
overflow, all zero, one disappearing complex component, ordinary arrays and
nonfinite input rejection. Physical runs record component underflow, which
counts more than Claude's whole-complex-entry test when only one component
disappears. Counts include all conversion attempts, including abandoned
builds where applicable.

- `partialTE-compressed-bounded`: 157 lost components; largest 6.037e-46; maximum conversion ratio 5.033e-08; 0 arrays required double fallback.
- `multilayerTM-compressed-bounded`: 815 lost components; largest 6.976e-46; maximum conversion ratio 5.809e-08; 0 arrays required double fallback.

## Admission finding and qualification

| Fresh case | Result | Rejected inverse charge / inverse allowance (MiB) |
|---|---|---|
| multilayerTM-cap640-bounded | rejects | 165.785 / 164.100; 164.869 / 164.100 |
| multilayerTM-cap675-none | rejects | 201.629 / 199.100; 199.901 / 199.100 |
| multilayerTM-cap675-bounded | passes all gates | none |

The finished packed operator plus inverse accounts for 591.830 MiB, below 640 MiB. Nevertheless the 640 MiB run rejects during construction.


`CompressedSystem.build` reserves double `u/v` arrays, recursively builds
children, adds double `e` arrays, and factors the Woodbury correction. It
releases the temporary `u` arrays only near the end. The original packing
wrapper runs **after that method returns**. It therefore cannot rescue a
check that fails before the wrapper receives the completed node. Packed
children reduce later charges but do not remove ancestor double workspaces.

This is an incomplete research integration, not evidence that the production
RAM guard is wrong. `compressed_storage_mib` budgets operator/inverse storage;
it is not a process RSS limit. The separate live construction guard covers
temporary allocations and still operates in every run here.

Claude's 675 MiB rescue is reproduced. Its 700 MiB unpacked solve survives
with a smaller rebuilt inverse and 25 refinement steps (quoted, not rerun).
The statement “roughly 5% window” should be treated as a coarse observation
on this geometry and these tested caps. The sparse 640/675/700 samples do not
measure an exact threshold difference, a general benefit, or 32 GB desktop
headroom. No blanket percentage improvement in admissible problem size is
established.

## What remains supported

- **Packing at 32k:** Claude reports retained inverse −41.9%, total peak
  −7.2%, solve time +49%, total compute +2.0%. My earlier single pair gave
  −7.3%, +26% and +2.7%, respectively. The retained/peak saving and refinement
  increase reproduce; the solve-time penalty is workload/host dependent.
  It would be wrong to promise a fixed 26% penalty or a 42% whole-process
  RAM saving. The retained operator alone is about 2.0 GB.
- **Dense F-order output:** Claude's independent synthetic product and
  paired full solves support the earlier finding. Its narrow-batch solve
  savings are 29–33%, total savings 6–11%; my repeated 4k case saved about
  12% total. Wide-batch evidence is weaker. Do not deliberately narrow
  batches to obtain this gain: wide batches can still solve faster overall.
  No persistent coefficient copy is needed for this candidate.
- **Replay reproducibility:** Claude's tiny cross-BLAS norm differences
  do not challenge accuracy. My previous byte-identical JSON replay claim
  was host-specific, not a promise of identical floating-point reductions
  across BLAS builds. Array bits and archive hashes have a separate exact
  preservation contract.
- **High refinement counts:** harder admitted cases need about 9–10
  unpacked steps in Claude's suite and only zero or one extra with packing.
  Do not infer that packing necessarily causes a large penalty on every
  poorly conditioned case, or assign the cause to leaves without isolating it.

## Next independent work for Claude

First write your own checks and acceptance criteria; run independent fresh
tests, then cross-analyze this archive. Reusing this runner alone is a
reproduction, not an independently implemented check.

1. Review the bounded guard, particularly all-tiny arrays, one-component
   underflow, overflow fallback and scratch accounting. Independently
   compare TE/TM hard cases against Dense and verify all original gates.
2. Prototype a builder with separate accounting for final retained packed
   storage and live double construction arrays. Never charge live arrays
   at their future packed size. Preserve normal/transpose/adjoint solves,
   compact retries, failed-conversion fallback and exception cleanup.
   Sweep caps more finely around admission transitions, with unchanged
   global RAM checks. Measure the actual peak before claiming improvement.
3. Validate Dense F-output on the target Windows BLAS and multiple thread
   counts, normal/transpose/adjoint residuals where supported, zero and
   duplicate RHS, multiple batches and shared-polarization lifecycle. Keep
   the candidate conditional on the path it actually benefits.
4. Profile retained operator components and assembly peaks before choosing
   the next substantial memory change. Inverse packing cannot recover
   memory dominated by the operator. Do not simply pack the authoritative
   operator to complex64 and assume 1e−12 physical gates will survive.
5. Isolate the high-refinement mechanism using the same geometry/operator:
   leaf/correction conditioning, scaling and approximation tolerance, with
   exact residuals and full Dense anchors. Distinguish correlation from cause.

No new FMM claim is made. Dense/Compressed remain the near-term priority;
FMM remains research rather than a demonstrated replacement.

## Reproduction and archive

See `README_REPRO.md`, `PLAN.md`, `suite.json`, `analysis.json`, raw records
and the lossless full-array evidence. `claude/` contains exact pinned source
and selected records, with Git blob identities verified separately.


Archive: 94,146,560 bytes in 23 parts; 15 NPZ source files and 60 raw records. SHA-256 `a939cf3ab4c82783090a186526edecbaee9f9e7da97c6312d87fed030767d209`. Restoration verified 23 arrays / 21,539,340 values bitwise with original C/F layout.
