# Audit of Codex's Line Expansion audit

- **Codex audit:** `codex/line-expansion-audit-2026-11-10` at `b7dd6c7` (`audits/codex-2026-11-10/line-expansion/`).
- **Code it audited:** `distribution/grim-ux-2026-11-10` at `7216291`.
- **My environment:** Linux x86-64, Python 3.13, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 offscreen, using the Linux libraries shipped on that branch.
- **What I did:** ran Codex's three scripts unmodified, read the code behind each finding, and added two checks of my own (scripts beside this file). No production file was changed.

## Verdict

Codex's audit is accurate. All eight findings reproduce, its severities are reasonable, and its "do not sign off" conclusion is right for workflows that use body shadowing or an imported base. I disagree with nothing of substance; I narrow two findings, and I add one defect it did not report.

Codex is also right about my earlier review: my "no blocking defect" verdict on the distribution branches covered the solver tab, the Geometry tab and the packaging. I did not exercise the Line Expansion tab, and that verdict should not be read as covering it.

None of this code was touched by the solver fixes or the UI simplification. `geometry/line_visibility.py`, everything under `assembly/`, `ui/line_expansion.py` and `io/grim.py` are byte-identical to `f207c61`, so these defects are present on main today.

## Findings, re-run

| ID | Codex's claim | My result | Agree? |
|---|---|---|---|
| LE-01 | Body shadowing crashes with `TypeError` on ordinary crossing lines | Reproduced with the minimal script and through the expansion path | Yes; see scope note below |
| LE-02 | Base in radians, polar theta or exp(-jwt) is accepted and combined | Reproduced: all three accepted, no warning | Yes |
| LE-03 | Base with VH and HV gets only VH updated | Reproduced: max \|VH\| 0.0544, max \|HV\| 0 | Yes |
| LE-04 | Saved file drops line-expansion provenance and warnings | Reproduced: key created at `expand_wing_sections.py:814`, absent after reopening | Yes |
| LE-05 | Cancel does not reach the section solve; publication race after the last cancel check | Reproduced: cancel at 0.03 s, idle at 1.0 s; destination replaced when cancel arrives during save | Yes; the race is narrow |
| LE-06 | Sweep parser unbounded; overflow escapes the GUI handler | Reproduced: `OverflowError` for `0:1e308:1e-308`; 100,001 samples built on the GUI thread | Yes; I would rank the overflow P3 |
| LE-07 | Tab always runs the certified section solve and ignores Solver-tab settings | Confirmed at `assembly/line_expansion.py:163-172` | Yes |
| LE-08 | Help text contradicts the shadow and corner options | Reproduced | Yes |

Codex's passing checks also ran clean here (45 passes, 11 deficiency observations, 1 resource observation). The real GUI solve against the PEC-cylinder series gave the same errors Codex reports: 0.0245% (VV) and 0.0299% (HH).

## Where I narrow or extend Codex's findings

### LE-01: when it crashes, and what is left once it does not

The cause is exactly as Codex describes: `_union` returns lists, the next leaf appends tuples, and `sorted` cannot compare the two. Two things Codex did not state:

- **It needs an occluder of more than 256 triangles.** `Occluder._LEAF_TRIANGLES` is 256, so a smaller mesh has one leaf and can never mix the two types. That is probably why this survived: small test bodies pass.
- **On a realistic body it is common, not rare.** On Codex's 720-triangle cylinder, 1,168 of 4,800 random line-and-look queries near the body crashed (24%); 1,129 of 4,800 on a second tessellation.

I also checked what Codex could not, because every multi-leaf query crashes: whether the answer is right once the type error is bypassed. With the interval items normalised to lists in a test-only wrapper (production untouched), the visible fraction of 100 lines per look, over 12 looks, matched 2,000-point sampling through the occluder's own point test to 0.0004, across 271 partially shadowed and 63 fully shadowed cases. So the defect is the crash alone; the clipping geometry behind it is correct. A one-line normalisation is a sufficient fix, and Codex's requested multi-leaf tests are the right regression.

Assembly line features call the same function (`assembly/fields.py:3366`), so they are exposed in the same way. I confirmed that by reading, not by running an Assembly job.

Script: `shadow_frequency_and_oracle.py`.

### LE-03: the fix is simpler than the finding suggests

The radar-frame matrix the code adds is symmetric to rounding (|S₀₁ − S₁₀| / max|S| = 1e-16 on a tilted, twisted, anisotropic section with 23% cross-polarisation). So writing the same value to both VH and HV is correct; no separate HV calculation is needed. I also checked two layouts Codex asked about: a base labelled HV only, and a reordered `[HH, VV, VH]` base. Both receive the right values in the right channels.

Script: `cross_pol_and_attitude.py`.

### LE-05: severity of the publication race

The race exists, but the window is only the time to serialise one file after the last cancel check. I would call it P3 on its own. The part that matters to a user is the other half of LE-05: cancel is not passed into the section solve, so a large section runs to completion first.

## A defect Codex did not report

### LE-09 (P1 for chained use): the body attitude is not saved, and a base without it is silently treated as zero attitude

- **Where:** `assembly/expand_wing_sections.py:598-601` (`stored = {}` when the base has no readable radar-grid record, including when reading it raises) and `:620-628` (attitude values default to 0.0 from that empty record). The output written at `:806-822` contains no attitude at all.
- **What happens:** a sections-only run made with a non-zero `axis_az_deg`, `axis_el_deg` or `roll_deg` writes a file with no record of them. Using that file as the base of a second run places the new sections at zero attitude unless the user re-enters the same values. No warning is given in either run.
- **Evidence:** sections-only run at axis azimuth 30°, elevation 10°. Reloading its radar-grid record returns `None`; the file has no attitude key. Adding the same section again on top of it should exactly double the field:

  | Second run | \|output\| / \|base\| at the two looks | Warnings |
  |---|---|---|
  | attitude not restated | 2.058, 1.830 | none |
  | attitude restated (30°, 10°) | 2.000, 2.000 | none |

- **Why it matters:** this is the tab's own output used as its own input, the most natural way to build a job in stages, and the result is wrong by several percent with no indication. It also applies to any imported base whose radar-grid record is missing or unreadable, because the read error is swallowed.
- **Relation to Codex's findings:** it sits between LE-02 (base conventions not validated) and LE-04 (provenance not saved), but neither covers it. Saving the attitude in the output, and refusing or warning when a base has none and the user supplied none, would close it.

Script: `cross_pol_and_attitude.py`.

## Notes on Codex's method

- The LE-02, LE-03 and LE-04 reproductions replace the section solver with synthetic coefficients. Codex says so, and it is the right way to isolate import and export; the real-solver runs cover the rest.
- Its main script exits 0 while recording deficiencies. Anyone automating it must read the statuses, as its report says.
- I did not verify the source manifest's 218 file hashes; I checked instead that the audited modules are identical to `f207c61`.

## What I did not do

- No fixes. Codex's report asks for them; this pass was the audit you asked for.
- No Assembly-tab run, no Windows run, and no comparison of the line model with a full 3D solver. Like Codex's, this audit checks the code against its stated model, not the model against reality.
