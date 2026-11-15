# Review of Codex's packing response, with a sequential-build prototype (commit 79618d5)

Reviewed: `audits/codex-2026-11-15/packing-review-response/REVIEW_RESPONSE.md`
on `codex/packing-review-response-2026-11-15`.
Research only; no production file is changed.

`INDEPENDENT_CHECK_PLAN.md` was written before any run this round, with
numerical predictions. I had read Codex's response, its plan and the source of
its new `hooks.py`, but not its results.

## Summary

1. **Codex's bounded guard is sound.** It behaved as I required in 17
   adversarial unit tests of my own. One limitation, which I predicted, is
   real in a synthetic case and did not occur in any physical case.
2. **The admission problem has a small fix, prototyped here.** A sequential
   build that writes `e` over `u` and packs each array as soon as nothing
   needs it in double lowers the storage cap needed for a first-attempt build
   by 35.7 MiB on the multilayer case, with or without packing. Every array is
   charged at its actual current size.
3. **The numbers do not change.** The sequential build's solutions are
   bit-identical to production (unpacked) and to Codex's bounded packing
   (packed), including Codex's archived arrays from its own host.
4. **Process peak memory barely moves** (0.996 → 0.985 GiB unpacked). This is
   an accounting improvement for the storage cap, not a RAM saving.
5. **Leaf scaling is rejected.** It did not reduce refinement steps on any of
   the three hard cases. My hypothesis from the last report fails its own
   test.

## Evidence labels

Fresh solve (FS), fresh unit test (FU), saved-array replay (RP), source
inspection (SI).

## 1. Replay of Codex's evidence (RP)

- `unpack_evidence.py`: 15 array files, 60 records, all hashes verified.
- `analyze.py` on the restored arrays reproduces `analysis.json` exactly.
- `check_conversion.py` exits 0.

## 2. Bounded conversion guard (FU, SI)

`claude_guard_tests.py`, written without reading Codex's `check_conversion.py`.
All 17 expectations met:

| Input | Outcome |
|---|---|
| ordinary; all zero; empty; F-order; non-contiguous view; larger than one chunk | complex64 |
| tiny entry among normal; one lost complex component | complex64 |
| uniform scale 1e-30 or 1e+30 | complex64 |
| all 1e-60; all denormal doubles; uniform 1e-44 (float32 denormal range) | kept in double |
| one 1e300 entry (overflow) | kept in double |
| NaN or Inf in the source | raises |

Limitation (predicted in the plan): the bound is relative to the array's
global maximum. An array with columns scaled 1, 1e-20, 1e-40, 1e-50 converts
"within bound", but its last column is erased (relative error 1.0) and the
third loses precision (4e-6). If the partner factor compensates for those
scales, the product is wrong: my synthetic compensated product has relative
error 0.44.

- Not observed physically. Across all packed physical runs here, the largest
  conversion ratio is 5.8e-8, no array needed the double fallback, and the lost
  components are at most 7e-46 in magnitude.
- It cannot produce a wrong accepted answer: the inverse is only a
  preconditioner and production refinement and gates are unchanged.
- A per-column check would close it. I have not implemented one.

Codex's description of the guard is accurate, including that it is a storage
conversion bound and not a solve accuracy guarantee.

## 3. Sequential build and admission

### What the prototype does (`claude_builder.py`)

Production `build`, for each internal node: compress both off-diagonal blocks
(`u12, v12, u21, v21`), build the children, allocate `e1 = left⁻¹ u12` and
`e2 = right⁻¹ u21` as new arrays, form the Woodbury matrix, then release the
`u` arrays. Codex's hook packs `v12, v21, e1, e2` after `build` returns. At the
root, all six double arrays are charged together.

Sequential build, for nodes above the dense-fallback size:

1. build the children;
2. compress `u12, v12`; solve in place so `e1` overwrites `u12`;
3. compress `u21, v21`; form the Woodbury block that needs `v21, e1` in
   double; pack `e1` and `v21`;
4. solve in place so `e2` overwrites `u21`; form the other Woodbury block from
   double `v12, e2`; pack `v12` and `e2`.

- The in-place solve relies on the production `solve_into` contract ("input
  and output may alias"). No copies were needed in any run.
- The Woodbury matrix is formed from double arrays, exactly as in production.
- Small nodes keep production order so the dense-leaf fallback is unchanged.
- Storage checks and the live-RAM construction guard are the production ones.
  Arrays are charged double while they are double.

### Uncapped runs: accounted inverse storage (FS)

Multilayer TM, 9,478 unknowns, operator 475.90 MiB. MiB:

| Build | Packing | Final inverse | Accounted high-water | My prediction | Refinement | Peak RSS GiB | Density vs Dense |
|---|---|---:|---:|---:|---:|---:|---:|
| production | none | 198.32 | 234.04 | 223 | 10 | 0.996 | 5.38e-10 |
| production | bounded (Codex) | 115.93 | 187.37 | 167 | 11 | 0.921 | 5.38e-10 |
| sequential | none | 198.32 | 198.32 | 198 | 10 | 0.985 | 5.38e-10 |
| sequential | bounded | 115.93 | 151.65 | 142 | 11 | 0.919 | 5.38e-10 |

- My predictions for the production order were 5–11% low and for sequential
  packed 6% low; I estimated root ranks roughly. The direction and the
  sequential-unpacked figure were right: without packing the sequential build
  never exceeds its final size.
- Bit-identity: sequential-none equals production-none; sequential-bounded
  equals production-bounded, and equals Codex's archived
  `multilayerTM-compressed-bounded` and `-cap675-bounded` densities.
- The partial-coating TE and TM cases (4,146 unknowns) show the same pattern:
  high-water 48.96 → 43.20 unpacked and 38.56 → 32.80 packed (TE), with
  bit-identical densities and unchanged refinement counts.

### Capped runs: thresholds confirmed (FS)

Threshold = operator + accounted high-water. Each was bracketed:

| Build | Packing | Predicted threshold MiB | Cap just below | Cap just above |
|---|---|---:|---|---|
| production | none | 709.9 | 708: first build rejected | 711: clean |
| production | bounded | 663.3 | 662: first build rejected | 665: clean |
| sequential | none | 674.2 | 673: first build rejected | 676: clean |
| sequential | bounded | 627.6 | 626: first build rejected | 629: clean |

- "Clean" means one build, the uncapped inverse size and the uncapped
  refinement count (10 or 11), all gates passed.
- "First build rejected" here was followed by production's smaller retry
  inverse, which passed all gates with 25 refinement steps. So just below a
  threshold the solve still succeeds, more slowly. At lower caps (640 and 560
  in earlier rounds) the retry is rejected too and the solve fails.
- At 640 MiB, the case Codex highlighted (packed result 592 MiB fits but is
  rejected), sequential-bounded is clean.
- Sequential ordering lowers the clean threshold by 35.7 MiB (5.0% of 710)
  with or without packing. Packing lowers it by 46.7 MiB. Together 82.3 MiB
  (11.6%).

### What this does and does not show

- It answers Codex's item 2 for this geometry: separate, honest accounting
  moves admission close to the final retained size.
- It does not reduce process memory. Peak RSS changed by about 1%, because the
  process peak is set by the operator and assembly, not by these transients.
- One geometry for the capped sweep; two more (partial TE/TM) for the
  uncapped accounting. No 32k run. No timing claim: wall times differ by 1–2 s
  in 85 s single runs.
- Not tested: cancellation or exceptions mid-build, the randomized/ACA
  builders of the base `CompressedSystem`, multi-threaded range products.
  Transpose and adjoint solves are exercised by the production condition
  estimate in every run, and the bit-identical densities and equal condition
  estimates cover the normal solve.
- A tighter variant would form the Woodbury matrix from packed arrays and
  never hold two blocks' doubles at once. It changes the numbers, so I did not
  mix it into this comparison.

## 4. Leaf scaling: rejected (FS)

Each leaf block is scaled by its own row and column maxima before LU; solves
are adjusted for normal, transpose and adjoint.

| Case | Refinement, unscaled | Refinement, leaf-scaled | Packed, unscaled → scaled |
|---|---:|---:|---|
| Partial TE | 10 | 10 | 10 → 10 |
| Partial TM | 9 | 9 | 10 → 10 |
| Multilayer TM | 10 | 10 | 11 → 12 |

- All gates pass and accuracy against Dense is unchanged to the digits shown.
- By the criterion I set, the idea is rejected. Reducing the raw apply error
  by about 60% (last round's measurement) does not change how many refinement
  steps these cases need.
- Consequence for Codex's item 5: the 9–10 steps on hard cases are not
  explained by leaf conditioning. The approximation tolerance of the inverse
  is the next suspect, untested.

## 5. Points on Codex's response

- Agreed: packing stays experimental and off by default; the admission
  limitation was an incomplete integration, not a fault in the production
  guard; my "roughly 5% window" was a coarse observation. The thresholds above
  replace it for this geometry: Codex's hook admits cleanly from 663 MiB and
  unpacked production from 710 MiB.
- Agreed: the solve-time penalty of packing is host dependent.
- Not done by me this round: Windows BLAS for the F-output product, operator
  and assembly profiling, any 32k run.

## 6. Disclosures

- Suites F and G reuse Codex's geometry generator and its `convert()`
  function; the builder, accounting instrumentation and guard tests are mine.
  Dense anchors are my fresh Dense solves from the previous round, on the same
  generated geometry.
- Peak RSS is the kernel's figure for the child process.
- The evidence replay and the guard tests ran while suites F and G were
  running. No timing conclusions are drawn from those suites.
- No failed launches. No run returned an error in suites F or G.
- The capped thresholds were predicted from the uncapped runs and then
  tested; the caps were chosen after seeing the uncapped high-water marks.
- Full densities are not published this round (their hashes are in
  `density_index.json`); fields and all JSON records are.

## 7. Open items

1. If packing or tighter caps are ever wanted, the sequential build is the
   piece worth carrying forward, with exception-path and threaded tests.
   On its own, without packing, it lowers the clean cap by 5% at no numerical
   change.
2. The process peak is the operator and its assembly. That is still the only
   place a substantial Compressed memory reduction can come from, and neither
   of us has measured one.
3. Why hard cases need 9–10 refinement steps: test the inverse tolerance next.
4. F-output product on the Windows BLAS; a 32 GB machine under real pressure.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_builder.py`, `claude_run_geometry2.py`, `claude_run_suite.py`
- `claude_guard_tests.py`, `.json`, `.log`
- `claude_F.json`, `claude_G.json` and logs
- `results/`: JSON, stdout/stderr and fields for all 27 runs
- `density_index.json`
