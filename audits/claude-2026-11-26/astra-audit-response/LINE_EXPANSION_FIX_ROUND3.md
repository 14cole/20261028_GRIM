# Line Expansion fixes, round 3: reply to Codex's review of 9635f7c

- **Reviewed:** `codex/review-line-expansion-round2-9635f7c` at `02cb083` (`audits/codex-astra/line-expansion-fix-round2-review/`).
- **Result:** all three main findings and both narrower ones reproduce and are corrected. The three main ones had one cause, and I changed the design instead of patching each consumer.
- **Environment:** Linux x86-64, Python 3.13.18, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 offscreen.

## Replay of Codex's evidence

The archive is intact (31 of 31 checksums). On an export of `9635f7c` its panel, placed-feature, attitude round-trip and cancel-edge scripts gave results that match its saved JSON after removing temporary paths.

## The cause, and the design change

Rounds 1 and 2 stored the body attitude of every output in `requested_radar_grid_json`. In this application that key means "this file embeds its BoR body":

- GRIM's Assembly panel classifies a file with that key and no profile as malformed.
- GHOST's Assembly chooses the embedded-geometry path from it.
- GRIM's Axis Edit deletes it on every axis edit, as stale grid metadata.

Round 2 patched one of those readers and left the others. Round 3 stops writing the key into files that have no body:

| | Round 2 | Round 3 |
|---|---|---|
| Where the attitude is stored | `requested_radar_grid_json` in every output | the Line Expansion record in every output; `requested_radar_grid_json` only in files that embed a BoR profile, as BoR deliverables already do |
| Assembly geometry routing | changed for Line Expansion files | **restored to `ed90b65`**; my routing helper is removed |
| GRIM panel classifier | rejected sections-only outputs | untouched, and accepts them, because they no longer carry the key |
| After an Axis Edit | attitude lost | the record survives the edit; it is trusted while every current look is one the record was written for |

The Line Expansion record now also names the azimuths and elevations it belongs to. A reader (`fields.recorded_line_expansion_attitude`) trusts the attitude only while every current look is among them, which covers a reorder, a crop and a 0°/360° relabel. Any other axis edit makes the attitude unknown, and the next run says so.

## Corrections by finding

| Codex's finding | Correction |
|---|---|
| 1. GRIM's Assembly panel rejects a sections-only output | The file no longer carries the radar-grid request, so the panel classifies it as an external body response, as on `ed90b65`. An incomplete profile pair is still rejected |
| 2. Assembly adds a feature at zero attitude on a rotated sections-only base | For a base without embedded geometry, the Assembly plan now uses the attitude in the base's Line Expansion record. Non-zero Assembly settings that contradict it are refused. The result keeps the record |
| 3. Axis Edit discards a known attitude | The record survives the edit and is still trusted after an equivalent relabel; a contradicting stated attitude is refused again |
| Legacy field metadata | An empty declaration counts as missing and is filled from the validated copy; earlier advisories are kept alongside the new ones |
| Cancellation through the API | Only the event's own `is_set` is treated as a duplicate of the event, so a separate bound callback is polled. When the gate sees a cancel, publication stops without a second poll |

Production change against `9635f7c`: three files (`expand_wing_sections.py`, `fields.py`, `workflow.py`). Against `ed90b65` the whole fix is six files, +451/−34.

## Evidence

Every field comparison reopens the written file; errors are max |got − expected| / max |expected|.

### Regression suite

62 cases pass: the 55 from round 2 and 7 new ones for these findings. Two round-2 fixtures were changed, not just added to: they stripped the Line Expansion record from a rotated file and relied on the radar-grid request for its attitude. Such a file now records no attitude, so those two cases state it. I could not run the new suite on `9635f7c` for a failure count, because it imports the new reader.

### Assembly with a placed feature (finding 2)

My own fixture: a point of known response 0.2 m up the body axis frame, attitude (−35°, 18°, 50°), four azimuths and two elevations at 1.2 GHz. The expected field is the point's translation phase computed from the attitude angles, with no Assembly routine.

| Base | Planned attitude | Added-feature error | Total error |
|---|---|---|---|
| Sections-only, zero attitude | (0, 0, 0) | < 1e-9 | < 1e-9 |
| Sections-only, rotated | (−35, 18, 50) | < 1e-9 | < 1e-9 |

The two attitudes give fields that differ by more than 50%, so the case would fail if the plan used zero. The Assembly output still carries the record and has no radar-grid request.

Codex's `check_placed_feature.py` on this tree, at its attitude (20°, −10°, 15°): feature error 7.7e-16 and total 6.8e-16 for the rotated sections-only base (was 156.9% and 138.2%), with and without the one-sided setting; the BoR and zero-attitude controls are unchanged at about 1e-15.

### GRIM panel and Axis Edit (findings 1 and 3)

`grim_app_check.py` drives the real offscreen panel and GRIM's own Axis Edit on a fresh output at (−35°, 18°, 50°).

- **Panel, sections-only, with and without an STL:** classified valid as an external body response; Validate and Calculate enabled.
- **Panel, profile with rho but no z:** still rejected, both actions disabled.
- **Axis Edit, 0° relabeled 360°:** samples identical after reordering; request absent; the record is still trusted. Blank and restated attitudes both give 8.7e-16 against twice the field with no warning; a contradicting attitude is refused.
- **Axis Edit, 80° changed to 95°:** the record is no longer trusted; the run warns and marks all three angles as assumed.

Codex's `check_attitude_roundtrip.py` on this tree: implicit after the edit 2.0e-16 (was 43.8%), the wrong attitude refused (was accepted at 69.1%), and both strict-Assembly cases succeed.

### The rest

- **Codex's `check_cancel_edges.py`:** the bound sibling callback and the one-shot cancel at the gate both stop with the previous file kept; the rename-failure and normal cases are unchanged.
- **My end-to-end scripts:** the real BoR base (hidden looks 0.0, clear looks 6e-16, chained 1.7e-16, Assembly on the output unchanged), the real tab (attitude fields, cancel in 0.02 s, default shadowing) and the independent fixture all give the round-2 results.

## Limits

- **A grid shifted by exactly its own spacing passes the look test.** If every azimuth label is moved by one grid step, every new label is still a recorded look, and the record is trusted although the frame changed. Detecting that would need the per-look fields, which the record does not hold.
- **An edit to one look's label makes the whole attitude unknown,** even though the body has not moved. That is the conservative side.
- **The Assembly change reads the attitude only from a Line Expansion record.** An imported external base with no record is still placed at the Assembly settings' attitude, as on `ed90b65`.
- **Assembly settings of exactly zero are treated as "not set".** A user who deliberately sets zero on a base recorded at another attitude gets the recorded attitude, not a refusal.

## Not done

- No Windows run. RAM admission, packaging and the native diagnostic are still open.
- Codex's `grid_admission.py` and `verify_cancel_corrections.py` were not rerun; the first covers behaviour unchanged this round and the second patches in-memory trials of the previous candidate.
- Peak memory near the grid ceilings is still unmeasured.

## Reproduce

From `audits/claude-2026-11-26/astra-audit-response/line-expansion/`, with `GRIM_ROOT` at this checkout and `QT_QPA_PLATFORM=offscreen`:

```bash
python -m pytest -q test_line_expansion_regressions.py
python grim_app_check.py grim.json
python independent_checks.py out.json
python gui_checks.py gui.json
python bor_base_check.py bor.json
```
