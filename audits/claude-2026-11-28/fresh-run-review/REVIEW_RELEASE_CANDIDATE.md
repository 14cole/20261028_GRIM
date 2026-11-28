# Review of Codex's display and sheet-planning release candidate

- **Reviewed:** `3eab4bb` (sheet planning) and `6621db2` (display and partial recovery) against `main` at `95f8719`; handoff at `codex/ghost-display-sheet-handoff-2026-11-28`, `4115cca`. The evidence archive matches its stated SHA-256.
- **I did not merge the handoff branch into mine,** because it carries production changes that are not on `main`. I tested exports of each commit.
- **Decision:** merge `3eab4bb`. Merge `6621db2` for user testing, with the limits below. I could not confirm or refute the thin-layer finding.

## Sheet planning (`3eab4bb`) — merge

New fixture of mine (`sheet_rc.py`): an impedance sheet bent 70° in the middle, split into 11 named pieces, every second piece reversed, two alternating impedances; and a coated PEC cylinder as the ordinary-material control. 4 GHz, 72 angles, Automatic backend, P1 to P3. I recorded the desktop forecast, the HPC forecast (TE then TM, TM then TE, each alone), the sizes of the matrices actually factorized, and the full fields.

| Bent sheet | Desktop and HPC forecast on `main`, TE / TM | Forecast on `3eab4bb` and `6621db2` | Factorized |
|---|---|---|---|
| P1 | 94 / 94 | 84 / 94 | 84 / 94 |
| P2 | 177 / 177 | 167 / 177 | 167 / 177 |
| P3 | 260 / 260 | 250 / 260 | 250 / 260 |

- **All four HPC orderings give the same corrected counts.**
- **The coated-cylinder control is unchanged:** 544, 1,088 and 1,632 in every column on every tree.
- **Fields are bit-identical** to `main` on both commits, for both fixtures and all three orders. These were executed solves, not planning only.
- **My seven earlier fixtures** (`sheet_unknowns.py`) show no remaining mismatch on either commit.
- The fix itself is one argument in `selection.py` and a shared helper in `hpc/scheduler.py`. Not tested: a cluster submission, the three-way branch rejection.

## Display (`6621db2`) — merge for user testing

I did not build an independent GUI harness. I ran Codex's `verify_display.py` on exports of both trees, with the large dataset changed to one of mine: 53 frequencies in shuffled order from 3 to 14.7 GHz, 541 angles, both polarizations, 57,346 rows. The small special-case fixtures are Codex's unchanged. The copy I ran is `display/verify_display_variant.py`.

| Case | Record loads on `main` | On `6621db2` |
|---|---|---|
| My 53-frequency dataset, initial presentation | 1,484 (28 per frequency) | 53 |
| 7 frequencies, completion | 196 | 7 |
| 4 of 7 recovered | 48 | 4 |
| Body of revolution, either ordering | 84 | 3 |
| Bistatic | 96 | 3 |
| Extension record with a missing field | 96 | 97 |
| Any small case with the 1-byte budget (fallback) | — | same as `main` |

- **Initial presentation of my dataset took 6.75 s on `main` and 0.50 s on the candidate,** one run each, offscreen Qt on Linux. Sampled extra memory was 7.5 against 7.8 MiB.
- **Every formatted cell (286,730), every curve, the status text and the export history matched** between trees on my dataset; Codex's comparison script asserts this.
- **Damaged record:** the candidate rejects it, keeps the previous view, and exports after the file is restored without reopening. `main` needs the result reopened. That is a fix, not only a speedup.
- **Reading the diff,** I found no defect. Two behaviours to know about: results above 524,288 rows silently use the old slow path, and a completed solve whose records fail verification at display now reports an error and keeps the previous result on screen.
- **Not covered:** native Windows, a real screen, interactive responsiveness, and any dataset above the 16 MiB budget at realistic size.

## Thin dielectric layer forecast — not confirmed

`thin_layer.py` splits a thin layer into three or four named sections (straight, two reversed, gently bent). On both `main` and the candidate the forecast and the executing estimate agree (48 / 24 for four sections), and fields are identical between trees. My probe could not isolate the size of the system the thin-layer solver actually assembles on its joined midsurface: it sees both 24 / 48 and a 21 / 42 that also appears for an unsplit layer and is probably a qualification solve. So I have neither reproduced Codex's 24 / 12 against 20 / 10 nor contradicted it. This needs instrumentation inside the thin-layer solver, which I have not written.

## Not done from the handoff's list

- Region-membership sharing, with stage and whole-process peaks: not started.
- Native Windows checks: no Windows machine.
- A clean-desktop walk-through by hand: not possible here; the GUI was driven offscreen.

## Reproduce

```sh
export GRIM_ROOT=/path/to/export          # git archive <commit> tools GRIM_Backend airfoil.geo, for 95f8719, 3eab4bb, 6621db2
OPENBLAS_NUM_THREADS=1 python sheet_rc.py <label> results/rc
OPENBLAS_NUM_THREADS=1 python thin_layer.py <label> results/rc
cd display && QT_QPA_PLATFORM=offscreen python verify_display_variant.py /path/to/export large ../results/display/<name>.json
python compare.py main-large.json candidate-large.json --one-pass      # run inside results/display
```
