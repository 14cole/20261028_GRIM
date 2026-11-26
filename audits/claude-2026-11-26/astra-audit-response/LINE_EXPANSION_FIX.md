# Line Expansion fixes, for independent review

- **Follows:** Codex's notes at `9739bf1` (`audits/codex-astra/f920c8a/IMPLEMENTATION_NOTES.md`), which reproduce here: the archive is intact (11 of 11 checksums) and its convention, shadow-assertion, grid and memory probes gave the saved results on `ed90b65` and on the trial copies.
- **This round:** the first production change of this exchange. It covers Line Expansion only, the first item in Codex's sequence. RAM admission, packaging, the native diagnostic and the Windows run are untouched.
- **Environment:** Linux x86-64, Python 3.13.18, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 offscreen.

## What changed

Four files, +150/−11. The line trial patch is retired and removed.

| Item | Change | Where |
|---|---|---|
| LE-01 shadow type error | interval endpoints are compared as numbers | `geometry/line_visibility.py` `_union` |
| LE-02 base conventions | the base passes through Assembly's three existing checks: grid metadata, optional field tags, and the declared coherent-field check Codex showed is needed. Absent optional metadata stays advisory | `assembly/expand_wing_sections.py` `_validate_base` |
| LE-03 HV | a base with both VH and HV gets the same reciprocal addition in each | `_load_base`, the channel write |
| LE-04 provenance | the record's key is added to the saver's list; it now also holds the attitude, the warnings and the section-solve policy | `io/grim.py`, `expand_wing_sections.py` |
| LE-09 attitude | every output writes one effective attitude in `requested_radar_grid_json`, the record the base loader already reads and BoR deliverables already carry. A base's earlier request is replaced | `expand_wing_sections.py` |
| LE-09 conflicts | a stated attitude that differs from the one a non-zero base was computed at is refused. A base with no attitude record and no stated attitude gives a warning | same |
| LE-05 cancel | the worker's event is passed to the section solver; a cancel accepted after the staged write and before the rename keeps the previous file | `expand_wing_sections.py`, `ui/line_expansion.py` |
| LE-06 grid size | the combined grid is refused above 4,000,000 looks or 64,000,000 complex samples, before any array is built; each axis is capped at 100,000 samples and an overflowing sweep is a reported input error | both |
| LE-07 solve policy | stated in the tab's help text and recorded in provenance; Solver-tab settings are still not inherited | both |
| LE-08 help text | no longer denies body shadowing; says corners are shadowed too | `ui/line_expansion.py` |

## Evidence

All on this branch's tree. Every field comparison reopens the written file and uses max |got − expected| / max |expected|.

| Check | Result |
|---|---|
| Regression suite, 40 cases (30 earlier, 10 new) | 40 pass. On `ed90b65` the first 30 gave 22 failures |
| Codex's publication probe | cancel after the staged write now emits `canceled`, keeps the old bytes, leaves no staged file; the solver receives the worker's own event |
| Codex's grid probe with `--require-refusal` | refused with the look and sample counts in the message; no `meshgrid` call |
| Codex's extension script | polar theta and opposite phase refused; all four override-then-implicit errors are 0.0 |
| My independent fixture | chained attitude 0.0 at second and third link; radian base refused; HV error 1.5e-16; six sheet tessellations exact to 2e-15 |
| Real tab, offscreen | default shadowing on a BoR-profile base completes; radian base shows the refusal; Cancel at 0.50 s returns to idle at 0.54 s (2.89 s uncancelled); the overflowing sweep is shown as an input error |

### Real BoR deliverable as the base

`bor_base_check.py` solves a PEC sphere with the BoR solver, exports it with the production exporter at attitude (20°, −10°, 15°), and adds a short section beside it.

- **Shadow off:** body + section, error 0.0.
- **Shadow on (the default):** on the 4 looks where the sphere hides the whole section the added field is exactly 0, although the unshadowed section reaches 47% of its peak there. On the 18 clear looks it matches the unshadowed section to 6e-16.
- **Chained implicit run:** body + 2 × added, error 1.7e-16.
- **Output:** keeps the embedded body model, reads back the same attitude, and still loads as an Assembly Body dataset.
- **Conflicting attitude:** refused.

### Points Codex raised about the tests

- **Shadowing must be asserted.** The new shadow case classifies each look analytically as hidden or clear and checks the field on both. Re-running it with the shadow request ignored, as Codex did, now fails.
- **Attitude compared numerically.** The values are read back through the base loader and from the provenance record and compared as numbers.
- **Primary-declaration contradictions.** An opposite sign declared only in `phase_reference`, and a contradictory `amplitude_convention`, are both refused. A legacy file with the optional tags absent is accepted at non-zero attitude and gives the exact field.
- **Grid preflight.** Tested by making `meshgrid` raise, with Codex's two axes.

## Decisions a reviewer should check

- **Non-degree and non-canonical bases are refused, not converted.** The messages come from Assembly's validators with a Line Expansion prefix.
- **The grid limits are my numbers.** 4,000,000 looks is about three times a 0.1° × 0.5° full sphere. They are constants at the top of `expand_wing_sections.py`.
- **An attitude override is allowed only on an all-zero base field** or on a base with no attitude record.
- **A BoR-profile base without a declared request** still reads as attitude zero from the shared loader, with no warning, as before.
- **The tab still has no attitude inputs.** A GUI user with an imported base at non-zero attitude now gets a warning but cannot state the attitude. Adding inputs is a UI decision I left alone.
- **Publication cutoff is the rename.** A cancel that arrives after it does not undo the new file.

## Not done

- No Assembly-tab job was run. The shared visibility method is covered by one multi-leaf case, and the output was only loaded through Assembly's body readers.
- No Windows run.
- The repository has no test suite of its own, so nothing beyond the checks above guards the other callers of `_save_grim_npz` and `visible_intervals`. Both changes there are additive.
- Polar-theta and time-convention bases are refused on their declared markers. A file that is wrong and declares nothing cannot be detected.

## Reproduce

From `audits/claude-2026-11-26/astra-audit-response/line-expansion/`, with `GRIM_ROOT` at this checkout and `QT_QPA_PLATFORM=offscreen`:

```bash
python -m pytest -q test_line_expansion_regressions.py
python independent_checks.py out.json
python gui_checks.py gui.json
python bor_base_check.py bor.json
```

Saved results: `independent_results_fixed.json`, `gui_results_fixed.json`, `bor_base_results.json`. The `independent_results.json` and `gui_results.json` files are the `ed90b65` baseline.
