# Review of Codex's backend cleanup

- **Production commit reviewed:** `32eb406` on `distribution/grim-backend-cleanup-2026-11-11`.
- **Base:** `7216291` (`distribution/grim-ux-2026-11-10`).
- **Codex's evidence:** `codex/backend-cleanup-2026-11-11` at `f86c40e`, `audits/codex-2026-11-11/backend-cleanup/`.
- **My environment:** Linux x86-64, Python 3.13, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 offscreen. Not run on Windows or on Python 3.10.

## Verdict

Do not ship this commit as it stands. The cleanup itself is numerically clean and the removed code is dead, but deleting two of the files breaks the main GRIM application's link to GHOST. The fix is three lines in a file the cleanup did not touch. With that fix applied in a scratch copy, everything I checked passes.

## Blocking defect

### BC-01 (P1): GRIM can no longer find its GHOST backend

- **Trigger:** any GRIM feature that reaches GHOST on the cleaned tree: the embedded GHOST tab, the Assembly panel, interference metrics, the headless assembly workflow, and `GRIM_Backend/run_diagnostics.py`.
- **Cause:** `GRIM_Backend/execution/diagnostics.py` lists the files a complete GHOST backend must contain. That list (`GHOST_SENTINELS`, lines 210-) still names two files this cleanup deleted:
  - line 220: `execution/thread_control/_threadpoolctl_py36.py`
  - line 226: `execution/_dataclasses.py`

  `GRIM_Backend/integrations/ghost.py:32` uses the same list to decide whether a backend is usable. The thread-control diagnostic at line 567 also still requires `LICENSE-2.2.0.txt`, which was deleted too.
- **Expected:** GRIM locates `tools/GHOST/ghost_backend` and loads modules from it, as on the base.
- **Actual:**

  | Check | Base `7216291` | Cleaned `32eb406` |
  |---|---|---|
  | `discover_ghost_backend()` | the bundled backend path | `None` |
  | `load_ghost_module('assembly_inspector')`, `'grim_io'`, `'line_expand'` | load | `ImportError: No complete GHOST backend was found` |
  | GRIM diagnostics startup exit code | 0 | 1 |
  | Required diagnostics failing | none | "GHOST workspace files" (2 missing) and "BLAS thread control" (`LICENSE-2.2.0.txt` not found) |

- **Why Codex's checks missed it:** its reference scan looked for callers of the removed *functions*. The removed *files* are referenced by path, as strings, in the other application. Its 293 checks all run inside GHOST; none start from GRIM.
- **Fix, verified in a scratch copy:** delete the two entries from `GHOST_SENTINELS` and change the license loop from `("3.6.0", "2.2.0")` to `("3.6.0",)`. With those three edits the diagnostics exit 0 and all three modules load.
- **Reproducers:** `grim_ghost_integration_check.py <checkout>` and `grim_diagnostics_check.py <checkout>` beside this file.

## What I verified and found correct

### The six removed helpers are dead

Whole-repository search (Python, C, Markdown, JSON, TOML; `tools/` and `GRIM_Backend/`) on the base:

| Helper | References on the base other than its definition |
|---|---|
| `bor/kernels.py: _cosine_moments` | one comment in `bor_stream_kernel.c:1028` |
| `bor/kernels.py: _project_parity_brackets` | one comment in `bor_stream_kernel.c:1032` |
| `bor/kernels.py: _checked_near_kernels` | none |
| `bor/solver.py: _graded_cells` | called only by `_cell_points`; one docstring in `sharp_pairs.py:4` |
| `bor/solver.py: _cell_points` | none |
| `twod/formulations/regions.py: _assemble_system_fresh` | none |

No `getattr`-style dynamic lookup of any of them exists. `_CELL_CACHE` is still used by the live regular-cell path, as Codex says. The two C comments and the `sharp_pairs.py` docstring now point at functions that no longer exist; that is cosmetic, and leaving the C sources byte-identical is the right call given the recorded library hashes.

### Numerics are unchanged, native and fallback

| Comparison, 31 reference field sets | Result |
|---|---|
| Base vs cleaned, shipped Linux libraries | 31 of 31 bit-identical |
| Base vs cleaned, all `.so` files removed (pure NumPy path confirmed by `check_speed_paths.py`) | 31 of 31 bit-identical |
| Cleaned native vs cleaned fallback | differ by at most 2.8e-12, as expected between the two paths |
| My regression set on the cleaned tree | 207 of 207 checks pass |

Codex ran the before/after comparison on the native path only; the fallback comparison above is new.

### Python-version backports

- GHOST declares `requires-python = ">=3.10"`, and its four driver scripts and `hpc/check_environment.py` already refuse anything older. GRIM requires 3.11. So the dataclasses and threadpoolctl 2.2.0 backports were unreachable in any supported run.
- `ScopedValue` on Python 3.7 and later already took the `ContextVar` branch, so removing the thread-local branch changes nothing on supported interpreters.
- The standalone CEM tools still declare Python 3.6. They do not import `execution/runtime.py` or the removed backports, so that boundary is intact. The moved module parses under 3.6 grammar (checked with `ast.parse(feature_version=(3, 6))`); like Codex, I had no 3.6 interpreter to run it.

### The moved certification-evidence code behaves the same

- Both import orders work, embedded (`ghost_backend.data_tools.cem_tools`) and standalone (`cem_tools`), and importing `grim_native` no longer loads the new module.
- Thirteen inputs of my own (empty, non-JSON, wrong schema, wrong container types, partial and malformed source records, NaN, an array where a scalar is expected) give identical results or identical exception text on the base and the cleaned tree. Script: `evidence_inspection_cases.py`.
- `setup.py` uses `find_packages`, so the new module is packaged without further change.

### Nothing else moved

The commit changes exactly the 11 files Codex lists. No native library, C source, manifest or UI file differs from the base.

## Smaller observations

1. **The relocated 460 lines have no caller in the repository.** `_mesh_certification_sources` is not called anywhere on the base or the cleaned tree; only its own definition and constants reference it. Codex kept it as "explicit inspection", which is a defensible choice for external users of the CEM tools, but it should be described as retained-unused code, not as a live feature. If no external consumer exists it could be deleted outright.
2. **`linalg/workspace.py` still says "(Python 3.6+)"** in its module docstring, the last such statement in GHOST proper.
3. **Line-count claim checks out:** 481 added, 2,814 removed. As Codex says, no speed or memory change should be inferred, and I measured none.

## Not part of this cleanup

- The Line Expansion defects (LE-01 to LE-08 and my LE-09) are untouched by this commit and still present. Nothing in this cleanup makes them better or worse.
- I did not review `codex/line-expansion-review-2026-11-11`, which appeared in the same fetch.

## Answers to Codex's six requests

| Request | Answer |
|---|---|
| 1. No live or dynamic callers of the six helpers, searching beyond `tools/GHOST` | Confirmed for the helpers. The same wider search found BC-01 for the deleted files. |
| 2. Interpreter floor and CEM-tools boundary | Confirmed by declaration and by import graph. Python 3.10 and Windows not executed. |
| 3. Lazy module in both import orders, packaging, exceptions, callers | Confirmed; no in-repo caller exists. Thirteen independent inputs match. |
| 4. Regression and before/after fields, native and fallback | Reproduced; bit-identical on both paths. |
| 5. Library and source hashes; Windows DLLs | No native file differs from the base. Windows not available. |
| 6. Separate Line Expansion findings from cleanup regressions | The only regression introduced by this cleanup is BC-01. |
