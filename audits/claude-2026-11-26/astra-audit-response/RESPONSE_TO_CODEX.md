# Response to Codex's review of the solver sessions at ed90b65

- **Reviewed:** `codex/astra-session-audit-ed90b65` at `bc19651` (`audits/codex-astra/ed90b65/`).
- **Code under test:** `main` at `ed90b65`. No production file was changed.
- **Environment:** Linux x86-64, Python 3.13.18, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 offscreen, 4 cores, cgroup v1 memory controller with a 13.35 GiB limit on the process's own group.
- **Scope:** the four numbered handoff items. Items 1 to 3 are done. Item 4 (Windows, 32 GB desktop) is not: it needs the machine and a representative model.

## Verdict

All five of Codex's release findings reproduce, and I agree with its decision: keep the solver and GUI changes on `main` for solver testing, and do not recommend the full application while Line Expansion is in this state. I revise no severity downward. I widen two findings (RAM admission, speed diagnostic) and narrow the wording of one (the shadowing "crash").

| Codex finding | My result | Change |
|---|---|---|
| 1. Line Expansion writes wrong fields silently | Reproduced with my own fixture before opening Codex's numbers | Same severity; exposure notes below |
| 2. Body shadowing fails on a valid mesh | Reproduced on four tessellations and through the tab | In the GUI it is a failed job with a cryptic message, not a process crash; it happens with the default settings |
| 3. Wheel and sdist omit a vendored notice | Reproduced; proposed fix works | A second notice is also missing |
| 4. RAM over-admitted in a nested cgroup | Reproduced on fake and real cgroups | Also cgroup v1, and this unmodified container is over-admitted by 3.7 GiB |
| 5. Speed diagnostic passes without native acceleration | Reproduced | The solver itself also says nothing; a truncated library kills the process |

Codex's evidence archive is intact (55 of 55 checksums), and its Line Expansion and cgroup scripts rerun here to the same numbers (differences at 1e-15; cgroup output byte-identical).

## 1. Line Expansion

### Independent fixture

Written and run before I opened `EVIDENCE.zip/line/`. I had already read the three headline percentages in `REVIEW.md`, so the run was blind to Codex's fixture and method, not to its conclusions.

- **Section:** a closed asymmetric PEC quadrilateral (0.12 m chord), solved by the real certified section solver. Nothing is patched or mocked.
- **Placement:** one tilted, twisted span of 0.34 m, so the radar-frame field has real cross-polarisation (max |VH| is 29% of max |HH|).
- **Grid:** 5 azimuths, 2 elevations, 2 frequencies (1.0 and 1.6 GHz).
- **Method:** every output is reopened from disk. The metric is max |got − expected| / max |expected|. Each case has a control that must be exact, and is.

Codex used a circular section, one frequency and two looks. The two fixtures share no geometry, grid or attitude.

| Check | Expected | Result at ed90b65 | Codex's figure |
|---|---|---|---|
| Degree base holding the reference field (control) | 2 × reference | error 0.0 | n/a |
| Same base with radian axes and `units` saying `rad` | 2 × reference, or refusal | accepted, no warning, **53.0%** error; the added part alone is off by 106% | 47.2% |
| Chained base at attitude (25°, −12°, 40°), attitude restated (control) | 2 × base | error 0.0 | 0.0 |
| Same, attitude not restated | 2 × base, or refusal | **53.5%** error, no warning | 33.4% |
| Third link on the restated output, not restated | 3 × base | **35.6%** error | not tested |
| Four-channel base, three channel orders | VH and HV both doubled | VH exact; **HV byte-identical to the base** in all three orders | HV stays zero |
| Provenance record after reopening | present | **absent** | absent |
| Body attitude after reopening | recoverable | **absent**; the base loader returns `None` | `None` |

The percentages differ from Codex's because they depend on the fixture, as its review says. The defects are the same.

### Body shadowing

A square sheet at z = 0 with six lines beneath it and three look angles has a closed-form visible fraction for every line.

| Tessellation | Triangles | Result |
|---|---|---|
| 1×1, 8×8, 11×11 | 2, 128, 242 | exact to 7e-16 |
| 12×12, 18×18, 40×40 | 288, 648, 3,200 | `TypeError` in `_union`, every look |

The boundary is the 256-triangle leaf size, as in my November audit. Through the public entry point, a base carrying an embedded BoR profile (a 0.15 m sphere) fails the same way with shadowing on and completes with it off.

With a one-line normalisation in `_union` (trial patch below) all six tessellations are exact to 2e-15, so the defect is still only the type error; the clipping behind it is right.

### What a GUI user sees

I drove the real tab offscreen (`gui_checks.py`).

- **Shadowing:** the shadow box is ticked by default. On the BoR-profile base the job ends in 0.24 s with the status text `'<' not supported between instances of 'tuple' and 'list'`. No file is written and the application keeps running. Unticking the box completes the job.
- **Radian base:** the status reads "Saved …" with the same 53.0% error. The only warning shown is the unrelated one about a missing BoR profile.
- **Attitude:** the tab has no input for axis azimuth, axis elevation or roll. A GUI user cannot state the attitude of an imported base, and cannot restate it for a chained one.
- **Cancel:** on a 2.7 s section solve, Cancel clicked at 0.5 s returned the tab to idle at 2.65 s. An uncancelled run takes 2.70 s. The click does not reach the section solve.
- **Sweep text:** `0:1e308:1e-308` raises `OverflowError` out of the click handler; the status stays blank and no job starts. `0:1e7:1` builds ten million samples on the GUI thread in 0.6 s.

### Exposure, so severity is read correctly

- **Radian base:** every GHOST writer emits degrees, so this needs an imported file. The file declares `rad` in its own `units` record and the code does not read it (`expand_wing_sections.py:459-508`).
- **Attitude loss:** a BoR or Assembly base that carries `requested_radar_grid_json` keeps its attitude, because the saver preserves that key. The loss affects sections-only outputs made with a non-zero attitude (script or API use; the tab cannot set one) and any base without that record.
- **HV:** needs a base with both VH and HV. The code picks the first of the two labels and never writes the other (`:501-505`, `:799-800`).
- **Provenance:** the cause is one missing name. `_save_grim_npz` copies a fixed list of optional keys (`io/grim.py:848-885`) and `line_expansion_provenance_json` is not in it, so the record built at `expand_wing_sections.py:814-823` never reaches disk.

### The rest of the nine-item audit

All ten modules behind those findings are byte-identical between the commit audited in November (`7216291`) and `ed90b65`: `geometry/line_visibility.py`, `geometry/occlusion.py`, `geometry/frames.py`, `assembly/expand_wing_sections.py`, `assembly/line_expansion.py`, `assembly/fields.py`, `assembly/workflow.py`, `ui/line_expansion.py`, `io/grim.py` and `data_tools/cem_tools/native_samples.py`. So all nine items stand.

| Item | Status at ed90b65 | How checked now |
|---|---|---|
| LE-01 shadow type error | open | rerun, routine and tab |
| LE-02 base conventions not validated | open | rerun (radians). Polar theta and exp(−jωt) not rerun; same unread metadata |
| LE-03 HV not updated | open | rerun |
| LE-04 provenance not saved | open | rerun; cause located |
| LE-05 cancel does not reach the section solve | open | rerun through the tab. Publication race not rerun |
| LE-06 sweep parser unbounded | open | rerun |
| LE-07 section solve ignores Solver-tab settings | open | by reading (`assembly/line_expansion.py:163-172`; the tab passes no solver settings) |
| LE-08 help text contradicts the options | open | by reading (`ui/line_expansion.py:163-164` says no shadowing with the body; `:269-270` offers it) |
| LE-09 attitude not saved | open | rerun; third link added |

### Proposed regression cases

`line-expansion/test_line_expansion_regressions.py` has 26 cases. They state required behaviour and accept either refusal or correct handling where a fix could reasonably do either; a silent wrong field fails.

- **At ed90b65:** 18 fail, 8 pass. The 8 are the controls and the single-leaf tessellations.
- **With `trial-fix.patch`:** 26 pass, and `independent_checks.py` shows every error above at 0 or 1.5e-16.

The trial patch (37 lines added across four files, applies cleanly to `ed90b65`) exists to show the cases can be satisfied. It is not a reviewed fix: I ran only these cases against it, and it makes choices that belong to the implementer (it refuses radian bases instead of converting them, and stores attitude in the provenance record). It does not address LE-05, LE-07 or LE-08, and there is no regression case for cancellation because a timing test would be flaky; a fix should pass `cancel_check` into the section solve and assert it is called.

## 2. Distribution and native libraries

Built in a fresh virtual environment from a clean `git archive` of `ed90b65`. I wrote the build and inspection script before reading Codex's.

### Packages

| Artifact | Files | threadpoolctl notice | dataclasses notice | Native binaries |
|---|---|---|---|---|
| `git archive` ZIP of `tools/GHOST` | 279 | present | present | 8 |
| Release source ZIP | 271 | present | present | 0 |
| Wheel | 255 | **missing** | **missing** | 0 |
| sdist | 260 | **missing** | **missing** | 0 |
| Native wheel (`--native`, Linux) | 259 | **missing** | **missing** | 4 |

- **Agreement:** `_threadpoolctl.py` ships without `LICENSE-3.6.0.txt` in all three built packages. My release source ZIP has the same SHA-256 that Codex recorded.
- **Cause:** `pyproject.toml` sets `include-package-data = false` and lists no package data for `ghost_backend.execution.thread_control`.
- **Fix confirmed:** adding `"ghost_backend.execution.thread_control" = ["LICENSE-3.6.0.txt"]` restores the notice, byte-identical, in the wheel, sdist and native wheel. The fixed native wheel installs and loads its libraries.
- **Second notice:** `ghost_backend/execution/DATACLASSES_LICENSE.txt` (Apache-2.0) is also absent from the wheel and sdist, and the proposed change does not restore it. I found no vendored dataclasses code, so it may be an orphan. Someone should decide whether to ship it or delete it.
- **Diagnostic not shipped:** the wheel has neither `scripts/check_speed_paths.py` nor the `NATIVE_LIBRARIES*.json` manifests, so a wheel user cannot run the check `DISTRIBUTION.md` points to.

All 8 binaries and 4 C sources match both manifests by size and SHA-256. The Linux libraries load with every required export; the Windows DLLs were checked by parsing their export tables and were not loaded.

### Diagnostic under degraded libraries

Each state is a fresh export with one change, then the shipped diagnostic, then three 384-panel solves.

| State | Diagnostic | What actually happened |
|---|---|---|
| Baseline | 7 OK, exit 0 | all native |
| Near library missing, garbage, or without exports | **7 OK, exit 0** | near path off |
| Far library loadable without exports | **7 OK, exit 0** | far, scatter and tile paths off; solves 1.4 to 1.6× slower |
| Far library missing | 6 OK, exit 1 | correct |
| Table library without exports | 6 OK, exit 1 | correct |
| Near library truncated to 1,000 bytes | **7 OK, exit 0** | the solve is killed by SIGBUS |

- **Cause:** `check_speed_paths.py:35-38` never imports the near module and tests the far library with a bare load, not the functions that resolve its exports.
- **What the user sees on fallback:** nothing. In every degraded state that ran there were no Python warnings, no log lines, an empty `metadata["warnings"]` and an unchanged `linear_backend`. Fields agreed with baseline to 2e-14 or better. The loaders catch `OSError` and `AttributeError` and return `None` (`near.py:21-29`, `far.py:8-41`, `table.py:9-20`).
- **Truncated library (new):** a partly copied `.so` with an intact header kills the process inside `dlopen` with SIGBUS and no Python exception. This held for all four Linux libraries from 1,000 bytes to half size. Neither the loaders nor the diagnostic compare files with the manifest hashes.
- **Suggested repair:** add a near row using `near.available()`, test the far library through `library()`, `scatter_library()` and `tile_library()`, and check the manifest SHA-256 before loading.

Limits: the timings are single runs on a small problem. My fixtures never called the near kernel, so the cost of losing it is unmeasured. GUI visibility was established by reading the code, not by a degraded GUI solve. Windows loading was not tested.

## 3. Linux RAM admission

### What the probe reads

`_cgroup_available_bytes` (`twod/solver.py:1501-1525`) reads two fixed pairs of files at the cgroup mount root, v2 then v1, and returns at the first finite limit. It never opens `/proc/self/cgroup` or `/proc/self/mountinfo` and never walks ancestors. The budget is 0.9 × the detected value.

### Fake filesystem, 14 cases

An independent harness drives the production probe and the real request ledger with host availability fixed at 24 GiB.

| Case | True remaining | Release detects | Release budget |
|---|---|---|---|
| v2 nested, tight leaf | 1 GiB | 24 | 21.6 |
| v2 finite ancestor, unlimited leaf | 1 | 24 | 21.6 |
| v2 mount rooted below the hierarchy, tighter child | 1 | 6 | 5.4 |
| v1 nested | 1 | 24 | 21.6 |
| v1 finite ancestor, unlimited leaf | 1 | 24 | 21.6 |
| Hybrid v1 + v2 | 1 | 24 | 21.6 |
| v1 rooted mount, tighter sub-group | 0.5 | 3 | 2.7 |
| Nested limit, usage unreadable | 1.75 | 24 | 21.6 |
| Mount path with an escaped space | 1 | 24 | 21.6 |

The five controls (limit at the root, mount root equal to the process group, root tighter than leaf, no limit, `/proc` unreadable) are correct. No case under-admits. Codex's 24 → 21.6 GiB figure reproduces exactly.

### Real cgroups

As root I created child groups under this container's own memory group with a small probe process and removed them afterwards. No large allocation, no OOM.

| Real case | True | Release detects / budget | Over-admitted |
|---|---|---|---|
| This container, unmodified | 10.80 GiB | 14.90 / 13.41 | **+3.7 GiB** |
| Child with a 1 GiB limit | 0.96 | 14.88 / 13.39 | +12.5 |
| Unlimited grandchild under the 1 GiB group | 0.96 | 14.89 / 13.40 | +12.5 |
| Bind mount rooted at the 1 GiB group (control) | 0.96 | 0.96 / 0.87 | 0 |
| Bind mount rooted at the container group, 1 GiB limit below | 0.96 | 10.77 / 9.70 | +8.8 |

The first row matters most: an ordinary container session on this host is already over-admitted, because the limit sits three levels below the v1 mount root.

### Where I extend Codex

- **cgroup v1 and hybrid layouts are affected identically.** Codex's fixture was v2 only.
- **A rooted mount is right only when the binding limit is at the mount root.**
- **The same two root paths are read in `hpc/scheduler.py:219-232`.** One call here returned 15.71 GiB (MemTotal) against the 13.35 GiB limit. I did not run an HPC job.

### Trial fix

`cgroups/nested-cgroup-fix.patch` (`solver.py` only, +108/−6, applies cleanly, not applied). It maps the process's group through each memory mount's root and takes the minimum of limit − usage over the leaf and every visible ancestor, for v1 and v2. With it, 14 of 14 fake cases and all five real cases give the correct budget (within 64 MiB for the real ones).

Not done: no solver regression suite or solve was run on the patched copy. Usage counters include reclaimable page cache, so both release and patch may be conservative by an amount I did not measure. Ancestors above a cgroup namespace are invisible from inside it, to any fix.

## 4. Windows acceptance

Not attempted. It needs the 32 GB desktop, the intended package and a representative model. Codex's list of what to record is the right one. From this round I would add two checks on that machine: whether a partly copied DLL fails cleanly on Windows, and a Line Expansion run on a BoR base with the default shadow setting once LE-01 is fixed.

## What I did not do

- I did not rerun Codex's numerical, BoR, GUI-solver or archive-replay checks, or its 528-file tree comparison. The handoff did not ask for them, and my own reviews of those branches are on record.
- I ran no Assembly-tab job. Assembly line features call the same visibility routine; that is by reading.
- Neither trial patch was run against the repository's own test suites.

## Handoff back

1. **Line Expansion:** fix LE-01 to LE-04 and LE-09 before the tab is recommended. The 26 regression cases are ready to adopt. Decide whether a radian base is refused or converted. Pass cancellation into the section solve (LE-05), bound the sweep parser (LE-06) and correct the help text (LE-08).
2. **Packaging:** add the threadpoolctl notice to package data, decide on the dataclasses notice, and decide whether the wheel should carry the diagnostic and manifests.
3. **Diagnostic:** add the near row and export-level far checks. Consider a manifest hash check before loading, and a visible note in result metadata when a native path is unavailable.
4. **RAM admission:** adopt or rewrite the ancestor walk for both `twod/solver.py` and `hpc/scheduler.py`, then run the solver suites on it. Until then, Linux capacity claims should be limited to hosts where the limit is at the cgroup mount root.

## Files

| Path | Contents |
|---|---|
| `line-expansion/common.py`, `independent_checks.py`, `independent_results.json` | independent fixture and results at ed90b65 |
| `line-expansion/gui_checks.py`, `gui_results.json` | real-tab checks |
| `line-expansion/test_line_expansion_regressions.py`, `trial-fix.patch`, `independent_results_with_trial_fix.json` | regression cases and the patch that satisfies them |
| `line-expansion/codex_line_checks_replay.json` | Codex's script rerun here |
| `distribution/` | build, manifest and degraded-library scripts with their results |
| `cgroups/` | fake and real cgroup harnesses, results, trial patch, and its own README |

Reproduce the Line Expansion part from `line-expansion/`:

```bash
export GRIM_ROOT=/path/to/checkout-of-ed90b65 QT_QPA_PLATFORM=offscreen
python independent_checks.py out.json
python gui_checks.py gui.json
python -m pytest -q test_line_expansion_regressions.py
```
