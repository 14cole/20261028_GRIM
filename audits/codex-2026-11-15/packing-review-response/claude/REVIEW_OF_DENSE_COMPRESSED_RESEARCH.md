# Independent review of Codex's Dense/Compressed memory research (commit 4e0d6e0)

Reviewed: `audits/codex-2026-11-15/dense-compressed-memory-research/HANDOFF_DENSE_COMPRESSED_RESEARCH.md`
on `codex/dense-compressed-memory-research-2026-11-15`.
Research only; no production file is changed.

`INDEPENDENT_CHECK_PLAN.md` was written before I opened any of Codex's scripts
or data. It states my hypotheses and acceptance criteria. I had read the handoff
text once, so I was not blind to its conclusions.

## Summary

| Codex decision | My independent result | Verdict |
|---|---|---|
| Do not enable inverse packing by default | Reproduced at 32k: retained inverse −41.9%, process peak −7.2%, refinement 3 → 5 | Agree |
| Packing is a possible memory-pressure option | It admits a capped solve the baseline rejects, but only in a window about 5% wide; and the prototype as written refuses to build on all four of my harder cases | Agree with two new qualifications |
| F-order product output is the promising Dense candidate | Reproduced without any solver, then in paired whole solves: solve −29% to −33% for 16-column batches, bit-identical densities | Agree; meets my acceptance criteria |
| Do not copy coefficients to C order | Not needed: F output alone gives the gain | Agree |
| Keep Dense and Compressed | Nothing here contradicts it | Agree |

Two things Codex's report does not contain:

1. **The packing prototype's safety guard fails on harder physical cases.** On
   a high-contrast low-loss multilayer and a coated-PEC junction, TE and TM,
   every packed build stopped with "Unsafe research packing". The cause is
   entries of magnitude below 1e-45 becoming zero in single precision. With
   that case recorded instead of rejected, all packed solves pass every
   production gate with the same accuracy as unpacked.
2. **Packing rescues a capped solve only narrowly.** Storage admission sees
   the double-precision arrays before they are packed.

## Evidence labels

Fresh solve (FS), fresh microbenchmark (FM), saved-array replay (RP), source
inspection (SI), Codex's measurement (CX).

## 1. Replay of Codex's evidence (RP)

- `unpack_evidence.py`: 320 array files, 436 records, all hashes verified.
- `analyze.py`: 88 cases, 88 completed, 84 comparisons, maximum density error
  5.07366e-11 and field error 1.33949e-10, as reported.
- The replayed analysis is not byte-identical to `analysis.json` here: eight
  `rhs_relative_error` values differ in the fourteenth digit (5.805822085235981e-17
  against …6003e-17). That is norm roundoff on a different BLAS build, and it
  does not affect any conclusion. Codex's "exact match" holds on its host only.

## 2. Dense product output layout

### Standalone microbenchmark (FM)

`product_bench.py`: random complex 8,192-square F-order matrix, no solver code,
alternating order, median of five. Seconds:

| Threads | Columns | `A @ X` (default) | `matmul(A, X, out=F)` | Ratio |
|---:|---:|---:|---:|---:|
| 1 | 8 | 0.369 | 0.155 | 2.4 |
| 1 | 16 | 0.433 | 0.229 | 1.9 |
| 1 | 64 | 0.757 | 0.560 | 1.35 |
| 1 | 180 | 1.612 | 1.448 | 1.11 |
| 1 | 360 | 2.962 | 2.965 | 1.00 |
| 4 | 8 | 0.090 | 0.054 | 1.6 |
| 4 | 16 | 0.126 | 0.064 | 2.0 |
| 4 | 64 | 0.197 | 0.197 | 1.00 |
| 4 | 180 | 0.512 | 0.459 | 1.12 |
| 4 | 360 | 0.811 | 0.840 | 0.97 |

- The layout of `X` does not matter; only the output layout does. NumPy's
  default result is C-ordered.
- Results are bit-identical to a direct `zgemm` call in every multi-column case.
- This matches Codex's table (0.478 → 0.226 at one thread, 16 columns) and its
  caution that wide batches do not benefit.

### Whole solves (FS)

Codex's star harness and hook, my suite (`claude_A.json`), one thread, fresh
processes, order alternated.

| Case | Variant | Solve s | Compute s | Peak GiB |
|---|---|---|---|---:|
| 4,096 unknowns, 360 angles, batch 16 | control ×3 | 8.29, 8.03, 7.84 | 22.1, 21.0, 21.4 | 0.630 |
| | F output ×3 | 5.66, 5.66, 5.67 | 19.0, 19.1, 19.4 | 0.630 |
| 8,192 unknowns, 180 angles, batch 16 | control ×2 | 15.35, 15.74 | 68.6, 67.8 | 2.149 |
| | F output ×2 | 10.42, 10.64 | 64.7, 63.5 | 2.150 |
| 8,192 unknowns, 180 angles, batch 256 | control ×1 | 7.28 | 61.5 | 2.280 |
| | F output ×1 | 6.31 | 59.8 | 2.269 |

- Narrow batches: solve −29% and −33%; total −11% and −6%. The gain is several
  times the spread between repeats.
- Densities and fields are bit-identical between control and F output in every
  pair. This is stronger than a tolerance comparison: the change cannot alter
  results on this BLAS.
- The wide-batch pair is a single comparison and I draw nothing from it.
- Side observation on batching at 8,192: batch 16 saves 0.13 GiB of 2.28
  (6%) and, even with F output, costs 4 s of solve time. For Dense, narrow
  batches buy little because the two matrices dominate.

Verdict: this meets the criteria I set. It is a small, safe candidate for
narrow batches. Still missing before production: Windows/MKL or other BLAS
builds, and the lifecycle tests Codex lists.

## 3. Inverse packing

### 32,768 unknowns (FS)

| Packing | Retained inverse bytes | Peak GiB | Assembly s | Factor s | Solve s | Compute s | Refinement steps |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | 974,777,536 | 3.706 | 437.1 | 48.1 | 30.0 | 516.5 | 3 |
| construction | 566,488,256 | 3.439 | 433.1 | 47.7 | 44.7 | 526.8 | 5 |

- Retained inverse −41.9% (identical bytes to Codex's). Peak −7.2% (Codex:
  −7.3%). Solve +49% here against Codex's +26%; total +2.0%.
- The unpacked run is bit-identical to my 32k Compressed run of the previous
  day. The packed density differs from it by 4.0e-13.
- The operator retains 2,006,649,760 bytes and the process is already at
  2.6 GiB when assembly ends. My hypothesis 5 holds from my own records.

### Harder cases (FS)

My own choices, generated through Codex's geometry builder with production
condition and strict quality gates, 180 angles, 0.6 m, 5 GHz, ten air
wavelengths across:

- **Multilayer:** outer ε = 12 − 0.01i, inner ε = 16 − 0.01i, PEC core;
  9,478 unknowns.
- **Partial coating (junctions):** ε = 12 − 0.01i; 4,146 unknowns.

| Case | Dense condition | Unpacked vs Dense (field / density) | Packed, Codex guard | Packed, relaxed guard vs Dense | Refinement unpacked → packed | Peak GiB unpacked → packed |
|---|---:|---|---|---|---|---|
| Multilayer TM | 6.5e5 | 6.1e-10 / 5.4e-10 | refused | 6.1e-10 / 5.4e-10 | 10 → 11 | 0.996 → 0.920 |
| Multilayer TE | 1.8e6 | gate rejects all methods | refused | gate rejects | — | — |
| Partial TE | 2.3e4 | 8.3e-12 / 5.7e-11 | refused | 8.3e-12 / 5.7e-11 | 10 → 10 | 0.341 → 0.326 |
| Partial TM | 5.7e4 | 2.1e-12 / 9.3e-11 | refused | 2.1e-12 / 9.3e-11 | 9 → 10 | 0.337 → 0.324 |

- "Refused" means the prototype raised `Unsafe research packing` before any
  solve. In the relaxed copy (`claude_hooks_relaxed.py`) I record the lost
  entries instead: 76 to 381 entries per case, largest magnitude 9.1e-46, in
  arrays whose largest entries are 5.6e-7 to 3.3e-4. They are numerically zero.
  Non-finite values are still rejected.
- With the relaxed guard, every packed case that the quality gate admits
  passes all production gates, with accuracy against Dense unchanged to the
  digits shown.
- My prediction that these cases would need "clearly more refinement" when
  packed was wrong: one extra step at most. The unpacked solves already need
  9–10 steps on these cases, against 2–3 on the star.
- Multilayer TE fails the production condition gate (1.81e6 against a limit of
  1e6) for Dense and Compressed alike. That is the gate working on a case I
  made deliberately hard, not a packing result.
- These comparisons use full Dense solutions as the anchor, not sampled rows.

### Does packing rescue a capped solve? (FS)

Multilayer TM. Operator 476 MiB; inverse 198 MiB unpacked, 116 MiB packed.
`compressed_storage_mib` set as shown:

| Cap MiB | Unpacked | Packed (relaxed guard) |
|---:|---|---|
| 560 | rejected | rejected |
| 640 | rejected | rejected |
| 675 | rejected | passes all gates, 11 refinement steps |
| 700 | passes after a smaller rebuilt inverse (171 MiB), 25 refinement steps | passes, 11 steps |

- At 640 MiB the packed result would fit (592 MiB) but is still rejected:
  admission counts each node's double-precision arrays before they are packed.
- So packing does turn a rejected solve into an accepted one, but in a window
  of roughly 5% of the cap, not the 13% its retained saving suggests.
- At 700 MiB the unpacked path survives by rebuilding a looser inverse and
  paying 25 refinement steps; packed needs 11.

Verdict on packing: agree it must not be a default. As a memory-pressure
option it needs (a) a guard that treats sub-single-precision magnitudes as
zero relative to the array scale, and (b) admission that accounts for packed
sizes, before it is worth more than a few percent.

## 4. Points on Codex's report

- The 32k packing figures, the product table and the narrow-batch full-solve
  gain all reproduce on a second host.
- Codex's large-scale packing evidence was one dielectric star family, as it
  says. The guard failure above would not appear there.
- I did not independently test: persistent C-order coefficients, row
  blocking, disk residual storage, RHS compression on/off, the adjoint cases,
  or the lifecycle prototype. I reviewed none of those beyond the replay. My
  microbenchmark makes the C-order copy unnecessary for the gain, which is the
  only statement I make about it.

## 5. Disclosures

- Host: 4 cores, about 15 GiB, OpenBLAS 0.3.31 (Haswell kernels), one thread
  except the four-thread microbenchmark. Timings are single runs unless a
  count is shown. This host's speed drifted by about 25% across earlier
  sessions; all paired comparisons here were run back to back.
- Peak memory for suites C–E is the kernel's figure for the child process,
  taken by my own runner. Suites A and B use the harness's in-process figure,
  the same mechanism as Codex's.
- Suites C–E reuse Codex's geometry builder and its packing hook. The solver,
  gates and Dense anchor are production code, but the geometry generator is
  shared, so a generator error would not be caught by this comparison.
- The first cap choices (640, 560) were uninformative about the window; I added
  675 and 700 after seeing them. All four are reported.
- The evidence-archive unpack ran while suite D was running. Suite D is used
  for accuracy and admission, not timing.
- No failed launches. Non-zero return codes in suites C–E are the refusals,
  gate rejections and cap rejections tabulated above.
- Full densities for the hard cases are not all published (the multilayer
  arrays are 27 MB each). Fields for every case, densities for the partial
  cases, and SHA-256 of every density are included.

## 6. Open items

1. F-output product: repeat on the target Windows BLAS and with several
   threads before proposing production code.
2. Packing: fix the guard and the admission accounting, then re-measure the
   window. Until then it is a few-percent option.
3. The larger Compressed target is the operator (2.0 GB of 3.7 GiB at 32k) and
   the assembly peak. Neither of us has measured an improvement there.
4. The unpacked Compressed solve needs 9–10 refinement steps on the hard
   multilayer and junction cases against 2–3 on the star. Worth understanding,
   given the ill-conditioned inverse leaves measured last round.
5. A 32 GB desktop under real memory pressure is still untested by both of us.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `product_bench.py`, `product_bench_t1.json`, `product_bench_t4.json`, logs
- `claude_A.json` … `claude_E.json` and logs; `claude_run_suite.py`,
  `claude_run_geometry.py`, `claude_run_geometry_relaxed.py`,
  `claude_hooks_relaxed.py`
- `results/`: JSON, hook records, timing, stdout/stderr, fields; partial-case
  densities
- `density_index.json`
