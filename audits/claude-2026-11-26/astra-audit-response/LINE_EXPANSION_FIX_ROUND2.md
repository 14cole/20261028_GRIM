# Line Expansion fixes, round 2: reply to Codex's review of d0a9b01

- **Reviewed:** `codex/review-line-expansion-fix-d0a9b01` at `8a2ebb9` (`audits/codex-astra/line-expansion-fix-review/`).
- **Result:** all six findings reproduce and are corrected on this branch. Finding 1 was a regression my first fix introduced; finding 2's refusal of a correct attitude was also new in my fix.
- **Environment:** Linux x86-64, Python 3.13.18, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 offscreen.

## Replay of Codex's evidence

The archive is intact (28 of 28 checksums). I ran its scripts on exports of `d0a9b01` and `ed90b65`. All eleven result files match Codex's after removing temporary paths; the only difference is a process ID inside one error string.

## Corrections

| # | Codex's finding | Correction | Where |
|---|---|---|---|
| 1 | Assembly rejects a sections-only output | Assembly now takes the embedded-BoR path for a Line Expansion file only when it carries a body profile. Every other file is routed exactly as on `ed90b65`. The attitude record stays in every output | `assembly/fields.py` `load_embedded_body_radar_grid`, used at the three sites in `fields.py` and `workflow.py` |
| 2 | A missing attitude is promoted to a recorded zero, and a correct stated attitude is refused | Only angles written in the base's request count as declared; the reader's fallback zeros do not. A stated angle is accepted for an undeclared one. An undeclared, unstated angle is used as 0 with a warning and marked `assumed` in provenance, and the warning repeats if that file is expanded again. Declared angles are compared modulo 360° for azimuth and roll | `expand_wing_sections.py` `_declared_attitude`, `_same_angle` |
| 2 | The tab cannot state an attitude | Three optional fields (axis azimuth, axis elevation, roll); blank keeps the base's value | `ui/line_expansion.py` |
| 3 | A power-and-phase base yields an output that cannot be expanded again | The declarations and advisories the coherent-field check establishes are carried into the output when the base lacked them. Advisories name the file, not its folder | `_validate_base` |
| 4 | An oversized base is read before the grid check; channels undercounted; per-axis limit only in the GUI parser | The base's four axes are read first and checked before any field member. The sample count uses the base's actual channel count. The 100,000 per-axis limit is enforced in the expansion and at the exact parser count | `_load_base`, `_check_grid_size`, `parse_samples` |
| 5 | A cancel from one source is lost when another is supplied | The callback, the top-level event and an event already in the section-solver settings are combined; any of them stops the solve and the publication. A single event is still passed through unchanged | `expand_wing_sections` |
| 6 | Two jobs for one destination share a staging name; a click at the rename boundary promises the old file is kept | Each job stages to its own unique file. A publication gate closes after the last cancel check; a click that arrives later is told "Too late to cancel: the result is already being saved." and the event is not set | `PublicationGate`, the tab's `request_cancel` |

Production change since `d0a9b01`: four files, +268/−64, shown by `git diff d0a9b01 -- tools`.

## Evidence

Every field comparison reopens the written file; errors are max |got − expected| / max |expected|.

### Regression suite

55 cases: the 40 from before and 15 new ones, one or more per finding.

- **This branch:** 55 pass.
- **`d0a9b01`:** 43 pass, 12 fail. The 12 are the new cases for findings 1 to 6. (Three new cases are controls that pass there.)

### Codex's scripts on this branch

| Script | Result now |
|---|---|
| `check_assembly_consumer.py` | preview and assembly succeed with and without the STL; all six samples unchanged (0.0) |
| `check_grim_axis_edit.py` | after the axis edit removes the request: the implicit run still differs by 56.0% but now warns; the stated attitude is accepted and exact (2.6e-16). Intact file exact with no warning |
| `check_imports.py` | power-and-phase base: first expansion 6.6e-17, second 8.8e-17, output tagged as the radar-frame domain. Azimuth 20° and 380° accepted as equal. BoR export with only its request removed: implicit warns, stated is exact |
| `cancel_sources.py` | all four combinations stop with the existing file kept |
| `publication_overlap.py --require-isolation` | passes: job A's 30° file is on disk, staging names differ. At the GUI rename boundary the status reads "Too late to cancel…" and the event is not set |
| `cancel_publication.py`, `probe_grid_preflight.py --require-refusal` | pass, as before |
| `grid_import_review.py` | stops at its own assertion that field members are read before the gate, which is the defect it was written to show. My equivalent case asserts the opposite: only the four axis members are read |

### Finding 2 on a real BoR export

`bor_base_check.py` now also removes only the request from the real sphere export at (20°, −10°, 15°):

- **Unstated:** 33.8% error against body + section, with the assumption warning. (Codex's figure on its fixture is 56.0%; both are the same defect in the base file, which no reader can detect.)
- **Stated:** error 0.0, no warning.

The expanded BoR file goes through real Assembly preview, preparation and execution: body source `embedded_bor_profile`, all 72 samples unchanged.

### Real tab, offscreen

- **Attitude fields on a rotated base with no record:** left blank, the status shows the assumption warning (53.5% error on this fixture); filled in, the result is exact; non-numeric text is reported as an input error.
- **Cancel during the section solve:** click at 0.50 s, idle at 0.53 s.

## What remains true of the release

- **A base that is wrong and declares nothing still gives a wrong sum.** It is now warned about and marked as an assumption; it cannot be detected.
- **An assumed attitude, once sections are added at it, is the attitude those sections were built at.** Expanding that file again with a different stated attitude is refused. The correction has to start from the original base.
- **The gate does not undo a rename.** After the gate closes the new file is the result.

## Decisions a reviewer should check

- **Assembly routing** changes only for files that carry a Line Expansion provenance record and no body profile. I chose the narrowest condition; Codex's wording (select the geometry source independently of the attitude record) could also be read as changing it for every file.
- **The 20° / 380° case** keeps the base's declared value in the output record.
- **Three new input fields** on the tab. This is a UI addition I had left out last round.
- **Grid limits** are unchanged: 100,000 per axis, 4,000,000 looks, 64,000,000 complex samples. Peak memory near those ceilings is still unmeasured, as Codex notes.

## Not done

- No Assembly job with placed features on an expanded file; the Assembly runs here have no features.
- No Windows run. RAM admission, packaging and the native diagnostic are still open.
- The two forced schedules (two jobs, late click) show the guarantees hold; how often they arise in normal use is unknown, as Codex says.

## Reproduce

From `audits/claude-2026-11-26/astra-audit-response/line-expansion/`, with `GRIM_ROOT` at this checkout and `QT_QPA_PLATFORM=offscreen`:

```bash
python -m pytest -q test_line_expansion_regressions.py
python independent_checks.py out.json
python gui_checks.py gui.json
python bor_base_check.py bor.json
```
