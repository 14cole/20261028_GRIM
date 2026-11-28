# Release decision for thin dielectric planning

Merge the thin-layer planning correction at `f1564a7` as its own change after PR #4 at `6621db2`. Claude’s independent review and this replay agree on the user-visible behavior. GHOST now estimates the size of a continuous thin dielectric layer from the joined surface it actually solves. How the user names its pieces can no longer inflate that count in the cases tested. This can admit a previously refused job or change the backend chosen by Automatic near a threshold. The input format and solver controls stay the same. The measured benefit is a correct decision about resources. These runs establish neither a faster field solve nor a new desktop capacity limit.

## Independent checks

I verified the Git blob IDs of the 195 files in Claude’s audit at `50b68bf` and the 528 tracked solver files in each tested source export. I read all 92 archived traces and all 78 numerical result files. For the 38 cases that completed on both revisions, all 684 paired arrays matched byte for byte. They contain 18,480 polarization/angle rows and 166,320 numeric values per revision, including the real and imaginary field, coordinates and stored residual. The largest saved residual was 3.77 × 10⁻¹⁵.

I also reran 50 fresh Linux processes using Claude’s unmodified tracer. These comprise 26 geometry and material runs, eight at the Compressed cutoff, 12 with ample or tight memory reservations, and four targeted checks of zero contrast and explicit P2. The last four intentionally repeat two configurations to check the individual memory calls and error paths. All common successful cases produced identical fields between revisions on this host. Across cases compared to Claude’s separate host, the largest field difference was 1.85 × 10⁻¹⁵ relative to the peak amplitude of the corresponding channel. The replay includes the raw values, input geometry, traces and comparison scripts.

## What changes for the user

For a 608-panel layer divided into 200 named segments, the release candidate forecast 1,616 TE and 808 TM unknowns. It actually solved 1,218 TE and 609 TM unknowns. The candidate forecast those exact physical dimensions for both polarization orders. The batch planner, Automatic desktop forecast where exercised, and instrumented solve-time checks used the correct dimensions across open, closed, reordered and disconnected inputs.

| Backend | Configured per-solve cap | Release candidate | Thin-layer correction |
|---|---:|---|---|
| Dense | 0.44 GiB | Refused | Solved |
| Dense | 0.42 GiB | Refused | Refused |
| Compressed | 0.34 GiB | Refused | Solved |
| Compressed | 0.32 GiB | Refused | Refused |

Each newly admitted solve returned the same 480 complex samples as its ample-budget reference. In the local capped Dense replay, only the recomputed residual columns differed, by at most 2.61 × 10⁻¹⁸ absolute. Every refusal occurred before an operator was built. The fresh capped processes peaked at 0.1282 GiB for Dense and 0.1457 GiB for Compressed. Claude’s corresponding raw values are 0.1485 and 0.1679 GiB. The 0.17 GiB quoted for both in Claude’s prose fits the Compressed run. The configured cap is an application admission limit and the observed peak includes the Python process.

Automatic selected Dense in the four fresh cutoff runs. In the earlier larger **planning-only** test, splitting the same 4,998-panel layer into multiple names used to flip Automatic to Compressed. The correction consistently selected Dense at the tested 24 GiB budget. An explicitly requested, unsupported P2 thin-layer basis now produces the same error from the batch planner that solve-time validation already produced. Users need make no new selection.

## Which Compressed operator is priced

These are modeled peaks for TM in the forced-Compressed public solve. TE used streamed tiles in all four cutoff runs. The right-hand side had 240 incident angles per polarization.

| Actual TM size | Release candidate, initial / inner check | Corrected initial and inner checks | Actual operator on both revisions |
|---:|---|---|---|
| 1,023 | Hierarchical at 1,027, 0.258 GiB / streamed at 1,023, 0.327 GiB | Streamed at 1,023, 0.327 GiB | Streamed |
| 1,024 | Hierarchical at 1,028, 0.256 GiB / streamed at 1,024, 0.327 GiB | Hierarchical at 1,024, 0.259 GiB | Hierarchical |

Claude is right about the inner check at exactly 1,024. My previous study’s summary missed that distinction. The earlier five-angle raw results and detailed compression notes already showed it. Claude’s new geometry and 240-angle trace independently confirm it. Whole-process peaks on this host changed from 0.2178 to 0.2177 GiB at 1,023 and from 0.2255 to 0.2259 GiB at 1,024.

## Scope and reproducibility notes

- Claude’s one-, three-, six- and shuffled five-name cases share one physical surface. The 200-name budget case uses a different 200-piece polyline. All comparisons within each fixture are valid.
- The zero-contrast case returned zero fields for every angle without building an operator. Its public forecasts were zero on both revisions. At the inner estimate the release candidate still passed 129 DOFs per polarization. The corrected path passed zero. The interpreter alone can exceed the model’s small fixed allowance in this case.
- The monostatic cases use 240 incident directions. The Dense bistatic case has three incident directions and 120 observation directions each. Claude’s separate batch-planner call still used a 240-angle monostatic configuration. The bistatic rerun verifies dimensions and fields. It does not validate a bistatic scheduler reservation. Desktop Automatic was observed only where requested and the public batch planner ran locally.
- Physical accuracy of the thin-layer approximation against a finite-thickness dielectric, native Windows peak RAM, and full-scale solves exceed this experiment’s scope. The earlier study separately covered certification, invalid layers, ordinary formulations, and the low-level standalone mesh entry point.
- Claude’s archived geometry filename was reused for several material variants. The exact magnetic and zero-contrast inputs can be regenerated from the original runner. The new material replay retains separate input files per run. When replaying Claude’s tracer, check the JSON outcome and the output arrays for each case. The command can exit successfully for a modeled refusal or an exception that was recorded in the trace.

## Evidence

- Repository `14cole/20261028_GRIM`
- Release candidate `6621db27b90f7757606312ec99b8b2727a9e8837`
- Thin correction `f1564a770151abd8fa0e98cc95700ca311443cad`
- Independent input `50b68bfbec49eeb8259927efc7686fca8a94ca04`, `audits/claude-2026-11-28/thin-layer-review/`
- Earlier study and its five-angle cutoff trace at `ecc3e1abe44cb097d752e28136c890fdd92ea827`, `audits/codex-2026-11-28/thin-layer-planning-experiment/STUDY.md` and `REPLAY.zip`
- New archived-field verification, fresh solves and reproduction commands in the adjacent `REVIEW_REPLAY.zip`

The code branch contains only the five changed backend files relative to PR #4. Integrate PR #4 into main first, then retarget the separate thin-layer change to main. This closes the code review without requiring another model handoff.

Replay archive SHA-256 is `180e2696e270839ee3444848cf6bb4291ef3db85071744b7217a9ea294cf46ac`. Its manifest covers 167 files.
