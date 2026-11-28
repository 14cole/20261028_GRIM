# GHOST fresh-run implementation and next steps

The release candidate makes a completed sweep quicker to open and predicts the actual matrix size of connected impedance sheets on desktop and HPC. I recommend merging these changes after an independent check of the candidate. The next correctness task is the separate thin dielectric layer forecast. The memory experiments belong in separate changes with their own acceptance tests.

| Checkout | Use |
|---|---|
| [Main at 95f8719](https://github.com/14cole/20261028_GRIM/commit/95f87190956de9197f0d021b0497772818c6f532) | Reproduction baseline |
| [Impedance-sheet fix at 3eab4bb](https://github.com/14cole/20261028_GRIM/commit/3eab4bbc4e89661649cdf9b603739e2ef91356de) | Independently reviewable desktop/HPC change |
| [Candidate at 6621db2](https://github.com/14cole/20261028_GRIM/commit/6621db27b90f7757606312ec99b8b2727a9e8837) | Both fixes, suitable for user testing. Includes the GUI and current-run recovery change |
| [Evidence archive](CHECKS.zip) | Reproduction scripts, measurements, full small-solve fields, large-display fingerprints and per-file SHA-256 manifest |

## User impact

Use the same geometry, settings and **Solve** button. The GUI prepares four numeric columns from the verified, completed frequencies of the open result and shares them across sorting, plotting, summary and export history. This works when opening a partial run as well as when a solve completes. The extra retained columns have a 16 MiB allowance per view (32 bytes per displayed polarization sample, up to 524,288 rows). Larger datasets, an unsuccessful buffer allocation and unsupported sample layouts use the existing lazy access. Old and new displays can coexist briefly during replacement. Qt, sorting, plotted curves and decoded frequency records have their own memory requirements. There is no new preference, on-disk history or reuse of a previous solve.

For connected ordinary impedance sheets, planning now prices the same TE and TM meshes that execution uses. Unsupported TE branches are reported during planning. A corrected size can change Automatic's choice for jobs near a backend cutoff. Both Dense and Compressed remain available. This delivery changes neither the numerical assembly nor the factorization.

## What we independently ran

### Desktop

A fresh Linux process for each checkout drove the offscreen PySide6 Solve completion slot. The 131-frequency fixture had 361 cut angles, both polarizations and 94,582 rows. Initial presentation included table setup, a synchronous plot draw, summary and automatic-export history. The timed fixture used synthetic checkpoint fields and intercepted final file writing. File generation, solver time and exhaustive table inspection are outside the timed phase.

| Desktop measure | Main | Candidate |
|---|---:|---:|
| Initial presentation on the 131-frequency fixture | 18.89–22.39 s | 0.99–1.06 s |
| Verified frequency loads during that phase | 3,668 | 131 |
| Additional reads when inspecting every table cell | 130 | 131 |
| Incremental peak RSS sampled during initial presentation | 11.38–11.43 MiB | 13.52–13.61 MiB |
| Three-frequency bistatic fixture, including filename discovery | 96 reads | 3 reads |
| Three-frequency BoR fixture, both tested channel orderings | 84 reads | 3 reads |
| Seven completed frequencies, initial presentation | 196 reads | 7 reads |
| Recover Completed Run with four of seven present | 48 reads | 4 reads |

Every one of the 472,910 formatted cells and all 262 plotted curves, coordinates and labels matched. Sorting, status and saved history matched. At size, the determined reduction is the read count. The times and sampled RSS cover two fresh processes per checkout on this host. The new work is presentation after solving. The table still fetches complete rows for on-demand cell inspection. An extension with a missing numeric field took one extra read to detect before using the compatible fallback (96 to 97).

Tests also exercised BoR frequency ordering, bistatic export filenames, unequal channel lengths, ordinary and extension rows, the memory cap, result replacement and stale geometry. Damaging a record after discovery was detected. Restoring a verified record permits a retry without reopening the result. A verified partial completion of four out of seven now shows 57% and offers manual export for current geometry. The legacy four-of-eleven case showed 36%. In a separate end-to-end check a real desktop solve worker computed two frequencies per mode, passed the result to the GUI completion slot and automatically published one monostatic file, three bistatic files and one BoR cylinder file. All complex samples and numeric GRIM members matched main exactly. Replacing a fully exported result released its temporary recovery folder and preserved the output files. See `display/`, `display_secondary/` and `desktop/` in the archive.

### Desktop and HPC planning

A 16-panel straight sheet was split into 16 named pieces, with alternating input directions. Each revision ran three public single-mesh paired solves at 1 GHz over 180 monostatic incident angles. We recorded the dimensions of the assembled operators independently of the forecasts.

| Basis | Main forecast TE / TM | Candidate forecast TE / TM | Assembled TE / TM |
|---|---:|---:|---:|
| P1 | 32 / 32 | 17 / 32 | 17 / 32 |
| P2 | 48 / 48 | 33 / 48 | 33 / 48 |
| P3 | 64 / 64 | 49 / 64 | 49 / 64 |

All nine stored numeric columns for all 1,080 polarized samples per revision matched exactly, including the complex field and residual. The three discrete solution checks passed. Both HPC planning loops produced the right counts for each channel individually and in either paired order. A public automatic certification forecast on 88 panels kept its two distinct meshes across P2/P3. PEC, closed surface impedance, bulk dielectric and thin dielectric controls retained mesh sharing and their prior resource estimates. On a 9,992-panel case the TE-only forecast dropped from 10,000 to 9,993 and Automatic selected Dense. The paired forecast still selected Compressed because TM required 10,000 unknowns. That case was planning only. We exercised the public HPC planner locally. A cluster submission and native Windows GUI were outside these runs. See `planning/` in the archive.

## Findings that need a separate change

**1. Thin dielectric layers can still be overestimated.** They share the TYPE 1 geometry label with ordinary impedance sheets but have their own equations. Their solver joins named sections into a physical midsurface after the current resource calculation. On both main and the candidate, three named sections with nine P1 panels forecast **24 TE / 12 TM**, while Dense and Compressed executed **20 / 10**. In a two-section forecast at 4,998 panels and a fixed 24 GiB budget, the existing paired estimate of 10,000 / 5,000 selected Compressed. Pricing the actual midsurface gave 9,998 / 4,999 and selected Dense. That larger case has no solve timing. Ordinary automatic certification already uses P1 on this formulation. Explicit P2/P3 and branched thin-layer inputs can receive forecasts before execution correctly rejects them.

Use one preparation of the physical midsurface and its ordered physical properties across desktop selection, HPC, executing memory admission and assembly. Validate zero contrast, electric-only and magnetic contrast, reversed/disconnected/closed sections, invalid branching, and both certification levels. Early rejection must agree with runtime. A scalar adjustment to the DOF count would leave some consumers pricing a different mesh. See `thin/NOTES.md` and its reproducer.

**2. Sharing region membership lists is the best supported RAM change to implement next.** For 32 dielectric regions and 65,536 unknowns, peak traced allocations during planning fell from **215.04 to 25.44 MiB**. Measured RSS growth during that stage fell from 204.87 to 11.59 MiB. A separate prototype also reduced the state retained by the Compressed coefficient evaluator. In 32 fresh smaller whole solves on two backends, fields matched exactly within each before/after pair. At 1,536 unknowns, one-thread process peaks went from 186.19 to 184.09 MiB for Dense and 201.35 to 197.86 MiB for Compressed. With two threads the Dense peak rose slightly. The 65,536-unknown case ended at planning. Implement only the shared memberships first and confirm equal-wavenumber unions and weighted requests on another layout. Qualify the evaluator separately under actual multiprocess workers before changing memory forecasts. See `regions/README.md`.

**3. Reusing dielectric incident-field data saves a specific batch allocation.** At 8,192 unknowns and 180 angles the eligible RHS construction retained **45.01 → 22.51 MiB**. Seven fresh baseline/candidate pairs covered disk-backed Dense, mixed P1/P2, Compressed, a multi-region fallback, cancellation with restart, and a one-column tail. Full complex fields and residuals matched. The largest full solve used 1,536 unknowns and peaked at **142.14 → 142.10 MiB**. Review moving the projection lookup ahead of geometric reconstruction as a separate small change. Review signed views only after checking all in-place writes, lookup misses, and a real near-limit peak. See `rhs/FINDINGS.md`.

**4. Keep the experimental Local sizing and Dense residency work separate.** Test same-material continuation across segment names against converged references on sharp corners, close gaps, coatings, and changing properties before changing mesh defaults. The experimental Dense memory credit still needs a native 32 GB Windows run under both normal capacity and memory pressure. Record admission, physical reads, private memory, batch widths, residuals and complete fields in both cases. Neither experiment is in this release candidate. [Previous joint review and raw checks](https://github.com/14cole/20261028_GRIM/blob/6a4402361a01cb0ad3e2ca6b5340fa0b911ffd57/audits/codex-2026-11-28/ghost-fresh-run-study/CLAUDE_REVIEW_RESPONSE.md)

The archive contains 153 evidence files. Its SHA-256 is `ca66d4be18b8148314b0c1d8fbd74381479ba6bb2e082431cee3a28980d45ad9`. Each group includes a replay script or command. For the release decision, start with `display/README.md`, `desktop/README.md` and `planning/README.md`.

## Message for Claude

Please review `codex/ghost-display-sheet-planning-2026-11-28` at `6621db27b90f7757606312ec99b8b2727a9e8837` against `95f8719`. **Run independent checks first, then cross-compare with CHECKS.zip.**

1. Use a new split/bent sheet with reversed segments and an ordinary material control. Check actual assembled dimensions, both channel orders on HPC, and every complex field. Distinguish planning from an executed solve.
2. Open a complete and interrupted result on a clean desktop. Exercise BoR and bistatic, damage and restore a frequency record, test export/replacement and the oversized fallback. Compare table, plot, history and final files. If native Windows is available, record host, package versions and memory. Give timings for display and solve separately.
3. Give a merge decision on the two release commits. If a discrepancy occurs, supply a minimal fixture and the measured consequence. Then prioritize an independent thin-dielectric midsurface check. A second review of the same static report adds less value than an independent fixture.
4. For optimization follow-up, isolate plain membership sharing first. Report both the stage peak and whole-process peak and include complete field comparisons before drawing a capacity conclusion. Keep all experiments local to the active job.

The baseline checkout matched all 528 tracked GitHub file hashes before comparison. The four existing Linux libraries loaded their declared exports on this host. All four Linux library files and four Windows DLLs matched their distribution manifests. These Python changes require no native rebuild.
