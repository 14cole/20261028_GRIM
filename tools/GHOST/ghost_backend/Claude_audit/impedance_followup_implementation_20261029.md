# Handoff: implemented impedance-experiment audit follow-ups

## Implemented

Production changes are limited to `execution/failure.py` (new), `execution/cpu.py`, and `twod/adaptivity.py`.

1. Adaptive rejection reasons and steps now survive conservative retries and failed reference fallbacks. The original exception type and cause remain; `solver_diagnostics` contains structured records, Python 3.11 traceback notes carry JSON, and ordinary error text includes concise earlier causes.
2. Compressed numerical errors now report an informational dense estimate for the actual failed mesh and the stated angle batch. It prices a fresh retry after failed resources are released, resets temporary compressed batch shrink, honors environment-only profiles, and checks the current effective allowance. It neither allocates a dense matrix nor starts a dense solve. No automatic backend picker or physics conversion was added. Further mesh refinement and numerical convergence are explicitly outside that estimate.
3. A bounded interaction-sampling prototype was implemented and evaluated in the audit folder. It remains experimental; production admission is unchanged because it underpredicted a held-out operator by 7.48%.

The conditional suggestion for a new impedance GUI was not implemented. Existing explicit opaque IBC input remains available and default physics is unchanged.

## New evidence worth reviewing

The improved 2 GHz failure record resolves the earlier uncertainty. Under the 12 GiB study cap, the quadratic candidate completes. Its cubic check is refused at 13.28 GiB / 32,052 DOFs. The conservative retry is refused at 17.46 GiB / 42,708 DOFs, then the linear fallback at 33.57 GiB / 85,462 DOFs. These are memory-admission failures, not evidence of a failed mesh-convergence comparison. Previously only the final refusal survived.

A separate 16 GiB requested-cap trial still could not admit the cubic mesh. Windows commit headroom was binding: initial physical availability 16.27 GiB, initial commit availability 14.39 GiB, final effective allowance about 12.15 GiB. The actual full bulk memory requirement at 2 GHz remains unmeasured. No OS/pagefile settings were changed.

The refined small magnetic failure also reveals two different attempted meshes. Its first failed cubic candidate had a dense estimate around 3.64 GiB; the final doubled candidate had an estimate around 10.42 GiB and fit the observed allowance. The historical successful 23.39-second dense solve used the smaller candidate. Same input geometry/density did not mean the final adaptive mesh was identical. The new guidance deliberately identifies the mesh that actually failed and does not promise a whole certified-job fit.

## Pilot results and limits

`Codex_audit/impedance_followups_20261029/pilot.py` wraps assembly only inside isolated study workers. It samples at most eight interaction lists, with rank 64, four million queried entries, 262,144 entries per returned array, a 15-second cooperative time check, and live checks for 128 MiB additional workspace. These are empirical work/query bounds, not a formal bound on all Python/BLAS allocations. Unobserved levels retain the geometry forecast. The fixed sampled-rank margin is 1.5x plus eight. Inverse retention/construction forecasts are not discounted.

The smaller magnetic operator estimate improved from about 0.91 GiB to 0.54 GiB against 0.38 GiB actual, with about 1.05 seconds of sampling. However, the held-out moderate and low-loss operators were underpredicted, worst 7.48%. Larger interaction lists sometimes reached the query bound and retained much of the old conservative forecast. All four pilot-study solves certified, and both magnetic comparisons were bit-identical to saved reference fields. This validates preservation of solve results, not the accuracy of the admission prediction. Do not promote the pilot without better coverage and separate inverse/construction evidence.

## Validation

Final suite: **158 passed, 39 subtests passed, zero failures**, 13 files, 60.97 seconds. Exact command and source hashes are in the audit folder. Tests cover failure identity/cause, serialized evidence, both retry paths, fit/non-fit guidance, unavailable diagnostics, cancellation/input errors, no dense allocation, fresh-batch pricing, environment profiles, numerical regressions, memory accounting, desktop/HPC execution and concurrency.

The existing CPU-isolation concurrency test was repaired to give each simultaneous request a one-GiB reservation and a synchronized start. Previously both unreserved jobs could race to reserve the whole cohort and legitimately leave one zero allowance. Numerical equality and state-isolation assertions remain. An early new-test mock-import leak was also corrected; raw validation attempts remain alongside the final successful report.

Seven serial real-geometry trials are retained: four certified pilot-study solves, two reproduced original failures/refusals, and the larger-cap refusal. Regression tests ran afterward. Original historical evidence hashes remain unchanged. The initial diagnostic trials precede final text-shortening and fresh-batch wording refinements; final regressions cover finalized source.

## Review targets

- Confirm failure annotation never changes the exception category, retry selection, current memory plan or cancellation behavior.
- Confirm dense guidance is strictly informational and scoped to the stated mesh/batch after cleanup, not a guarantee for a full adaptive job.
- Confirm the experimental pilot is never imported by production and the existing memory model/admission paths are unchanged.
- Review whether a later bounded inverse/construction pilot could safely reduce conservatism. Operator samples alone do not justify the 2 GHz fallback admission.

See `Codex_audit/impedance_followups_20261029/README.md`, `summary.json`, `validation_summary.json`, `source_hashes.json`, plans and per-run records. Nothing has been pushed in this turn.
