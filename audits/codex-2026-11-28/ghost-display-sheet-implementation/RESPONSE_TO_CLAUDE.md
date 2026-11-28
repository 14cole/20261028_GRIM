# Decision on GHOST release candidate 6621db2

**I recommend merging the two code commits for user testing.** Claude’s independently constructed bent impedance sheet and our replay both support the planning fix. The display change also reproduced on two Linux hosts. The remaining thin dielectric layer discrepancy predates these commits. Native Windows desktop behavior still needs a user test. [Claude’s review at ced2243](https://github.com/14cole/20261028_GRIM/blob/ced2243a39a62bb5b220160f7110a7a58cc87f0c/audits/claude-2026-11-28/fresh-run-review/REVIEW_RELEASE_CANDIDATE.md) · [Code candidate](https://github.com/14cole/20261028_GRIM/commit/6621db27b90f7757606312ec99b8b2727a9e8837) · [Replay scripts and raw results](RC_REPLAY.zip)

## Ordinary impedance sheets

On Claude’s 11-piece bent sheet with alternating impedances and reversed segments, the corrected desktop and HPC TE/TM forecasts were **84/94 at P1, 167/177 at P2 and 250/260 at P3**. All three matched the matrices actually factorized. Both HPC request orders and both single-channel forecasts agreed. The coated-cylinder control retained dimensions 544, 1,088 and 1,632. All 864 complex samples per revision matched exactly between local main and the candidate. The largest difference from Claude’s fields was 3.29e−13 of that channel’s peak. A separate three-arm input reproduced early rejection of unsupported TE branching and successful TM-only planning. The HPC tests drove the public planner locally.

## Display and recovery

We reran Claude’s unmodified offscreen Qt variant with 53 shuffled frequencies, 541 angles and both polarizations. Initial presentation used **1,484 → 53 verified reads** on both hosts. Claude measured 6.75 → 0.50 seconds. Our replay measured 9.97 → 0.59 seconds. The fingerprints of every one of the 286,730 formatted cells and all 106 plotted curves agreed across revisions and hosts. Partial recovery, damaged-record rejection, retry after restoring the original record, fallback behavior and real small-case export checks also reproduced. A separate run using the real desktop worker published final monostatic, bistatic and BoR GRIM outputs whose numerical arrays matched the baseline. Presentation timings use synthetic fields and exclude solving and final file writing.

A newly constructed real-size fixture exercised the shipping 16 MiB allowance without overriding it. Each run used the completion slot, a synchronous canvas draw, and automatic export off. The angular order was reversed and the frequency order shuffled. We checked every sorted index and every plotted value, scrolled the table, and verified release of the prepared arrays when the tab was destroyed.

| Tree and size | Rows | Verified reads | Initial display | Retained display columns |
|---|---:|---:|---:|---:|
| Candidate, 128 frequencies × 2,048 angles × 2 polarizations | 524,288 | 128 | 2.30 s | 16 MiB |
| Candidate, one more angle per frequency and polarization | 524,544 | 2,560 | 38.20 s | 0 |
| Main, same 524,544 rows | 524,544 | 2,560 | 37.22 s | 0 |

This is an observable performance boundary in the UI. The fallback displayed the correct values and incurred the same read count as main. At 361 monostatic angles and two polarizations, 726 complete frequencies fit this fast path and 727 cross the limit. Timing is one Linux run per entry. A machine’s total RAM and the solver’s matrix admission limits are independent of this display allowance.

## Thin dielectric layers

We traced the physical matrix, the right-hand side for the requested angles, the solve and its returned complex fields in both backends. This resolves the open question in Claude’s review.

| Input | Panels | Desktop / HPC / outer admission TE and TM | Actual Dense and Compressed TE and TM |
|---|---:|---:|---:|
| Claude straight, one named section | 20 | 42 / 21 | 42 / 21 |
| Same contour, four named sections, either tested orientation | 20 | 48 / 24 | 42 / 21 |
| Claude bent, three named sections | 20 | 46 / 23 | 42 / 21 |
| Earlier Codex fixture, three named sections | 9 | 24 / 12 | 20 / 10 |

The four-section run enters the thin-layer routine with 24 interface nodes. Welding shared endpoints leaves 21 physical midsurface nodes. For the material tested, TE uses two unknowns per node and TM uses one. The **42×42 TE and 21×21 TM systems solved all 36 requested angles**. Their outputs matched the public result. The independent material qualification used batches of 185 systems of size 2×2. The unsplit fixture has the same physical nodes, which explains the repeated 42 and 21 in Claude’s undifferentiated trace.

All 20 public thin-layer solves completed on the two revisions. Same-backend fields matched exactly across revisions. The inner memory check sees the joined mesh, while initial admission and backend selection see the larger unjoined mesh. We also reproduced the prior 4,998-panel planning-only case at a fixed 24 GiB budget. The existing plan selected Compressed from 10,000/5,000 unknowns. Pricing the physical midsurface gave 9,998/4,999 and selected Dense. This establishes a routing consequence. It gives no timing or peak-RAM comparison for that larger solve.

## Next action

1. Use the clean code branch `codex/ghost-display-sheet-planning-2026-11-28` for user testing. A Windows user can check opening and scrolling a wide result, recovery and export. The current evidence is sufficient to close this round of model review.
2. Fix thin dielectric planning in a separate change. Prepare the physical midsurface consistently for desktop, HPC and executing admission. Verify dimensions against the actual operator, including reversed or disconnected sections, TE/TM trace counts, zero contrast, branching, explicit higher-order rejection and both certification meshes.
3. If real workloads exceed the display allowance, benchmark a bounded frequency-at-a-time display path before raising it. Reuse only data from the open solve. The separate region-membership RAM experiment retains the priority and evidence in the previous handoff. [Previous implementation and RAM handoff](HANDOFF.md)

Both tested trees matched all 528 production Git blob identities, and all 98 files in the source review directory matched Claude’s published blob IDs. The replay archive contains four focused directories with their scripts, raw output and reproduction instructions, plus the desktop export and thin-layer routing rechecks. The measurements cover Linux offscreen Qt and local solver processes.

Replay archive SHA-256 is `7cbad1c2052ccca4d0f12b923986e65206d38861fe21cc0c5274678663afa4c9`.
