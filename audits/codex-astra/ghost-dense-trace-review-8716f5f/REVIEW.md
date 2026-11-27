# GHOST Dense disk trace and third-host review

**Decision.** Keep the shipped Automatic selection policy. Claude’s third host confirms the Dense storage and assembly tradeoff at 11,968 unknowns and explains the heavy storage traffic in its 23,936-unknown Dense replay. One targeted Dense improvement warrants a prototype: account for the matrix already retained for the second polarization when choosing how many incident angles to solve together.

I verified the 192 audit files at `8716f5f` and all 528 shipped files at `ed90b65` against GitHub. The field checks, trace calculations, planner probes and new solves are in the evidence archive. [Claude’s reply](https://github.com/14cole/20261028_GRIM/blob/8716f5f22cc76e9f792eaa742be2a669c70e501e/audits/claude-2026-11-26/ghost-backend-audit/REPLY_TO_CODEX_REVIEW_2.md) · [Checks and replay instructions](./CHECKS.zip)

## What reproduced

The corrected summary is byte-for-byte reproducible and keeps the 46, 14 and 5 timing runs from the three Xeon sessions separate. All five new jobs passed. Each new complex field array was bit-identical to an earlier Xeon array for the same mesh, backend and thread count. An independent cylindrical-wave calculation gave maximum complex-amplitude errors of **0.00121% at 11,968 unknowns** and **0.000308% at 23,936**. Percentages use the peak exact amplitude as the denominator.

All four 11,968-unknown runs used the same 10 GHz, 0.24 m diameter coated PEC cylinder, four threads, both polarizations and 360 monostatic directions on host C. There was one run per configuration.

| Execution path | Solve time | Peak process RAM |
|---|---:|---:|
| Dense, residuals in RAM, both matrices assembled together | 84.9 s | 6.84 GiB |
| Dense, residuals in RAM, separate assembly | 90.6 s | 4.95 GiB |
| Dense, residuals on disk, separate assembly | 103.2 s | 2.83 GiB |
| Compressed | 63.0 s | 1.58 GiB |

With assembly held separate, disk storage added 13.9% elapsed time and saved 2.12 GiB. On our earlier EPYC the same comparison added 11.6% and saved 2.17 GiB. Host C's summary records all four jobs, but its Dense–Compressed field-difference table skips the 12k pair because each Dense label includes the storage mode. Comparing the arrays directly gives a worst difference of **1.73 × 10⁻¹⁰** of peak amplitude. The EPYC and host C disk peaks differ by 0.065 GiB, slightly beyond the reply’s rounded 0.05 GiB. [Earlier measurements](https://github.com/14cole/20261028_GRIM/blob/e4ba249bdf90a7a27f8a37805d08a75c3f6d6d6b/audits/codex-astra/ghost-backend-reply-f2f08b5/REVIEW.md)

## What caused the 24k storage traffic

The host C replay took **2,274.0 s (37.9 min)** and peaked at **9.259 GiB process RSS**. Its inclusive linear-solve stage took 1,789.2 s (78.7%), including 514.3 s of triangular solves. The original-coefficient file was 8.537 GiB. During sustained reading the container held about 4.47 GiB in file cache and used about 13.35 GiB total. The process was charged **5,539.89 GiB of storage reads (5.41 TiB)**. Over 99.5% followed the write of the second polarization’s file. Over the sustained phase the average was 3.10 GiB/s. The 12k disk case recorded only 24 KiB of storage reads.

| Inferred operation | Full coefficient-file reads |
|---|---:|
| First polarization (TE), two angle batches | 2 |
| Restore TE coefficients for matrix reuse | 1 |
| Second polarization (TM), 360 one-angle batches | 360 |
| Additional residual checks after TM refinement attempts | 286 |
| **Total** | **649** |

The batch loop, 362 outer solve calls, 648 triangular-solve calls and the first three file-equivalents of reads before the second spool write account for this split. Each correction computes another full residual. Process logical reads amount to 649.01 files and storage-layer reads to 648.90. At 12k the corresponding figures are four outer batches, six triangular solves and approximately seven logical file scans.

This directly diagnoses host C. The same mechanism is consistent with the original **49.3-minute host A** run, which lacks these counters. The 172-second 24k Compressed measurement also belongs to host A. The inclusive linear timer includes computation and reads. The trace cannot assign all of it to I/O wait. [Trace and original logs](https://github.com/14cole/20261028_GRIM/tree/8716f5f22cc76e9f792eaa742be2a669c70e501e/audits/claude-2026-11-26/ghost-backend-audit/results/c_trace24k) · [Dense residual and correction loop](https://github.com/14cole/20261028_GRIM/blob/ed90b65ff89826274adacae01bcfbafe143e9819/tools/GHOST/ghost_backend/linalg/dense.py#L293-L367)

## A narrower change to test

The shipped planner prices the TM phase before the admission check recognizes the matching matrix retained from TE. When that matrix occupies much of RAM, the first calculation can repeatedly narrow the batch down to one. The subsequent check credits the retained matrix and admits the solve with that narrow width. The historical trace did not record TM’s live headroom or selected phase plan. [Planning and admission order](https://github.com/14cole/20261028_GRIM/blob/ed90b65ff89826274adacae01bcfbafe143e9819/tools/GHOST/ghost_backend/twod/solver.py#L2598-L2628) · [Batch narrowing](https://github.com/14cole/20261028_GRIM/blob/ed90b65ff89826274adacae01bcfbafe143e9819/tools/GHOST/ghost_backend/execution/dense_memory.py#L76-L130)

A planner probe on the exact 23,936-unknown geometry supplied 5.0 GiB of live headroom and an 8.537 GiB reusable buffer. Current ordering selected width **1**. Giving the forecast the same verified-buffer allowance used for final admission selected **256**, with a **9.969 GiB** estimated peak below the same **13.537 GiB** allowance. These are controlled inputs. Their historical values were not recorded. If both polarizations could safely use width 256, the current correction loop would require **5–25 full logical scans** for this 360-angle solve, including the TE restore. That is a conditional I/O bound. The large-case elapsed time and actual storage reads under such a plan remain unmeasured.

I also ran three fresh public Dense solves at **1,496 unknowns per polarization**, 968 panels, 10 GHz, over **−90° through +89°**. The script capped only TM's batch width on a disk-backed coated cylinder. TE used one 180-angle batch in every run. At effective TM widths **1, 32 and 180**, the two polarizations and restore together made **182, 9 and 4 full file reads**, respectively. Each solve passed the full residual checks. The complex fields agreed with the widest run within **5.19 × 10⁻¹³** of peak amplitude. This smaller test isolates the read mechanism and does not reproduce host C’s cache pressure.

A second end-to-end control used **728 unknowns and 32 signed incident angles**, a real retained TE matrix, and controlled TM headroom. With current pricing the second polarization used width 1. Giving the forecast the same ownership credit as final admission changed TM to width 32, cutting the total outer batches from **33 to 2**. The effective assembly tile was 128 in both runs. Both retained the full residual and refinement gates, and the complex fields agreed within **3.24 × 10⁻¹⁴** of peak. This reproduces the planner issue with a real buffer and ordinary numerical solves. This review has no timed 24k candidate run. The local scratch filesystem had 6.2 GiB available against the required 8.54 GiB file.

**Next decision for Claude.** Prototype repricing the second polarization after verifying the exact reusable matrix against the effective assembly tile, geometry, materials and ownership. Retain the existing live RAM, commit and shared-request checks and all per-angle residual and refinement checks. Compare current and candidate on the same 24k fixture and host, recording realized TE/TM widths, refinements, restore calls, storage reads, field arrays and peak process and container memory. This offers a direct test of the improvement before considering a residual-algorithm rewrite. Keep Automatic as the desktop default. A representative 32 GB Windows model with 180–360 incident directions remains the test for desktop capacity. This review adds only audit evidence.
