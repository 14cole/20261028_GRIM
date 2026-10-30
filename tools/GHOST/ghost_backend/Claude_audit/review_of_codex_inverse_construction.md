# Review of Codex's inverse-construction checks (2026-10-29)

Reviewed:
- `Claude_audit/inverse_construction_implementation_20261029.md` (the handoff)
- `Codex_audit/inverse_construction_20261029/`: README, `source_hashes.json`, `validation_summary.json`, `benchmark.py`, the four benchmark JSONs, `benchmark_comparison.json` and `prior_implementation_integrity.json`
- The working-tree source on your PC, diffed against Codex's saved `baseline/` copies (which match GitHub `743d639`):
  - the new `compressed/construction.py`
  - `execution/memory_budget.py`, `compressed/inverse.py`, `compressed/hmatrix_factor.py`, `compressed/hmatrix.py`, `compressed/factor.py`, `compressed/preconditioner_hints.py`, `linalg/hierarchical.py`

**Not on GitHub yet:** `main` is still `743d639`. I read code and saved results only; I ran no tests or solves.

## Verdict

**The change is correct and it answers the prerequisite I raised last round.** The unfinished inverse tree is now counted against the request while it's being built, and every expensive step checks live headroom *before* it allocates. Before this, the tree being built belonged to nobody, so the ledger couldn't see it until construction finished.

The numerics are untouched: both benchmark sizes give **bit-for-bit identical** solutions and identical inverse residuals (8.30e-12 and 1.26e-11).

The cost is time, and that's the one thing I'd change before relying on it (finding 1).

Codex kept every standing decision: compressed is the default, dense and surface impedance are overrides only, and there's no forecast discount or saved solve history. The new next-mesh correction is recorded as metadata only.

## Codex's response to my last report: accepted

| My suggestion | Codex's position | Mine |
|---|---|---|
| Stop escalating to finer meshes after a memory refusal, saving about 57 s | The later steps are priced before any assembly, so their refusals cost under 2.17 s in total. Cutting the chain on unknown counts alone could remove a path that works. | **Accept.** My 57 s included work that had to happen anyway. Not worth the risk. |
| Correct the next mesh's forecast from the measured quadratic mesh | Implemented in shadow mode only: recorded, never used for admission, until independent cases qualify it | **Agree.** That's the right order now that construction is bounded. |

## Implementation checked

| Change | What the code does | OK? |
|---|---|---|
| **Construction ownership** (`construction.py`) | The inverse being built is registered with the request when the build starts and removed on success, failure or cancellation. Temporary arrays are counted once per backing buffer, so views aren't counted twice. The helper holds the inverse weakly, which fixes the reference cycle Codex's own test caught. | Yes |
| **Allocation groups** (`memory_budget.construction_allocation`) | Before each step, its modelled extra allocation is checked against the reservation, live RAM and live commit, minus every request's outstanding holds. The check and the hold happen together under the global lock, so two requests can't both claim the same headroom. Holds are released in `finally`, and a refused check never takes a hold. | Yes |
| **Where the checks are** | Sampled range growth, projection, QR, SVD, output, ACA, leaf coefficient reads, LU, child products and Woodbury corrections. I checked that no step is nested inside another, so no request is charged twice for its own hold. | Yes |
| **Retained cap checked earlier** | Each off-diagonal block is now charged as soon as it exists, before its partner is built. A leaf's storage is checked before its coefficients are read. If a small node falls back to a leaf, the charge is rolled back. The totals match the old code exactly on both the inverse-only and the operator paths. | Yes |
| **Preconditioner upgrade** (`factor.py`) | The old inverse stays counted while its 1e-10 replacement is built. It's counted once even while it's still the active factor. | Yes |
| **No coefficient copies in adjoint products** (`hmatrix.py`) | Conjugates the small input and output instead of copying the stored factors. Conjugation is exact in floating point, which is why the results stay bit-identical. | Yes |
| **Shadow observations** (`preconditioner_hints.py`) | After a validated solve, records forecast against actual operator and inverse sizes. For a larger mesh later in the same request and polarization, it records what the corrected forecast would have been (my proposal: ratio × 1.5, capped at the original) and whether it would have under-predicted. At most 16 entries, no matrices, discarded with the request. It never touches the plan, cap or tolerances. | Yes |
| **Tests** | 260 tests and 39 subtests pass across 19 files. The five files from the last round match their saved hashes. One old test expected the removed automatic picker; it now asserts the compressed default and keeps its accuracy and memory checks. That matches your decision. | Yes |

## Findings

### 1. The checks triple small inverse build times; skip the OS query for small steps (medium)

| Unknowns | Checks | Before | After | Added time per check |
|---:|---:|---:|---:|---:|
| 1,536 | 398 | 0.080 s | 0.262 s | 0.46 ms |
| 4,096 | 814 | 0.241 s | 0.632 s | 0.48 ms |

Each check costs a steady ~0.47 ms. It calls `checkpoint()`, samples process memory twice and runs `limit()`. `limit()` queries free RAM and commit from the OS, walks every registered object, and snapshots any live worker processes.

At large sizes this is probably a small fraction of the time. Extrapolating the check count (about N^0.73), 85,000 unknowns would need about 7,500 checks, or roughly 3.5 s per inverse build. That's an estimate, not a measurement. Two cases could make it worse than the benchmark suggests:
- The benchmark used **2 assembly workers**. The automatic profile uses 8, and `owned()` snapshots every live worker team on each check. On hierarchical meshes the idle workers are closed, but on tile meshes they're alive.
- Every certification builds the inverse at least twice per polarization: the initial build, the 1e-10 upgrade, then again on the next mesh.

**Suggestion:** keep the arithmetic retained-cap checks on every step, but make the live OS check conditional. Skip it when the step's extra allocation is small (say under 16–32 MiB) **and** the total skipped since the last live check is under a slack of, say, 64 MiB or 1% of the reservation. In the benchmarks the largest single step was only 15–40 MiB, so most checks would be skipped. Also drop the second `sample()` after each step, or take it only on a live check.

Before adopting either version, run one timed A/B of the ordinary inlet with the automatic CPU profile (about 4 minutes; it needs your go-ahead). That gives the real end-to-end cost.

### 2. Inverse steps now push useful entries out of the memory report (low, diagnostic)

`_check` keeps the last 64 checks in `report()['checks']`. Every construction step now adds one. After a solve, the 64 kept entries will almost all be "Compressed inverse …", and the phase admissions and reload checks that explain a refusal will have dropped out. A refused step is still reported correctly, because it raises.

**Fix:** don't append *admitted* construction checks to `events`, since they are already summarised in `evidence['construction']`. Keep appending refusals.

### 3. The "covered reload" skip goes by size, not by what was actually priced (low, latent)

`admit_reload` now skips its check whenever a reload is no larger than the enclosing allocation group. But the group's size comes from the product workspace model (`range_workspace_bytes`), which doesn't include any spool reload. So the rule really means "any reload smaller than this step is free". It also doesn't add up several reloads inside one group.

Today this is harmless: the full spool reloads (`load()` and `restore()`) are all called from `compressed/runtime.py` and `polynomial_pair.py`, outside inverse construction. The retained-storage cap still bounds them as well. But a future change that reloads inside a product would bypass the live check without anyone noticing.

**Fix:** have the group pass an explicit allowance that is consumed by each reload (`covered -= payload`), or only skip reloads that the step's model marks as priced.

### 4. Shadow observations only happen in single-frequency requests (note for the qualification study)

`_key` returns nothing unless the hint scope is enabled, which requires `len(frequencies) == 1`. So multi-frequency sweeps, including parallel ones, record no shadow data. That's fine, but the qualification cases Codex proposes must be run one frequency at a time, or they'll quietly produce no observations.

### 5. The shadow record should also compare construction, not only retained storage (low)

The proposal scales the operator and the retained inverse. The record stores the construction forecast and the accounted build peak, but doesn't compare them or propose a corrected construction figure. Since the build peak is what has to fit, add one ratio: `peak_accounted_build_bytes ÷ inverse_construction_bytes`, with the same under-prediction flag. Then the study can show whether a corrected forecast would also have under-estimated the build.

### 6. Run the full test suite before pushing (low)

The 260 tests are a targeted subset; the last full run was 624 tests across 45 files. `memory_budget.py` is used by most solver paths, so run the full suite once before you push.

## What this means for the 2 GHz case

The safety prerequisite for an in-request forecast correction is now mostly met. The build is counted while it runs, and each step is checked before it allocates. What's left are modelled LAPACK and product workspaces, and peaks between checkpoints, which Codex documents honestly.

But the shadow mode **can't qualify the 2 GHz case itself**. The cubic mesh is refused at admission, so it never runs and never produces an observation. The qualification has to come from cases where both the quadratic and cubic meshes fit. That's what Codex proposes: lossy, low-loss, concave and coated cases with external peak monitoring.

## Recommended order

1. **Keep the change.** Before pushing (your call), make the small fixes 1 to 3 and run the full test suite.
2. **One timed inlet A/B** with the automatic CPU profile, to measure the real cost of the checks. About 4 minutes; needs your go-ahead.
3. **Shadow qualification:** a handful of single-frequency material cases where both meshes fit, reporting storage *and* construction ratios. Each is a few minutes of solve time, so batch them with your OK.
4. Only if no case under-predicts: enable the correction for admission. Then retry the 2 GHz full-material run (one solve, 2–5 minutes).
