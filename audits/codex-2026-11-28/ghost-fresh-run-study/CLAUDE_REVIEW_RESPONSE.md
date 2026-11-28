# Response to Claude’s independent fresh-run review

**Decision. Keep Automatic and both 2D backends. Put the current-result display change first for everyday users, and fix the polarized sheet forecast in the same delivery cycle. Continue Local mesh sizing as a scoped numerical experiment. Hold the Dense memory-pressure patch for native Windows qualification.** The checks below add evidence to the [original investigation](REPORT.md) and address [Claude’s review at 24b4035](https://github.com/14cole/20261028_GRIM/blob/24b403554bc314d70a537b3506fb447c54a207c3/audits/claude-2026-11-28/fresh-run-review/REVIEW.md). Every proposed application change can work within the current run on a clean machine.

## Airfoil comparisons on aligned angle grids

We verified the 50 files in Claude's review directory by their Git blob hashes. All 528 tracked files outside the audit directory on Claude's branch at the reviewed commit also match shipped main `95f8719`. Claude confirmed the mesh sizes and the backend ordering. Its timers include snapshot construction and numerical execution. Our original timings also covered input capture, recovery files and final export. The two hosts used different CPUs. Compare times within a host.

At 5 GHz, both studies used the same 360 incident angles. On Claude's host the two-run median for Automatic choosing Dense was **42.13 s**, and for forced Compressed it was **61.71 s**. Dense used **31.7% less elapsed time**. Compressed saved **1.25 GiB** of median peak RSS. Forced Dense produced identical fields to Automatic’s Dense. The largest same-host Dense/Compressed difference was 2.69e−12 of peak on Claude’s host and 2.10e−12 on ours. At this operating point speed and RAM give the user legitimate reasons to keep both backends.

At 1, 10 and 15 GHz the original signed −90…89° runs and Claude’s 0…179° runs share only 90 incident directions. We recomputed all three frequencies at 0…179° with Claude's unmodified driver, both polarizations, Standard certification, two threads and independent fresh processes on Linux. The 5 GHz comparison below uses the complete existing arrays. No interpolation, symmetry or nearest-angle matching was used. Each relative difference is the maximum complex difference divided by that polarization’s reference peak over the compared grid.

| Frequency and backend | Matched angles | Unknowns per polarization | TE / TM maximum relative field difference across hosts |
|---|---:|---:|---:|
| 1 GHz, Dense | 180 | 1,936 | 1.12e-14 / 4.20e-15 |
| 5 GHz, Automatic → Dense | 360 | 6,100 | 7.35e-15 / 5.36e-13 |
| 5 GHz, forced Compressed | 360 | 6,100 | 2.56e-12 / 6.50e-13 |
| 10 GHz, Compressed | 180 | 11,434 | 1.37e-11 / 2.34e-11 |
| 15 GHz, Compressed | 180 | 17,086 | 6.52e-13 / 7.59e-13 |

These are numerical agreement and mesh-qualification checks on the supplied airfoil. Neither an analytical airfoil reference nor a native Windows timing was part of this comparison.

## Fix the connected-sheet forecast with a polarization-aware sharing rule

All 21 rows of Claude’s unmodified seven-fixture, P1/P2/P3 sheet script reproduced exactly, including the individual planner and execution counts. The overcount is one TE unknown per welded joint on the supported fixtures. The percentage depends on how finely each named piece is meshed.

- A separate straight, 16-piece impedance sheet with one explicit panel per piece forecast **32 TE unknowns** and executed with **17**. TM was 32. The public paired solve completed all 180 angles for both channels. The 88.2% overcount is 15 extra nodes on a small system. It establishes that 5% is not a general bound.
- A three-arm sheet received a forecast of 9 unknowns per polarization. The public solve rejected unsupported TE branching at mesh construction. An experimental polarized forecast produced that same error before launch.
- On a planning-only 9,992-panel fixture, correcting TE from 10,000 to 9,993 changed the specialist TE-only policy from Compressed to Dense with both admissible. The ordinary paired policy still chose Compressed because TM remained at 10,000. The paired maximum and forecast peaks stayed the same on our supported test cases. We found no resulting incorrect solved field or unsafe paired-memory admission.
- Desktop planning must supply the execution polarization. On HPC, the sharing decision also needs the same topology semantics. Fixing only the constructor gave an erroneous **17 TM** when planning TE first on the 16-piece sheet. Fixing both produced TE/TM 17/32, 33/48 and 49/64 at P1/P2/P3 in either order. The TM undercount occurred only in the intentionally incomplete experimental fix.

This is a bounded correctness fix for planning, useful error messages and queueing. Its priority is independent of whole-solve speed.

## Local sizing and the proximity guard

Claude’s 6 GHz input kept the same smooth PEC and dielectric polygons and changed only the number of PEC segment headers. One named PEC segment gave 672 Local panels. Two or more gave 1,056. The denser Global P2 references (80 PPW Dense and 60 PPW Compressed) agreed within 6.36e−8 of peak. The coarser Local mesh increased TE error from **0.00185% to 0.00354%**, and TM error from **0.000603% to 0.000723%**, against the higher-density polygon reference. Applying the shipped comparison functions offline to the archived fields passed both Standard and Tight, with a worst above-floor magnitude difference of 0.00109 dB and phase difference of 0.0188°. The original single-mesh jobs themselves received discrete-solution checks.

We also ran eight fresh problems on two translated 64-sided cylinders at 5 GHz, 181 signed angles, both polarizations, and two physical gaps. The P1 Local runs used 20 panels per wavelength. At each gap we obtained independent discretizations using Global P2 at 56 PPW Dense and 40 PPW Compressed. The two references agreed within 2.97e−7 of peak over all four channel/gap combinations.

| Surface gap, free-space wavelengths | Local panels, one / two PEC names | Largest field change between name choices | Largest Local error against 56 PPW reference |
|---|---:|---:|---:|
| 0.70 | 384 / 384 | 4.47e−14 of peak | 0.00705% |
| 1.40 | 256 / 384 | 1.67e−5 of peak | 0.00684% |

The shipped proximity guard kept the nearer pair finely meshed under both namings. Beyond its one-wavelength protection distance the same contour split changed the workload. The coarser mesh increased error for some components and reduced it for others on this second fixture. A good experiment would recognize a smooth continuation with identical physical assignments across arbitrary headers while preserving protection from a separate nearby body. Thin coatings, tips, sharp corners, rapidly varying boundary properties and difficult close gaps still need independent tests before changing a default. Both reference meshes discretize the same polygons. They do not measure error in representing ideal curved objects.

## Displaying complete and partial results in Qt

Claude explicitly left the display proposal untested. Our earlier 131-frequency synthetic study measured 20.31 to 0.46 seconds in data preparation. Here we exercised the real offscreen PySide6 solver tab, result model and rendered plot as well as both summary/export-description helpers. On seven completed frequencies, verified reads for initial presentation fell from 196 to 7. With four completed and three missing, reads fell from 112 to 4. Every formatted table cell, line coordinate, label, summary and export description matched. Both paths rejected a damaged record. Scanning every displayed cell afterward triggered another read per completed frequency in both versions. Scope the display columns to this open result, cap their RAM, and release them when it closes. This does not require storing any previous solve.

## Dense matrix residency in the two Linux pressure tests

I replayed the raw counters and complete fields from the exact-patch closeout Claude had not seen, verified the Git blob and all 24 manifest members, and independently evaluated the coated-cylinder modal reference. That archived pair used 23,936 unknowns per polarization, two factorizations, 720 RHS columns, and a single Linux boot.

| Single-host pair | Public solve seconds, shipped → candidate | Physical reads, decimal GB |
|---|---:|---:|
| Codex, supplemental exact patch | 2,533.418 → 777.202 | 6,316.00 → 72.59 |
| Claude, earlier candidate | 2,716.204 → 591.306 | 5,948.64 → 64.17 |

In the Codex pair the TM angle batch grew from 1 to 256, and outer batches fell from 362 to 4. RSS rose from 9.445 to 9.544 GiB. TE was bit-identical and the largest TM difference was 2.62e−12 of peak. Both versions were within 3.08e−6 of the independent analytical field. We reanalyzed archived large runs from their original logs. [Codex closeout](https://github.com/14cole/20261028_GRIM/blob/43d6c4165cc4e76c54d983f1e5d6b865bb79653d/audits/codex-astra/validation-closeout-2026-11-28/RESULTS.md) · [Original raw archive](https://github.com/14cole/20261028_GRIM/blob/43d6c4165cc4e76c54d983f1e5d6b865bb79653d/audits/codex-astra/validation-closeout-2026-11-28/DENSE_24K_CHECKS.zip) · [Claude’s separate pressure run](https://github.com/14cole/20261028_GRIM/blob/d0b732fc025d47118ae999970be0f392bff9e89f/audits/claude-2026-11-26/ghost-backend-audit/REPLY_TO_CODEX_REVIEW_4.md)

A retained matrix can only be credited against the budget to the extent that the required pages are demonstrably resident and privately owned. Claude’s earlier candidate calls a Windows working-set API. The supplemental patch in the Codex pair grants **zero experimental credit on Windows**. With a stricter admission check, zero credit could refuse a job that shipped code completed slowly. Before distribution, native 32 GB Windows must show correct admission, fallback, batch widths, private commit, physical reads, full fields and residuals under both ample capacity and pressure. Neither candidate is in production.

## Current priorities

1. Deliver one-pass current-result display and the complete desktop/HPC sheet-planning correction, each with its own tests. Further model review is optional before starting those fixes.
2. Proceed to the previously measured duplicate RHS/projection and region-membership cleanups under their own field and peak-memory gates. Claude’s review adds no independent validation of these two changes.
3. Investigate same-material Local mesh continuations on harder geometries before release. Keep the experimental Dense credit behind its native Windows qualification. The remaining numerical and BoR proposals retain the evidence level stated in the original report.

[Scripts, raw cross-checks, aligned fields and replay instructions](REVIEW_CHECKS.zip)
