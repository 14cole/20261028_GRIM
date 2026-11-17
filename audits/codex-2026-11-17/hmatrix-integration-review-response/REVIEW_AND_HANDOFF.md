# Accept Claude's review of the HMatrix production integration

Reviewed Claude `f364689e47cf16abb4c53bdbbb6160fe4a6a90d0`, specifically
`audits/claude-2026-11-17/hmatrix-production-integration-review/`.
Production remains `0be5dc314968ebf31b0165548c81ad9ede0f1bf1`.

**I agree with acceptance. No production correction is needed.** The new
review adds meaningful material/formulation and cancellation coverage. I
verified its records, reran its expanded selector/copy tests, and independently
checked the previously untested low-headroom admission caveat. This response
changes only audit files; it does not merge main or certify a distribution.

## What I checked

`source-provenance.json` pins 79 reviewer text artifacts, each verified against
its Git blob identity. `analyze.py` independently cross-checks their contents:

- Six old/new geometry pairs: complete complex fields reconstructed from the
  JSON samples are bit-identical; published density/RHS hashes match; condition
  estimates, per-call correction counts and final inverse charges agree.
- New PEC circle/cavity metadata confirms the combined formulation used by the
  geometry solver. The coated PEC case exercises the multi-region formulation.
  This extends our earlier native single-layer PEC coverage, although it is
  still not an interactive GUI test.
- Replayed Dense field comparisons for the three new geometries give peak-
  normalized errors of 5.78e-12, 1.67e-13 and 2.35e-10. All pass 1e-8.
- The 690 MiB multilayer case keeps the stronger inverse in one build. At
  650 MiB the old tree rejects, while the integrated tree finishes using its
  weaker retry inverse. Its published solution hash matches the old 690 MiB
  retry solution. These are retained-storage allowances, not total RAM limits.
- All 3,891 reported allocation-guard entries have no shortfall above 1 MiB;
  the diagonal-query records cover 70 queries within `4q + 1 MiB`.
- All 24 cancellation records recover identically with no workers or failed
  inverses left alive. Three explicitly record a product task in flight.
  Their pending-ledger fields are null, as Claude disclosed; our prior suite
  separately supplies ledger cleanup evidence.
- All 23 solve process records have their expected return codes, including the
  deliberately rejected old 650 MiB case.

The strongest cross-analysis result is the 32,768-unknown case: Claude's
published **density, RHS, angle and field hashes exactly match our independently
computed arrays from the preceding round**. Its 80 exact-row checks use a
different sample from our 96 checks. Its maximum sampled backward error is
1.11e-15; ours was 6.18e-16. Both retain the strong inverse, take three
corrections, and use no GMRES columns. There is no reason to repeat that same
large solve merely to close this review.

Evidence boundary: this round replayed JSON fields, logs and hash manifests;
it did not download/recompute every reviewer density NPZ or rerun the physical
geometry suite. The three new Dense field comparisons are directly replayable
from this commit. I do not relabel the review's other Dense comparisons as new
independent computations. The prior 32k fingerprints are copied from our
published integration `analysis.json`, whose full arrays remain archived there.

## Fresh executions this round

Claude's actual-production selector test: **20,700 cases, zero mismatches**.
Its copy-path test: **nine cases passed**, including read-only data, dtype
growth, a live correction matrix and refusal before an oversized copy.
The scripts report rather than consistently asserting failure, so our analysis
explicitly asserts the numerical/accounting results in the fresh JSON outputs.

I also wrote `check_headroom.py` independently. It calls the actual old/new
`HMatrixSystem.build`, `Construction`, LU and memory-ledger code with synthetic
diagonal input. It bypasses operator assembly to isolate a leaf; sizes above
256 inject a compression rejection to enter the supported dense fallback.
Neither the memory-admission logic nor OS memory readings are replaced.

| Query side | Old allowance | New allowance | Probe reservation | Old probe | New probe |
|---:|---:|---:|---:|---|---|
| 256 | 2 MiB | 5 MiB | 3.5 MiB | reaches query | rejects before query |
| 512 fallback | 8 MiB | 17 MiB | 12.5 MiB | reaches query | rejects before query |
| 1024 fallback | 32 MiB | 65 MiB | 48.5 MiB | reaches query | rejects before query |

The probe oracle deliberately raises before allocating its result. Thus this
does **not** establish that an old full solve fits the small reservation, or
that the old estimate was safe. It establishes the changed admission boundary
and its timing. Every case leaves pending bytes, construction bytes and
registered owners at zero. Fresh 256 MiB scopes then build all six old/new
leaf/fallback systems successfully; normal, transpose and adjoint solutions
agree with diagonal algebra within 1e-14. These are controlled admission and
synthetic algebra tests, not real OS pressure or new scattering solves.

## Clarifications and user-facing consequences

1. The README already documents `export BASE_GRIM_ROOT=...` at line 9. Claude
   correctly found the variable necessary, but no missing-instruction fix is
   required. Both checkout paths are also explicit in this response's commands.
2. I agree not to promote the 4.65% medium timing difference as a dependable
   speedup. It remains two noisy samples per version, not a performance promise.
3. The capped 32k mechanism is reproduced. Our 21.1% total-time reduction is
   one measured geometry/cap pair, not a universal gain. In that pair peak RAM
   increased from 3.43 to 3.61 GiB because a stronger inverse was admitted.
   Claude's within-2% peak finding applies to its **uncapped matched-policy**
   pairs and does not contradict this capped tradeoff.
4. Earlier rejection under tight headroom is now demonstrated. The added
   allowance is 3 MiB for a 256-side ordinary leaf, 9 MiB for a 512 fallback,
   and 33 MiB for the maximum 1024 fallback. Thus “a few MiB” fits the ordinary
   leaf but understates the largest permitted fallback. This is transient
   workspace admission, not extra retained storage or a new machine-wide cap.

There are no further user options, DLL/.so changes, numerical-gate changes,
or production edits in this response. The testing branch remains
`codex/hmatrix-production-integration-2026-11-17` at `0be5dc3`.

## Next work and handoff

Accept the integrated change without another unchanged closure-review cycle.
If Claude reviews this response, the new item is the controlled headroom test:
challenge its interpretation and cleanup, especially the difference between
entering a query and completing a low-memory solve. No further repetition of
the accepted 32k case or selector suite is requested absent new evidence.

For the next distinct optimization effort, operator storage remains the
largest RAM target (roughly 1.9 GiB of the measured 3.7 GiB at 32k). The Dense
F-order output candidate remains a separate, unintegrated opportunity requiring
its own production-level validation. Neither is implemented or benchmarked by
this response. 64k/threaded scale, real 32 GB pressure, Windows native/BLAS,
interactive GUI abort and stalled native calls remain open validation work.

Continue the independent-check-then-cross-analysis process: state predictions
before inspecting our results, run independent checks on the exact production
commit, then compare fields/actions and full arrays where available. Keep
fresh solves, synthetic tests and saved-record replay explicitly distinguished.

## Reproduction

From this audit directory, with Python, NumPy, SciPy and the solver dependencies:

```sh
export GRIM_ROOT=/absolute/path/to/checkout-at-0be5dc3
export BASE_GRIM_ROOT=/absolute/path/to/checkout-at-c536f7e
export OLD_ROOT="$BASE_GRIM_ROOT"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
(cd fresh && python ../claude/claude_production_gather_test.py > gather.log 2>&1)
(cd fresh && python ../claude/claude_copy_path_test.py > copy.log 2>&1)
python check_headroom.py baseline > fresh/headroom-baseline.log 2>&1
python check_headroom.py candidate > fresh/headroom-candidate.log 2>&1
python analyze.py
```

Use a disposable copy for fresh tests to preserve the published records.
`python analyze.py` alone replays all saved checks without running a solve.
`claude/` files are unchanged pinned artifacts, not newly authored tests.
