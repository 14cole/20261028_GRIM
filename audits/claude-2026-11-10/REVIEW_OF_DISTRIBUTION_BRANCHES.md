# Review of Codex's distribution branches

- **Reviewed:** `distribution/grim-native-2026-11-10` at `4a07de6` and `distribution/grim-ux-2026-11-10` at `ef6753d` (the UX branch sits on top of the native one; both start from `f207c61`).
- **Compared against:** my reviewed head `4f97977` on `claude/festive-keller-nj5bje`.
- **Environment:** Linux x86-64 (glibc 2.39), Python 3.13, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 with the offscreen platform. The GUI was driven headlessly; I did not look at rendered pixels.

## Verdict

Both branches are sound. Nothing in them changes solver numerics, the shipped Linux libraries are what their manifest says, and the simplified solver UI describes behaviour the solver actually has. I found no blocking defect. There are six small items, mostly wording left behind by the UI change and tooltips that no longer reach the user.

## What I verified

### Native distribution (`4a07de6`)

| Check | Result |
|---|---|
| Solver source against my head | every `.py` and `.c` file under `tools/` and `GRIM_Backend/` is identical |
| Four shipped `.so` files against `NATIVE_LIBRARIES_LINUX.json` | size and SHA-256 match; recorded source hashes match the C sources |
| Required exports | all present |
| Recorded dependencies and symbol versions | match `objdump` (highest glibc symbol 2.35, in `libghost_near.so`; `libgomp.so.1` with GOMP_4.0/OMP_1.0 for the BoR kernel) |
| Loading here | `check_speed_paths.py` reports every native path OK |
| Fields with the shipped libraries against my own gcc 13 build | bit-identical on all 31 reference sets |
| My regression set against the UX tree | 207 of 207 checks pass |

The documentation edits on this branch only replace repository-relative paths to audit material with permanent links to `4f97977`, which is right for a tree that no longer carries `audits/`.

### UI simplification (`ef6753d`)

Only `ui/solver.py`, `ui/twod_options.py`, `ui/geometry.py`, two call sites in `runs/setup.py` and three guides changed. No stale reference to a removed widget remains in any Python file.

Each statement the new UI makes was checked against the solver:

| UI statement | Check | Result |
|---|---|---|
| Startup keeps the old checked/adaptive default | captured controls at startup | workflow "automatic": compressed, adaptive, certification on |
| "Solve specified mesh" replaces the one-shot preset | uncertified solve with `adaptive` against `global` P1 | same panel count, bit-identical fields |
| "Check specified mesh" solves that mesh and a finer copy | panel counts for "solve" and for the base of "check", explicit N with and without grading | equal in each case (48/48, 64/64, 48/48) |
| …at the same polynomial order, with the selected linear solver | certified run, global P2 compressed and global P1 dense | base and fine both P2 (or P1); backend unchanged |
| …and publishes the finer result | certificate metadata | `published_mesh: fine` |
| Local sizing can retry Global | `twod/solver.py:3976-3986` | present |
| Automatic search is 2D monostatic only | bistatic and BoR | item disabled; choice falls back to "check" |
| Bistatic uses Dense | `automatic_run('bistatic')` | dense, global |
| BoR single mesh still checks Fourier-mode convergence | mode truncation raises on non-convergence | true |
| Switching workflow preserves backend, order, sizing, grading | dense / local / P2 / grading off, through automatic and back | preserved |
| Each solver kind remembers its own workflow | 2D monostatic, bistatic, BoR round trip | remembered |
| Grading can add panels to a single-mesh solve | N = 12 square | 64 panels with grading, 48 without |

## Items to fix

None blocks a merge.

1. **Menu tooltips never appear.** The new `QMenu`s in the Geometry tab do not call `setToolTipsVisible(True)`, so Qt does not show the tooltips set on their actions. That loses guidance the old buttons carried: what "Refine selected 2x" does to automatic N, the accepted CSV column names for impedance tables, the FREDDY outer-envelope note, and the new "selects rows only" and thin-layer explanations. One line per menu fixes it.
2. **Geometry cheat sheet still names removed controls.** `GEOMETRY_INPUT_CHEATSHEET.md` lines 141-142 ("**Certify mesh convergence** option is enabled by default"), 148-150 ("**Find corners/junctions** and **Refine selected 2x** … These buttons"), 152 ("click **Reverse selected**"), 217 and 683 ("**+ Thin layer**"). Only the "Apply IBC" reference was updated.
3. **Two status strings still say "mesh certification".** `ui/geometry.py:1394` ("use mesh certification to check complex-field accuracy") and the policy line from `runs/controls.py` ("Mesh certification: On (compare meshes)" / "Survey — mesh convergence not checked"), which now sits beside labels that say "Check specified mesh".
4. **"Dense (manual override)" is a leftover label.** The override checkbox it referred to is gone; the combo box is now an ordinary choice. `FACTORIZATION_LABELS` in `runs/controls.py`.
5. **The policy line shows 2D settings while BoR is selected.** With BoR chosen, the Advanced policy text still reads, for example, "Factorization: Dense (manual override). Mesh: Local; polynomial order: P2. Corner grading: Off", none of which applies to BoR. This predates the UI change, but the new "Linear solver: BoR modal solver" label directly contradicts it now.
6. **Removing a surface material now needs a selection; removing a dielectric does not.** "Remove selected" is disabled with nothing selected, while the dielectric table keeps its "-" button that removes the last row. Harmless, but the two tables behave differently.

## Notes, not defects

- `.gitignore` on the distribution branches changed its line endings for most lines, so its diff looks larger than the two real changes (Linux libraries whitelisted; `/audits/` and `SOLVER_AUDIT_2D_BOR.md` ignored).
- The Linux libraries need glibc 2.35 or newer, as `DISTRIBUTION.md` says. Older distributions fall back to NumPy silently unless the user runs `scripts/check_speed_paths.py`.
- The mesh tooltip says negative N uses wavelength sizing. True; `N = -1 .. -3` are now refused, which the cheat sheet states.
- `QFormLayout.setRowVisible` needs Qt 6.4; the project requires PySide6 6.6 or newer, so this is fine.
- The commit message reports 33 Qt/worker checks; those are not in the repository, so I could not run them. My own headless checks are described above.
