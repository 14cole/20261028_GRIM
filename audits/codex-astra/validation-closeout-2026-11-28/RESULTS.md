# GHOST release decision after the final Linux validation

**Merge the Line Expansion fix through PR #3. Keep the Dense optimization on its research branch pending a native 32 GB Windows result.** The production PR is source-only. The timing, field arrays, Windows runner and review notes live on this separate evidence branch. [Line Expansion PR](https://github.com/14cole/20261028_GRIM/pull/3)

## Line Expansion

The PR brings the six reviewed files from Claude’s `d0b732f` forward to shipped `ed90b65` and fixes the remaining GRIM crop, angular editing and Assembly orientation handling. Rotated sections-only files keep their body orientation through compatible crops, wraps and interpolations. Embedded bodies and external features use that same orientation. When a physical relabel makes the orientation unknown, Assembly tells the user how to use the original looks or regenerate the base. It checks the full source before the selected subset can hide the edit.

| Public workflow | Before, Claude’s six-file revision | Corrected |
|---|---:|---:|
| Crop a rotated field, reopen and assemble a feature, combined peak-relative field error | 128.73% | 6.75 × 10⁻¹⁶ |
| Relabel 0° as 360° on a rotated body of revolution and assemble a feature, combined peak-relative field error | 128.84% | 7.92 × 10⁻¹⁶ |
| Physically edit one look and omit it in a later subset | Saved a result with 152.17% combined error | Refused before saving |
| Regrid in the same physical frame, peak-relative feature error | 87.16%–88.39% | Below 1.15 × 10⁻¹⁵ |

The fixed version passed 62 pinned tests, 23 behavioral check groups and all 32 public test subprocesses. Tests reopened saved data, evaluated the complex added field separately from the combined field, and exercised Qt opening, incompatible direct-grid inputs and preservation of existing output on cancellation. Twenty-four test programs were repeated in a quiet interval between the Dense jobs to remove interference from the large job’s memory usage. The 99 native-grid comparison values were unchanged. One standalone case now reports the extra warning for a physical edit. The production PR contains eight Python files and is based directly on `main`. [Reproduction](LINE_REPLAY.md) · [Raw test outcomes and test programs](LINE_EXPANSION_CHECKS.zip)

## Paired Linux Dense benchmark

We ran the exact experimental patch on top of shipped `ed90b65` and the shipped version in consecutive fresh processes on the same boot. The fixture was a 24 cm diameter lossy dielectric cylinder over a 20 cm diameter PEC core, εr = 2.8 − 0.06i at 10 GHz, 15,488 linear panels, 23,936 unknowns per polarization, both polarizations and all 360 distinct monostatic directions. Both runs used four cores, automatic residual storage, genuine disk scratch, the original public solver driver and its ordinary memory sensors. The operating system was Linux 6.18.57 on an AMD EPYC 7763, with 16 GiB cgroup RAM. Approximately 9.5 GiB disk scratch was available before each run.

| Measure | Shipped | Corrected |
|---|---:|---:|
| Public solve time | 2,533.418 s | 777.202 s |
| Peak process RSS | 9.445 GiB | 9.544 GiB |
| Peak sampled cgroup anonymous RAM | 9.520 GiB | 9.648 GiB |
| Physical storage reads | 6,316.00 GB | 72.59 GB |
| TM planned batch width | 1 | 256 |
| Outer RHS batches, both polarizations | 362 | 4 |
| Factorizations | 2 | 2 |
| Total RHS columns | 720 | 720 |
| Maximum reported residual | 5.02e-11 | 1.76e-11 |

The corrected version saved **29 minutes 16 seconds**, a **3.26× speedup** in this pair. Physical reads fell 98.85%. Peak process RAM changed by +0.099 GiB. The TM gate identified the retained matrix at tile 128 and credited 9,166,909,440 of 9,166,913,536 bytes.

The same-host maximum complex-field differences, normalized by the corresponding shipped peak, were 0 (bit-identical) for TE and 2.62e-12 for TM. The corrected fields agreed with an independently evaluated analytical cylinder solution to 3.02e-06 TE and 3.08e-06 TM. All 720 values and the complete angle grid were checked. These are errors on the fixed mesh and quantities in this benchmark.

The corrected run went first. Both times come from the unmodified driver's public solve timer. The test launcher paused between jobs for 53.6 seconds after the corrected solver exited so the smaller GUI and field checks had adequate RAM. That interval is excluded from the timings. Other tasks accounted for approximately 5.22% of aggregate cgroup CPU time during the corrected run and 0.24% during the shipped run. The archive contains the host snapshots, raw I/O and memory samples, and CPU context. One pair quantifies this workload on this host. Claude’s earlier Linux run used its original candidate and observed 591.306 s against 2,716.204 s shipped. Those figures and this exact-patch run come from different hosts and implementations. At 11,968 unknowns our previous four ample-memory solves already used wide batches, had bit-identical fields and showed no consistent timing benefit. Neither result establishes the speed on a 32 GB Windows desktop.

To make room on disk, 313 older benchmark verification copies were temporarily packed. After the runs all 313 were restored to their original paths, with their bytes and file metadata verified. The restoration check is part of the raw archive. [Raw production-entry-point measurements and complete TE/TM fields](DENSE_24K_CHECKS.zip) · [Patch under test](https://github.com/14cole/20261028_GRIM/blob/6a7bdc98f43c88c991758c2445f8c445741e84b8/audits/codex-astra/ghost-residency-review-d0b732f/private-matrix-reuse.patch)

## Remaining desktop decision

Keep Automatic as the shipped default. For a desktop with more physical headroom Dense may already use wide batches, and it can choose in-memory residual storage. On an accessible native 32 GB Windows machine, measure the shipped and corrected versions on the same representative mixed-material 180–360 angle job. Record completion and runtime, working set, private commit, system commit headroom and both complex fields. The candidate withholds the new physical credit on Windows. Near the memory boundary this can change whether TM is admitted. The runner supports both the two-coated-body fixture and a user-supplied geometry.

The Windows A/B runner was checked through four actual small Linux solves. Its native working-set, commit and timing outputs on Windows remain unmeasured. A targeted desktop measurement is the next decision point. Re-reviewing this Linux archive would add no desktop evidence. [Native Windows instructions](WINDOWS_AB.md) · [Runner](windows_dense_ab.py) · [Linux control confirming the shared numerical path](WINDOWS_HARNESS_CHECK.zip)
