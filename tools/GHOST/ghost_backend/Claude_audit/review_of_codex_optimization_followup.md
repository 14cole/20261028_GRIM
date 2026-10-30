# Review of Codex's construction-efficiency and optimization follow-up (2026-10-30)

Reviewed:
- `Claude_audit/construction_efficiency_implementation_20261029.md`, now **pushed as `6c73ccd`**. I read the diff on GitHub against the version I audited last round.
- `Claude_audit/optimization_followup_implementation_20261029.md`, **local only and not pushed**, plus:
  - `Codex_audit/optimization_followup_20261029/`: README, `summary.json`, `junction_reason.json` and `.py`, `validation_summary.json`, the final test logs, `concurrency.py`
  - `Codex_audit/push_scope_20261029.md`
- The local source on your PC compared with `6c73ccd`:
  - `compressed/worker_pool.py`, `execution/memory_budget.py`, `twod/assembly/polynomial_pair.py`
  - `tests/test_polynomial_pair.py` and the two new test files

I read code and saved results only; I ran no tests or solves this round.

## Verdict

**Both rounds are correct, and the slowdown I measured is now mostly gone.**

| Inlet, 15 GHz, automatic profile | Added time from the construction checks |
|---|---:|
| First version (my A/B last round) | +12.25 s (+12.1%) |
| Pushed `6c73ccd` (Codex's A/B) | +3.74 s (+3.2%) |
| Local follow-up | a further 3.20 s saved against `6c73ccd` |

Combining the last two suggests the remaining overhead is about **0.5–1 s (under 1%)**. That combines two different sessions, so it's an estimate. A single four-run A/B against the original code would confirm it (see "Next steps").

Fields are bit-for-bit identical in every run, memory use is unchanged, and the standing decisions all hold: compressed default, dense and surface impedance as overrides, no forecast discount.

## Round 1, pushed (`6c73ccd`): my findings were addressed

| My finding | What Codex did | OK? |
|---|---|---|
| 1. Live OS check on every small step | A step under 16 MiB can reuse the last live reading for up to 50 ms. In total, reuse can cover at most the smaller of 64 MiB and 1% of the reservation. Reuse is refused when another request overlaps, when another hold is pending, if the caps change, if owned memory grew more than the steps priced, or if idle workers changed. Any registration, plan change or other live check cancels it. Each step still takes a hold under the global lock. | Yes |
| 1b. Second process sample per step | The live check's own sample is reused; the build's entry and exit samples remain | Yes |
| 2. The 64-entry memory report flooded with construction checks | Admitted construction checks are now counted and summarised; refusals and phase and reload checks stay in the list | Yes |
| 3. Reload skip based on size only | A reload is now covered only by an explicit allowance that each reload uses up, and the default is zero. No caller uses it today. | Yes |
| 5. Compare the construction peak too | Adds the ratio of accounted build peak to forecast, labelled as an accounted allowance, not a measured peak | Yes |

I checked the reuse limits for a way to skip a large or growing allocation, and found none:
- Anything 16 MiB or larger always gets a live check.
- Reuse stops once 64 MiB has been reused.
- Retained growth beyond what was priced forces a refresh.

The worst case is about 64 MiB allocated against a reading at most 50 ms old, in a single request. That's an acceptable trade.

## Round 2, local: cheaper worker readings and the junction fix

| Change | What the code does | OK? |
|---|---|---|
| **Cheap worker reading for incremental checks** | Profiling showed 3.5 s spent in full worker-memory scans. Incremental checks now use plain RSS and private commit. RSS is always at least the unique residency, so this only *overcharges*. In this mode workers get no residency credit. Full admissions still use the detailed scan, and platforms without private commit fall back to it. | Yes |
| **Exact recheck before refusing** | If the reservation would refuse *only* because of the conservative worker RSS charge, it retries once with the detailed scan and fresh live limits, and refuses if that still doesn't fit. Other refusal reasons (live RAM, commit, caps) don't trigger the retry, since the worker charge doesn't affect them. Two tests cover acceptance after the recheck and a genuine refusal. | Yes. This prevents the false low-memory refusal you wanted avoided. |
| **Junction projection declined** | The optional quadratic-to-cubic matrix reuse was wrong at combined material junctions. One set of densities replaces the slave endpoint with its master, while the other keeps both, so a single interpolation can't serve both. Codex measured the mismatch as 0.497: algebraic, not roundoff. These layouts now fall back to normal assembly. The option is off by default, and no tolerance changed. | Yes. This explains the "existing failure" left open in round 1 (TE 0.037, TM 0.056 errors). |
| Tests | 184 tests and 27 subtests pass, including exact dense and compressed junction fallback fields | Yes |

**One minor note.** The memory report's last 16 worker samples are now mostly the cheap kind. Their unique-residency field is 0, marked "not eligible for credit". Anyone calibrating worker memory from that list, as we did in an earlier round, needs the full snapshots. Worth one sentence in the report text, or a separate short list of full snapshots. It's not a correctness issue.

## Codex's other results: checked

| Result | My reading |
|---|---|
| Moderate-dielectric dogleg certifies in 366 s at 6.83 GiB, fields identical to before | Consistent with the 371 s earlier. A good qualification. |
| Coated inlet stopped by the 240 s trial timer at 4.2 GiB | Inconclusive, not a failure. Earlier rounds found it fails on conditioning and rank, not RAM, so it needs a longer, separate study. |
| Magnetic dogleg: forecasts of 420 and 838 GiB, then the panel limit | Expected. These forecasts use the largest wavenumber of any medium and ignore loss (my earlier finding), so they overstate. The panel limit stops it either way. The surface-impedance **override** remains the practical route for this material. |
| 2 GiB-cap inlet stopped by the 180 s timer | Inconclusive; it didn't run out of memory |
| Two concurrent solves in one process: 24% faster combined, fields within 4e-15, separate reservations, no reuse during overlap | A solid check of the shared-process ledger. The GUI runs one job at a time, so the speed gain applies to scripts and HPC drivers, not GUI runs. |

## Things to know before the next push

1. **`6c73ccd` went out without a clean full test suite.** Codex says so plainly: the broad run was interrupted and resumed, and stale fixtures were repaired. Two failures were known at the time:
   - the junction projection, now fixed locally
   - the ASCII-source check, which was there before these rounds

   The follow-up's 184 tests are focused only. Run the full suite once on the follow-up before pushing it.
2. **The ASCII-source check** fails on Unicode in existing source and audit files. Codex reverted its encoding edits to keep the original bytes. Either fix the files or narrow the check to production source, so the suite can go green.

## Next steps

1. **Keep both rounds.** Pushing the follow-up is your call, after one clean full-suite run.
2. **Optional: one confirming A/B** against the original pre-check code, using my `Claude_audit\inverse_checks_ab\ab.py` unchanged. It still applies, because its baseline uses the saved pre-check copies of the seven changed modules, which never call the new worker method. Four inlet solves, about 8 minutes, with your go-ahead. It would turn the "under 1%" estimate into a measurement.
3. After that, I agree with Codex: **stop tuning the checks.** The open problems are numerical: conditioning and rank on the coated inlet, and discretization or forecast scaling on the magnetic case, where the impedance override applies.
