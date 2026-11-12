# Solver workflow experiments: Claude handoff

Branch: `codex/solver-workflow-experiments-2026-11-12`. Baseline: `d9350d64ede3bba018f83785236ffae6d9ab6869`; production code: `cfe005abb803b6218d5b97c16d7d5eb4c22a6883`. This study adds research scripts and evidence only. It does not change solver defaults, GUI options, distribution binaries or numerical release gates.

## Findings and recommended order of work

**Keep Dense and compressed as distinct internal methods behind a simpler Automatic workflow.** This study does not support making Dense a universal replacement. Compressed still used far less RAM on several cases even after the Dense specializations. The 7,168-unknown PEC star is a useful example: ordinary Dense used about 2.47 GiB, sector Fourier about 1.99 GiB, and compressed about 0.49 GiB. Their individual wall times were 43.47, 30.16 and 40.40 seconds respectively. An internal policy can select a speed/RAM tradeoff without adding controls for every research variant.

1. **Highest-value new numerical investigation: verified symmetry and reduced assembly.** The 8,000-unknown PEC circle's clean Dense timing median was 69.67 seconds versus 35.30 for Fourier. Observed ranges were 61.28–75.69 and 33.92–55.06 seconds. The sevenfold star also benefited, so this is more than a circle-only shortcut. Full original-matrix residual and condition checks remained active. Next investigate assembling only independent columns/sectors, while proving geometry/material/basis eligibility and preserving a safe generic fallback. Do not infer eligibility from a shape label or a few sample entries.
2. **Practical workflow priority: finish the already-confirmed Automatic storage-plan fix.** Dense's existing raw disk residuals already provide large RAM savings. The prior review found that Automatic can miss this lean plan when applying its headroom preference. Carry the selected storage/batch plan through execution and replanning. This is a concrete follow-up from the preceding handoff; this research branch does not fix it. Changing raw-spool blocks from 4 to 32 MiB or assembly tile size produced tradeoffs, not a universal new best default.
3. **Investigate selective inverse precision, with realistic expectations.** Complex64 inverse payloads approximately halved that payload, but construction/operator memory dominated total RSS. Early quantization produced only modest total savings in the repeated dielectric and coated-star tests, with no consistent speed benefit. The actual complex64 arithmetic variant did not solve that problem: at 181 angles it took 43.27 seconds versus 43.65 for baseline compressed, with peak RSS about 1.01 versus 1.02 GiB. That is insufficient to claim a speedup. Priority should be sensitive-block double precision, explicit fallback, conversion-workspace accounting and a study with larger inverse ranks, not blanket casting.
4. **Schur TE/TM reuse is a speed candidate, not presently a RAM improvement.** The prototype verified and reused the three common blocks. At 8,000 unknowns, one run took 36.76 seconds versus 43.30 for Dense, but peak RSS increased from about 2.06 to 2.29 GiB. This needs clean timing repeats and an ownership/retained-cache study before promotion. A singular leading block can occur in an invertible full system; the supplied counterexample is refused and demonstrates the need for a full-LU fallback.
5. **Treat out-of-core LU as a capacity route requiring substantial integration.** Bounded disk-factor slabs cut factor-stage RSS substantially, but incurred much more I/O and longer runs. Fusing pivot application with the update reduced traffic. The measured factor tables below are the authority; they do not include disk-backed physical assembly. If long runtimes are acceptable, prototype direct-to-disk assembly and complete resource/cancellation accounting next. A memory map wrapped around an ordinary full LAPACK factorization is not equivalent.
6. **Lossless residual compression is an optional scratch-space investigation.** Circle/coating files retained only 18–26% of their original bytes, but the irregular coated star retained 71–73%. Encoding/decoding slowed the local full workflows. A codec might help on a slower storage device or when scratch capacity is limiting; neither is established here. Keep raw residual spooling as the reference and price worst-case codec buffers and file size.

Two tempting changes should **not** become blanket defaults. Dense mixed precision reliably saved some RAM but often increased total time after refinement. On the coated star, clean Dense repeats were 18.35–18.49 seconds versus 22.11–22.54 for scaled mixed precision; the much slower initial Dense run would have produced a false speedup claim. Separately, the looser compressed preconditioner caused the 8,000-unknown dielectric case to rebuild more tightly: three factor constructions across the polarizations rather than two, and about 0.99 GiB peak RSS versus 0.82 GiB. The automatic recovery preserved accuracy but defeated the intended RAM saving. The raw events show the extra build and larger retained factors.

For generic electrically large, irregular geometry, the longer-term direction remains shared hierarchical bases, directional/multilevel compression and better preconditioning. The kernel experiment below supports the need for cluster/direction design: simple unit-modulus phase scaling cannot reduce a fixed block's singular values. It is not a demonstrated FMM implementation or a capacity prediction for a full-size 15–18 GHz model.

### Accuracy finding from the scale control

The equal-electrical-size 15 GHz control exposed a baseline compressed sensitivity, not a new complex64 regression. Dense amplitudes agreed across the physical rescaling to 7.66e-12, whereas baseline compressed changed by about 1.14e-7. At 15 GHz, baseline compressed versus Dense was 1.139e-7; the fast complex64 inverse changed baseline compressed by only 1.75e-10. Both passed the unchanged discrete-system gates and the analytical RCS check (worst approximately 1.34e-5 dB for that baseline compressed case).

Tightening **operator** compression from 1e-12 to 1e-14 reduced the discrepancy versus Dense to **1.57e-10**. This is evidence for investigating scale-aware compression/error budgeting before chasing further rank or precision reductions. It does not establish the exact offending block or justify a global tighter default. The two original compressed cases remain explicitly flagged against the study-only 1e-8 field-comparison threshold in `VALIDATION.json`; no production gate was relaxed. The final tighter-operator diagnostic overlapped aggregate analysis, so its timing/RSS are not used as benchmark evidence. See `SCALE_CHECKS.json` and its full raw result.

The 8,000-unknown random-RHS factor stress is a second useful negative result: raw in-memory and raw disk LU exceeded the 1e-12 residual bound. Original-matrix double refinement brought all normal/transpose/adjoint probes below the bound. The refined disk test used about **0.318 GiB process RSS versus 2.036 GiB**, but took **149.81 seconds versus 18.78 seconds**. These are standalone factor tests, and the raw failures remain published. This reinforces the need for complete refinement and residual authority in any capacity route.

## Measured coverage and acceptance

Completed **119 workflow attempts**, of which **118 succeeded**, plus **17 standalone factor benchmarks**. Each workflow solves both polarizations. The main cases use 19 incidence angles; a separate dielectric set uses 181. All successful workflows passed the existing quality gate, returned finite complete complex fields, and were compared at matching frequencies, angles and polarizations against Dense. The largest field difference was **1.14e-07** under `max(abs(test-reference))/max(abs(reference))`. This is a global max-norm comparison, not a relative-error claim at every angular null.

Analytical PEC, dielectric and PEC-backed coating cylinder checks covered **186 polarization results**, with worst RCS error **0.00195256 dB** against the repository's series solutions. These analytical controls are independent of the Dense field comparison but are not a new external reference implementation. All **633 original repository blobs** were reverified unchanged after the experiments.

Main models: 4,000/8,000-unknown PEC and dielectric circles; a 4,050-unknown PEC-backed coating; a 4,720-unknown seven-lobed coated star; sevenfold PEC stars with nominal 1,792 and 7,168 panels; and an asymmetric ellipse rejection control. There is also a 15 GHz dielectric case scaled to the same electrical size as a lower-frequency case. It is **not** a full-size 20-foot 15 GHz test. Full raw geometry, actual unknown counts and material data accompany the results.

### Refusals and failures

- `ellipse-fourier-rejection`: `ValueError: Matrix is not sufficiently block circulant`.
- Factor `pec8k.npy` / `dense`: `AssertionError: ('dense', 0, 4.020969762366885e-12)`.
- Factor `pec8k.npy` / `disk512`: `AssertionError: ('disk512', 0, 4.8024526552787624e-12)`.
- Factor `pec8k.npy` / `fused512`: `AssertionError: ('fused512', 0, 4.8024526552787624e-12)`.

## Complete-workflow timing repeats

Seconds and GiB below are medians; parentheses give the observed minimum–maximum, **not confidence intervals**. Performance runs execute sequentially in fresh processes. The final operator14 accuracy diagnostic overlapped aggregate analysis and is excluded from performance comparisons. Matrix-capture baselines and the one run spanning the environment reconnect are excluded from these timing summaries. First-run outliers remain included otherwise. The host is shared and timing variability is substantial; small differences are not evidence of a general speedup.

| Model / backend / variant | Runs | Wall seconds: median (range) | Peak process/tree RSS GiB: median (range) |
|---|---:|---:|---:|
| diel8k / compressed / `baseline` | 3 | 37.86 (36.03–41.10) | 0.827 (0.821–0.853) |
| diel8k / compressed / `inverse32_build` | 3 | 40.24 (38.14–43.82) | 0.799 (0.794–0.828) |
| pec4k / dense / `baseline` | 3 | 14.98 (13.59–19.40) | 0.848 (0.846–0.850) |
| pec4k / dense / `fourier` | 3 | 14.40 (9.81–20.30) | 0.737 (0.694–0.743) |
| pec8k / dense / `baseline` | 3 | 69.67 (61.28–75.69) | 3.034 (3.032–3.040) |
| pec8k / dense / `disk32` | 3 | 85.89 (69.78–174.56) | 1.299 (1.276–1.348) |
| pec8k / dense / `fourier` | 3 | 35.30 (33.92–55.06) | 2.176 (2.139–2.195) |
| pec8k / dense / `mixed` | 3 | 73.81 (70.10–75.68) | 2.594 (2.594–2.598) |
| star / compressed / `baseline` | 3 | 29.73 (28.59–71.16) | 0.473 (0.471–0.481) |
| star / compressed / `inverse32_build` | 3 | 30.97 (28.88–85.98) | 0.447 (0.440–0.449) |
| star / dense / `baseline` | 3 | 18.49 (18.35–70.17) | 1.125 (1.124–1.127) |
| star / dense / `scaled_mixed` | 3 | 22.11 (20.48–22.54) | 0.967 (0.966–0.972) |

## Other targeted workflow measurements

These are individual runs, not repeated speed claims. `baseline` includes the same complete workflow and acceptance checks. Detailed stage times and factor/refinement events are in `SUMMARY.json` and each raw metadata file.

| Case | Actual unknowns | Seconds | Peak RSS GiB | Field difference vs Dense |
|---|---:|---:|---:|---:|
| `diel4k-dense-baseline` | 4000 | 10.64 | 0.596 | 0 |
| `diel4k-dense-fourier` | 4000 | 7.92 | 0.413 | 3.27e-12 |
| `diel4k-dense-schur` | 4000 | 10.23 | 0.652 | 4.72e-12 |
| `diel8k-dense-baseline` | 8000 | 43.30 | 2.056 | 0 |
| `diel8k-dense-fourier` | 8000 | 20.58 | 1.170 | 1.72e-11 |
| `diel8k-dense-schur` | 8000 | 36.76 | 2.294 | 1.37e-10 |
| `diel8k-compressed-baseline` | 8000 | 36.03 | 0.821 | 6.87e-10 |
| `diel8k-compressed-compact` | 8000 | 39.70 | 0.989 | 6.87e-10 |
| `diel8k-compressed-inverse32_fast` | 8000 | 35.48 | 0.866 | 6.87e-10 |
| `star-compressed-inverse32_fast` | 4720 | 35.43 | 0.495 | 4.45e-11 |
| `diel4k-dense-tile64` | 4000 | 10.13 | 0.599 | 9.98e-12 |
| `diel4k-dense-tile128` | 4000 | 9.65 | 0.598 | 1.58e-11 |
| `pec8k-dense-tile64` | 8000 | 63.61 | 3.031 | 3.89e-15 |
| `pec8k-dense-tile128` | 8000 | 52.98 | 3.037 | 3.71e-15 |
| `diel15GHz-compressed-baseline` | 4000 | 15.37 | 0.403 | 1.14e-07 |
| `diel15GHz-compressed-inverse32_fast` | 4000 | 15.15 | 0.421 | 1.14e-07 |
| `diel15GHz-dense-baseline` | 4000 | 9.55 | 0.604 | 0 |
| `diel15GHz-dense-scaled_mixed` | 4000 | 14.60 | 0.479 | 6.33e-12 |
| `diel8k-181-compressed-baseline` | 8000 | 43.65 | 1.021 | 8.41e-10 |
| `diel8k-181-compressed-inverse32_fast` | 8000 | 43.27 | 1.005 | 8.41e-10 |
| `diel8k-181-dense-baseline` | 8000 | 43.82 | 2.168 | 0 |
| `diel8k-181-dense-disk32` | 8000 | 54.96 | 1.200 | 0 |
| `diel8k-181-dense-mixed` | 8000 | 66.70 | 1.789 | 3.58e-11 |
| `star7-1792-compressed-baseline` | 1792 | 7.64 | 0.209 | 5.67e-13 |
| `star7-1792-dense-baseline` | 1792 | 3.90 | 0.264 | 0 |
| `star7-1792-dense-sector7` | 1792 | 3.11 | 0.273 | 6.44e-13 |
| `star7-7168-compressed-baseline` | 7168 | 40.40 | 0.485 | 5.35e-13 |
| `star7-7168-dense-baseline` | 7168 | 43.47 | 2.472 | 0 |
| `star7-7168-dense-sector7` | 7168 | 30.16 | 1.988 | 2.87e-13 |

`diel4k-dense-baseline` includes reference-matrix capture; do not use it as a clean timing denominator. Tile changes are ordinary assembly settings, not changes to the physical operator. Memory figures use the maximum of the outer monitor, runtime profile and process high-water reading.

## Disk-resident factorization measurements

These begin with exact saved physical matrices and use 19 random RHS columns plus separate transpose/adjoint probes. The factor time includes loading/copying the input into the chosen representation. Whole-test time additionally includes solves and full streamed original-matrix residual validation. These are **factor-stage tests**, not full solver timings. All successful probes have original-system normwise backward error at most 1e-12. Random-RHS forward differences are recorded separately in `FACTOR_SUMMARY.json`; a small backward error is not a blanket conditioning guarantee.

| Matrix / factor | Factor seconds | Whole-test seconds | Peak RSS GiB | Kernel read / write GiB | Max backward error |
|---|---:|---:|---:|---:|---:|
| diel4k.npy / `dense` | 1.99 | 3.07 | 0.566 | 0.24 / 0.00 | 5.79e-15 |
| diel4k.npy / `disk128` | 75.77 | 82.23 | 0.089 | 33.25 / 10.43 | 6.06e-15 |
| diel4k.npy / `disk512` | 18.00 | 21.63 | 0.183 | 5.80 / 2.73 | 5.68e-15 |
| diel4k.npy / `fused512` | 11.41 | 14.07 | 0.184 | 4.74 / 2.09 | 5.68e-15 |
| diel4k.npy / `mixed` | 1.32 | 4.61 | 0.488 | 0.24 / 0.00 | 2.49e-18 |
| diel4k.npy / `scaled_mixed` | 2.24 | 5.42 | 0.506 | 0.24 / 0.00 | 2.49e-18 |
| pec4k.npy / `dense` | 1.95 | 3.04 | 0.566 | 0.24 / 0.00 | 4.86e-13 |
| pec4k.npy / `disk128` | 74.20 | 78.87 | 0.089 | 33.25 / 10.43 | 5.53e-13 |
| pec4k.npy / `disk512` | 11.93 | 15.32 | 0.183 | 5.80 / 2.73 | 5.65e-13 |
| pec4k.npy / `fused512` | 11.49 | 14.64 | 0.184 | 4.74 / 2.09 | 5.65e-13 |
| pec4k.npy / `mixed` | 1.20 | 3.48 | 0.458 | 0.24 / 0.00 | 7.25e-15 |
| pec4k.npy / `scaled_mixed` | 1.41 | 3.85 | 0.486 | 0.24 / 0.00 | 8.65e-15 |
| pec8k.npy / `dense_refined` | 13.34 | 18.78 | 2.036 | 0.95 / 0.00 | 2.18e-16 |
| pec8k.npy / `fused512_refined` | 121.61 | 149.81 | 0.318 | 33.36 / 16.04 | 2.39e-16 |

The raw PEC8k Dense, disk512 and fused512 tests stopped at their first residual gate (about 4.0e-12, 4.8e-12 and 4.8e-12). Their incomplete wall times are not compared as successful complete tests. Additional `dense_refined` and `fused512_refined` controls retain those failures and test original-matrix double-precision correction without relaxing the gate. This is a factor-only stress with random RHS; the full physical workflows passed their existing release checks.

Kernel I/O counters are observations on this overlay filesystem, not a storage-device throughput certification. Cgroup anonymous/file-cache timelines are retained too; their absolute values include other processes and existing cache in the cgroup. Low process RSS alone does not imply that the OS used no memory for file cache. `disk128`/`disk512` are slab widths, while workflow `disk4`/`disk32` are residual block targets in MiB; they are different experiments.

## Lossless residual-file compression

| Model | Original bytes per polarization | Compressed/original fractions | Whole workflow seconds | Peak RSS GiB |
|---|---:|---:|---:|---:|
| pec4k | 256000000, 256000000 | 0.182, 0.256 | 26.79 | 0.468 |
| diel4k | 256000000, 256000000 | 0.241, 0.241 | 14.20 | 0.413 |
| coated4k | 262440000, 262440000 | 0.237, 0.241 | 23.43 | 0.442 |
| star | 356454400, 356454400 | 0.710, 0.731 | 27.51 | 0.546 |
| pec8k | 1024000000, 1024000000 | 0.197, 0.264 | 84.99 | 1.214 |
| diel8k | 1024000000, 1024000000 | 0.253, 0.253 | 60.28 | 1.163 |

## Kernel-rank study

| Frequency GHz | Cluster width m | Rank at relative 1e-12 | Rank at relative 1e-8 |
|---|---:|---:|---:|
| 2 | 1 | 15 | 12 |
| 5 | 1 | 21 | 17 |
| 10 | 1 | 30 | 25 |
| 15 | 1 | 37 | 31 |
| 18 | 1 | 41 | 35 |
| 2 | 0.25 | 7 | 5 |
| 5 | 0.25 | 9 | 7 |
| 10 | 0.25 | 11 | 8 |
| 15 | 0.25 | 12 | 9 |
| 18 | 0.25 | 12 | 9 |

## What was implemented for this study

All implementations are research files in this audit directory. They are installed only by the experiment driver inside a fresh process. No production module imports them; GUI controls, mesh generation rules, native binaries, release tolerances and default backend selection are unchanged.

- **Dense mixed precision:** exercise the existing single-precision LU with double-precision refinement, then a new variant that scales rows and columns before the single-precision factorization. Normal, transpose and adjoint solves transform the scaling correctly; residuals use the original double-precision matrix. The existing strict relative-residual stopping criterion is preserved. The existing Dense machinery can fall back to double LU.
- **Compressed inverse storage:** retain the hierarchical operator and exact sample rows in complex128, but store inverse-tree factors in complex64. Compare casting after construction, casting completed nodes during construction, and actually performing the inverse-tree arithmetic in complex64. The last distinction matters: NumPy otherwise promotes a complex64 factor multiplied by complex128 RHS data back to double arithmetic. Outer refinement, original sample-row checks, condition gates and field acceptance remain active. These hooks do not yet provide an explicit precision-restoring fallback or a qualified reduced admission forecast.
- **Compressed tolerance:** start from the existing compact 1e-6 preconditioner instead of the usual 1e-8, while retaining refinement and the automatic tighter rebuild. This tests a cost hypothesis, not a relaxation of the final operator or solution accuracy.
- **Residual storage:** compare existing raw disk spooling with 4 MiB and 32 MiB target blocks, plus a new byte-shuffled, checksummed Zstandard level-1 spool. All original coefficient bits are restored. The codec's extra compression/decompression workspace still needs production admission accounting. The baseline's 64-row minimum also means a nominal 4 MiB target can become a larger block at large matrix dimension.
- **Disk-resident LU:** implement blocked, partial-pivoted complex128 LU with a disk-resident factor, bounded column slabs, flushes and Linux page eviction. A second version combines pivot application and the trailing update in one visit to a column slab. Both support normal, transpose and adjoint solves. These are standalone factor-stage prototypes, not a completed disk-backed assembly workflow. Simply passing a memory map to one monolithic LAPACK call would not provide their bounded working set.
- **Uniform rotational symmetry:** a Fourier factorization for explicitly declared uniform PEC/dielectric circles checks every matrix entry for block-circulant structure. A related sector factorization handles sevenfold PEC geometry with dense local blocks and a Fourier transform across sectors. Both still assemble the full original matrix and check field residuals against it. These are demonstrations of factor reuse through symmetry, not yet the much larger potential gain from assembling only independent sectors/columns.
- **Dielectric TE/TM reuse:** a Schur factorization reuses the three common blocks of the current single-dielectric formulation across polarizations. Every common block is hashed in bounded chunks before reuse. For `A=[[B,C],[D,E]]`, retain `LU(B)`, `Y=B^-1 C`, and `D Y`; factor only `E-D Y` for each polarization. Normal, transpose and adjoint actions retain the original-matrix condition/residual checks. A deliberately invertible matrix with singular `B` demonstrates why a full-LU fallback is required. The prototype refuses that case. Schur and Fourier hooks require an admitted in-memory Dense plan; they do not impersonate a cheaper disk plan.

## Limits that matter before promotion

The current physical operator remains double precision. Halving a preconditioner or LU payload does not halve total solver RAM: original operators, retained polarization partners, assembly buffers and construction workspace remain. A cast performed only after construction cannot remove that construction peak. The experiment changes no production memory forecast to claim otherwise.

The complex64 hooks update the retained inverse payload count after casting, but `astype` temporarily holds old and new arrays. Those conversion allocations and the extra solve buffers are not yet integrated into the construction ledger. These ample-budget experiments do not qualify operation at a tight cap. A production precision policy needs selective double storage for sensitive corrections, an admitted precision-restoring fallback, and explicit peak accounting.

The disk LU tests begin with saved physical matrices. To make them a larger-geometry solver route, assembly must write directly into bounded disk storage, and the complete path needs scratch-space admission, full original-matrix residual evaluation, condition estimation, cancellation, failure cleanup and resource accounting. Linux `MADV_DONTNEED` plus `posix_fadvise` is not a Windows implementation. File cache is OS/cgroup memory, not proof of zero RAM use; the measurements include cgroup anonymous/file observations and kernel-accounted I/O.

A raw complex128 matrix requires `16 N²` bytes; an immutable original plus a disk LU requires approximately `32 N²` bytes before scratch and metadata. At 50,000 unknowns that pair alone is about 74.5 GiB on disk. Moving LU to disk changes the memory working set, but it does not remove cubic factorization work or repeated I/O. It is a possible capacity route when a long solve is acceptable, not evidence that Dense can efficiently cover every high-frequency geometry.

The symmetry prototypes avoid no assembly yet, and require a verified symmetry and compatible DOF ordering. Generic irregular shapes must reject this route. Reusing symmetry for circle/layer families or repeated sectors is promising, but an implementation that assembles only independent data would need its own geometry eligibility proof, residual authority and mesh-convergence qualification. The full-entry checks used here cannot certify a future reduced-assembly implementation by themselves.

Schur reuse currently covers the equal-sized density blocks in the homogeneous single-dielectric route. Extending it to PEC-backed coatings, multiple regions, magnetic contrast, higher-order bases or unrelated frequencies requires separate ownership and algebra checks. The prototype's bounded cache is local to the experiment request, but it is not yet integrated with the production memory ledger. A failed leading block or unstable Schur solve must release failed/retained work before an admitted full-LU fallback.

The codec preserves coefficient values, but adds a dependency and bounded temporary arrays whose peak must be derived. Corruption, truncation and bitwise round-trip controls are supplied. It should not be enabled merely because its files are smaller. Its speed depends on scratch bandwidth, latency, page cache and the number of complete residual passes.

All workflow cases are one-shot surveys. Passing their discrete quality gates and matching their fields is not mesh certification. Circle cases also have analytical cylinder comparisons. These experiments do not qualify Windows, BoR, adaptive/certified workflows, all polynomial orders, junction families, every material contrast, or a full 20-foot 15–18 GHz desktop model.

## Larger architectural investigations

The separate kernel study samples 2-D Helmholtz interactions at 2–18 GHz. It measures far-block ranks for two cluster widths and verifies an important limitation: multiplying rows and columns by unit-modulus phase factors cannot change a fixed matrix's singular values. A simple “remove the oscillatory phase, then take a lower rank” patch is therefore not a rank-reduction solution for that same block. Directional H2/FMM methods need appropriate cluster/direction organization, shared bases and a robust preconditioner; they are a larger architectural project.

For generic electrically large geometry, directional/multilevel compression and better preconditioners remain more promising than attempting to make dense storage universal. Other worthwhile, unmeasured follow-ups are nearby-frequency preconditioner reuse with current-operator residual checks, component/subdomain reuse for repeated parts, and a disk tier for selected compressed payloads. A memory map alone, looser global tolerances, or an attenuation discount inferred from one material is not sufficient qualification for any of these.

Other ideas should remain explicitly unmeasured: recomputing original-matrix residual tiles from geometry could trade kernel work for residual-file I/O; reciprocity-aware storage needs a formulation-specific symmetry proof and a factorization that actually uses compact storage; GPU offload needs a separate VRAM/admission study. None has evidence here sufficient to outrank the measured candidates. In particular, a triangular-input API does not by itself prove half-sized factor storage, and a complex wave operator should not be assumed Hermitian positive definite.

The existing solver already reuses factors across incidence angles. Recommending that again would not add a new optimization. An automatic policy that chooses among qualified internal representations is still preferable to adding research controls to the GUI. The previously confirmed Automatic headroom/storage-plan inconsistency remains a separate, concrete production follow-up; see [the preceding review response](../backend-stress-review-response/RESPONSE_TO_CLAUDE_REVIEW.md).

## Questions for Claude

1. Reproduce the clean timing repeats, including the slow first-run outliers, and distinguish whole-workflow savings from factor/payload savings. Which conclusions survive your hardware and scratch filesystem?
2. Audit block LU pivot application and normal/transpose/adjoint solves, especially the fused disk update. What is the complete live-buffer bound, and how should disk assembly, condition estimation and platform-specific I/O be integrated?
3. Audit complex64 inverse storage and arithmetic independently. Can sensitive leaves/Woodbury corrections stay double, with an admitted double-precision fallback, while still saving meaningful construction RAM at much larger ranks?
4. Review the lossless spool's codec, checksum and failure behavior. Derive its full temporary-memory bound and determine whether an optional disk-space policy is justified on real SSD and slower scratch.
5. Review Fourier/sector ordering and eligibility. Can independent-column/sector assembly preserve the current Galerkin operator and quality evidence without requiring the full matrix first?
6. Review Schur TE/TM reuse, common-block identity, cache lifetime, original-matrix adjoint/condition semantics, and fallback when the leading block is singular. Does it justify a production optimization confined to qualified single-dielectric cases?
7. Review the scaled mixed-precision results and refinement costs. Any change to the inner stopping rule must preserve the final original-system release checks and the reliability of condition probes. Do not promote a faster but less trustworthy result.

8. Investigate the equal-electrical-size compression sensitivity in `SCALE_CHECKS.json`. Which block norm/scale decision causes the baseline difference, and can nondimensionalization or a field-aware error budget improve accuracy without blindly increasing every rank?

## Reproduction

Use the pinned branch/commit stated at the top of this report and a Python environment with NumPy, SciPy, psutil, threadpoolctl and Zstandard. Existing Linux native libraries are used unchanged. The execution host had a 16 GiB cgroup and four allocated CPUs; workflow cases normally reserve 8 GiB and have a 10 GiB process-tree watchdog. Factor tests have an 8 GiB RSS watchdog and a 300-second limit. These are experimental controls, not application RAM limits or a claim of testing a 32 GiB desktop.

Create an empty run directory and copy this audit's Python files into it. Do not copy historical `results/`, `factor_results/` or `RUN_NOTES.json` when intending a fresh run: drivers deliberately skip completed case JSON files. Set `ROOT` below to the repository checkout and run from the new directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python experiments.py "$ROOT"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python followups.py "$ROOT"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_factor_benchmarks.py "$ROOT"
OPENBLAS_NUM_THREADS=1 python test_prototypes.py "$ROOT"
OPENBLAS_NUM_THREADS=1 python test_fourier.py
OPENBLAS_NUM_THREADS=1 python test_sectors.py
OPENBLAS_NUM_THREADS=1 python test_schur.py
OPENBLAS_NUM_THREADS=1 python test_lossless.py "$ROOT"
OPENBLAS_NUM_THREADS=1 python rank_study.py
python analyze_experiments.py
python factor_analysis.py
python repeat_analysis.py
python scale_checks.py
OPENBLAS_NUM_THREADS=1 python analytic_checks.py "$ROOT"
```

`experiments.py` accepts model groups or case names after the checkout path; `followups.py` accepts case names. Run heavy cases sequentially. Initial `capture_matrix` cases write the immutable physical `.npy` matrices used by the factor tests; those large matrices are excluded from the evidence archive and can be regenerated. Initial capture runs are excluded from the clean timing summaries. Complete workflow fields, samples, metadata, monitoring timelines, factor-test solution vectors, logs, geometry files and prototype controls are included in the evidence archive. Archive parts, contents and checksums are described by its manifest.

`SOURCE_IDENTITY.json` verifies the original repository blobs and native binaries. `EXPERIMENT_PROVENANCE.json` explains the staged addition of research variants and the early hook-hash limitation. `RUN_NOTES.json` identifies the environment-reconnection timing exclusion. Preserve refusals and outliers when reproducing; they are part of the result.

To inspect the published raw archive, run `python unpack_evidence.py /tmp/grim-workflow-evidence` from this audit directory. It verifies every part and extracted file. To reanalyse those published results, copy this directory's Python and JSON files into that extraction directory, then run the analysis scripts there. To reproduce new solves, use a separate empty directory as described above. Original matrix `.npy` files are deliberately omitted (about 1.5 GB total); `MATRIX_MANIFEST.json` records their byte hashes, and the capture cases regenerate them. `RESEARCH_SOURCE_MANIFEST.json` hashes the published scripts.
