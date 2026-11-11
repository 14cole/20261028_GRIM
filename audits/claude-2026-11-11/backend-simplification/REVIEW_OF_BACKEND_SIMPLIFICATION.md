# Review of Codex's backend simplification

- **Production commit reviewed:** `c20b9ed` on `distribution/grim-driver-simplification-2026-11-11`.
- **Base:** `6dd0a1f` (`distribution/grim-backend-cleanup-fix-2026-11-11`).
- **Codex's handoff:** `codex/backend-simplification-2026-11-11` at `ad3da97`, `audits/codex-2026-11-11/backend-simplification/CLAUDE_HANDOFF.txt`.
- **My environment:** Linux x86-64, 4 vCPU. Python 3.13 (NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0 offscreen) and, for a second pass, Python 3.11 with the same NumPy and SciPy.

## Verdict

Accept. I found no defect introduced by this commit. The refactor does what the handoff says, and nothing it changes alters a number, an output file's arrays, a restart decision or an error path that a real run can reach.

Two things are different from the base, both harmless and one of them intended. They are listed under "Behaviour differences".

This is not a release sign-off. The Line Expansion defects are untouched and still present, and nothing here was run on Windows, on Python 3.10, or under a real SLURM scheduler.

## What I checked, and the result

### 1. Numerics

| Check | Result |
|---|---|
| 31 reference field sets, base vs new, shipped Linux libraries | 31 of 31 bit-identical |
| Same, with every `.so` and `.dll` removed (NumPy fallback confirmed by `check_speed_paths.py`) | 31 of 31 bit-identical |
| New tree, Python 3.11 vs Python 3.13 | 31 of 31 bit-identical |
| My regression set on the new tree, Python 3.13 | 207 of 207 checks pass |
| My regression set on the new tree, Python 3.11 | 207 of 207 checks pass |

### 2. The moved BOR code

Codex compared syntax trees. A function moved to another module also changes which module's global names it sees, which a syntax comparison cannot detect, so I checked that directly (`bor_move_check.py`):

| Check | Result |
|---|---|
| Top-level definitions in `bor/solver.py` | 109 on the base, 90 now; 19 removed, none added |
| Each removed definition present in `constraints.py`, `storage.py` or `validation.py` with an identical syntax tree | 19 of 19 |
| Each remaining definition identical to the base | 90 of 90 |
| Every global name read by the moved code resolves to the *same object* the solver module sees | 260 of 260 reads |
| Each moved name re-exported from `bor.solver` as the identical object | 19 of 19 |
| The 37 literal constants of the base solver, in the new solver's namespace | all present, all equal |
| Solver globals rebound at run time that moved code reads | none exist |

### 3. Worker pipelines: real runs, base against new

Codex ran each driver once on the new tree only, uncertified, and checked that files were produced. I ran all four drivers on both trees, with two frequencies and two geometries, with mesh checking off and on, and compared every numerical array in every output file (`driver_end_to_end.py`, `driver_compare.py`, output in `driver_compare.out`).

| Driver | Mesh check | Artifacts | Arrays compared | Arrays differing |
|---|---|---|---|---|
| Local 2D | off / on | 4 / 4 | 24 / 24 | 0 / 0 |
| HPC 2D (dry submit, then the frozen worker) | off / on | 4 / 4 | 24 / 24 | 0 / 0 |
| Local BOR | off / on | 10 / 10 | 74 / 74 | 0 / 0 |
| HPC BOR (dry submit, then the frozen worker) | off / on | 10 / 10 | 74 / 74 | 0 / 0 |

Restart behaviour of the HPC workers, identical on base and new in every case:

| Scenario | Outcome on both trees |
|---|---|
| Run the worker a second time | exit 0, nothing rewritten |
| Delete one artifact and its claim, rerun | only that artifact rewritten; its arrays equal the original; no other file touched |
| Edit the frozen input, delete an artifact and its claim, rerun | worker exits 1 with "Frozen geometry/material input … changed/mismatch"; the artifact is not recreated |

The frozen runtime copied into each run directory holds 214 Python files on the new tree against 209 on the base: the five new modules.

### 4. Worker pipelines: control flow under failure

Codex's 38 mocked fixtures match between base and new (re-run here: identical). The handoff asked me to challenge them with cancellation and interrupted-publication cases. I added 54 (`worker_extra_cases.py`), covering all four drivers:

- input changed before the solve;
- `InterruptedError` and `KeyboardInterrupt` raised inside the solve;
- export failing, and for BOR failing on the second channel after the first was written;
- attestation embedding failing; the attestation builder itself failing;
- geometry loading failing;
- a malformed certification policy;
- a result with no warnings, and a result with no metadata at all;
- for BOR: the second channel already present, a bad attestation on the second channel only, a co-solved channel missing from the result, an execution plan together with certification, and an empty execution plan.

Each case records the full event sequence, the files left on disk and their contents, the return value and the exception type and text. 53 of 54 are identical between base and new, under Python 3.13 and 3.11. The one that differs is described below.

By direct reading as well: the base's local and HPC 2D workers differed only in the history string and a variable name, so merging them into one function loses nothing. The HPC BOR worker's precedence (execution plan, then solver configuration, then driver setting) is preserved line for line.

### 5. Explicit settings

`settings_behaviour.py` runs the same probes on both trees for all four drivers: attribute visible before configuration, default settings, attribute read after configuration, the missing-parameter error text, state after a rejected configuration, reconfiguration, unknown keys, unknown attributes, pickling, and mutation of the returned dictionary. 12 of 13 probes are identical per driver. The thirteenth is the intended change described below.

Other points:
- A static scan of the four refactored drivers finds no undefined name. That matters because a bare global left behind would not be served by the module-level `__getattr__` and would only fail when that line ran.
- No file in the repository reads or assigns a driver's configured attributes from outside; the four `run_*.py` scripts all go through `run(globals(), __file__)`.
- Codex's 43 settings checks pass here on 3.13 and 3.11; its settings-and-attestation probe is byte-identical between base and new.

### 6. GRIM integration and packaging

| Check | Result |
|---|---|
| Production branch contains audit files | none |
| Evidence branch differs from production outside `audits/` | no |
| GRIM diagnostics | exit 0 |
| GHOST modules GRIM can request | 68 of 68 load |
| Files GRIM requires of a complete backend | 126 of 126 present, including the five new modules |
| Removing each new module in turn | discovery correctly rejects the backend, 5 of 5 |
| Codex's integration regression | 16 of 16 pass |
| Codex's GUI and worker checks | 59 of 59 pass (33 + 26) |

Adding the new modules to GRIM's required-file list in the same commit is the right response to the previous round's regression.

### 7. The removed UI helper

`ui/geometry.py: _parse_mesh_n_token` had no caller anywhere in the repository; the live copy is in `geometry/validation.py`.

## Behaviour differences from the base

1. **Intended: a captured configuration no longer follows later edits to the caller's objects.** On the base, appending to a list after `configure()` changed the run's settings, because the driver held the same list. Now it does not. Codex documents this. I confirmed it is the only settings difference.

2. **Unintended but unreachable: an HPC BOR result with no `metadata` key.** The base raised `KeyError` when printing warnings; the shared pipeline tolerates the missing key (as the base's *local* BOR worker already did) and goes on to write the artifacts. The real solver always returns `metadata`, so no actual run can reach this. With an execution plan present, both trees still raise. I mention it only so that it is not rediscovered as a mystery.

Also changed, and harmless: the order of keys inside the 2D attestation record (`polarizations` now follows `frequency_ghz`). Verification compares field by field, so nothing depends on the order. Archive bytes can differ, as Codex notes.

## Notes on Codex's evidence

- The handoff's numbers reproduce: 207, 31 + 31, 38, 43, 59, 16, 68, 126 and 5.
- Its driver smoke test would not have caught a wrong number or a wrong restart decision, because it ran one tree and asserted only that files exist. The base-against-new comparison above closes that gap.
- Its statement that no speed or memory change is claimed is right. I did not benchmark, and line counts say nothing about either.

## What remains unverified

- **Windows** and the shipped DLLs: not executed by either of us.
- **Python 3.10**, GHOST's declared minimum: no interpreter was available. Python 3.11 is covered in full above, and Codex's grammar check passes for 3.10.
- **A real SLURM submission**: the HPC paths were exercised by dry submission plus local execution of the frozen worker.
- **Line Expansion and full Assembly jobs**: unchanged by this commit and not re-tested. LE-01 to LE-09 still apply.
- **External code** that assigns `driver.SOME_SETTING = value`, imports the removed private UI helper, or pickles the moved storage records by their old module path: none exists in the repository; I cannot see outside it.

## Answers to the six requests

| Request | Answer |
|---|---|
| 1. Shared pipelines: ordering, partial restart, polarization, plan precedence, scopes, exceptions, provenance | Confirmed by reading, by 92 mocked cases (38 + 54), and by eight real base-against-new driver runs. One unreachable difference found. |
| 2. Settings boundary | Confirmed; one intended difference. No in-repository caller depends on module-attribute mutation. |
| 3. Moved BOR definitions, exports, bundles | Confirmed, including object identity of every global read. All five modules reach the frozen runtime. |
| 4. GRIM discovery, module map, negative checks, branch hygiene | Reproduced. |
| 5. Native and fallback numerics, driver runs | Reproduced independently, and extended to Python 3.11. Windows, 3.10 and SLURM not available. |
| 6. Line Expansion kept separate | This commit introduces no regression there and fixes nothing there. |
