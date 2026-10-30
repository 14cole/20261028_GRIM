# Review of Codex's impedance follow-up implementation (2026-10-29)

Reviewed:
- `Claude_audit/impedance_followup_implementation_20261029.md` (the handoff)
- `Codex_audit/claude_impedance_review_20261029/`: Codex's review of my last report
- `Codex_audit/impedance_followups_20261029/`: README, `summary.json`, `validation_summary.json`, `pilot.py`, and the seven run folders (results and pilot records)
- The working-tree source on your PC, compared with GitHub `743d639`:
  - the new `execution/failure.py`
  - the changed `execution/cpu.py` and `twod/adaptivity.py`
  - `tests/test_failure_evidence.py` and the changed `tests/test_experimental_cpu.py`

**Not on GitHub yet:** `main` is still `743d639`. I read code and saved results only; I ran no tests or solves.

## Verdict

**Both production changes are correct and safe to keep.** They are the two diagnostics I suggested:
1. **Adaptive rejection reasons now survive.** A refused or failed fallback now says why each earlier mesh was rejected. This already paid off (see below).
2. **Compressed numerical failures now include a dense-override estimate for the mesh that failed**, stating whether it fits. It's information only: no dense solve and no automatic switch, so your "compressed default, dense as override" rule holds.

**Codex was right not to enable the memory pilot.** It under-predicted a held-out case by 7.5%, and it doesn't address the inverse, which is the larger term.

The surface-impedance solver remains an explicit override only; nothing here changes that.

## Codex's corrections to my last report: accepted

| My claim | Correction | Position |
|---|---|---|
| The tile path's sampled forecast was exact (1.0×) | That run reused the already-assembled partner operator's real size (`assembled_partner_payload`, `sampled: false`). It wasn't a sample. | **Accept.** This was my error, and it was the main evidence I gave for the sampling idea. |
| The 2–7× ratios imply the 2 GHz run would fit | Those are storage components, not total RAM, and retained inverse size isn't the construction peak | **Accept.** |
| The 2 GHz refusal is the same matrix at a slightly higher frequency | The refused fallback had 85,462 unknowns against 24,048 at 1.5 GHz | **Accept.** The new trace shows the full chain; see below. |
| A 25-second reproducer | The failing run takes about 147 s; the 23 s was the dense check on a *smaller* mesh | **Accept.** |

## Implementation checked

| Change | What the code does | OK? |
|---|---|---|
| `failure.attach` and `adaptive_failure` | Adds structured records to `exc.solver_diagnostics` and a JSON note through Python 3.11 `add_note`. Earlier reasons are added to the message, shortened to 500 characters with the dense advice stripped. It keeps the exception's type and cause. | Yes |
| `adaptivity.py` | Wraps the conservative retry, the reference fallback and the ineligible-geometry fallback. Records failed steps. Skips `InterruptedError`, which is how GHOST cancels everywhere I checked (`cpu.py`, `session.py`, `solver.py`), so cancelling still behaves normally. | Yes |
| `failure.dense_advisory` | Prices a dense solve of the current failed mesh with `_estimate_memory_gb`. It doesn't activate a memory plan, so the current plan is unchanged, and it allocates no dense matrix. It uses a fresh angle-batch scope and subtracts the failed run's retained worker allowance. If the estimate itself fails, it records "unavailable" and the original numerical error is raised unchanged. Only runs when compressed is active. | Yes |
| `cpu.py` | Routes the six decorated call sites through `failure.invoke`. Nested calls add the advice only once. | Yes |
| Concurrency test fix | Each simultaneous job now reserves 1 GiB. Before, two uncapped jobs could race for the whole cohort, which is correct behaviour since `b233c19`, so the old test was wrong. | Yes |
| Tests | 158 tests and 39 subtests pass across 13 files | Yes |

**One minor note.** The message text is extended by rewriting `exc.args[0]`. For an `OSError` built with errno and filename, `str()` ignores `args`, so the extra text disappears from the message. The structured record and traceback note are still there. This is cosmetic: the spool code raises single-argument `OSError`s, so it doesn't happen today.

**Wording not yet seen in a real run.** The saved real-run messages predate Codex's final shortening, and they still repeat the dense advice and the "Review the saved RAM budget" sentence. The final wording is covered by tests only. The next real failure will show whether the message is now readable.

## What the new trace reveals about 2 GHz

The full-material dogleg at 2 GHz, under the 12 GiB cap:
1. The quadratic mesh **completed**.
2. The cubic check was refused at a **13.28 GiB** forecast (32,052 unknowns), only **10.7% over** the cap.
3. The conservative retry was refused at 17.46 GiB (42,708 unknowns).
4. The linear reference was refused at 33.57 GiB (85,462 unknowns).

A 16 GiB cap didn't help, because Windows commit headroom limited it to about 12.15 GiB.

So this case is not "33.6 GiB needed". The first refusal came within 11% of fitting, and every later step forecast a *bigger* mesh than the one that came within 11%. Once the cubic step is refused, escalating to finer meshes can only make it worse.

## Improvements

### 1. Correct the next mesh's forecast from the mesh this run just measured

This is the safest way to reduce over-forecasting without a pilot or any history across runs. When the adaptive path has just **completed** the quadratic mesh in the same request, it has measured that mesh's actual operator and inverse sizes next to their forecasts. On the material runs so far, the hierarchical model over-forecast storage by 2.4–3.7× for the operator and 4.7–7.5× for the inverse.

The proposal:
- Scale the cubic forecast's storage terms by the quadratic mesh's measured ÷ forecast ratio. That ratio is capped at 1, so the forecast can only shrink, and it gets a safety margin such as ×1.5.
- Leave the workspace terms unchanged.
- Apply it only within the request. Nothing is kept between runs, which matches the rule against a persistent learned history.

At 2 GHz, the cubic forecast only needed to drop by 11%. Even a heavily margined correction would very likely have admitted it, but that is an estimate until it runs.

**Prerequisite, and worth checking first:** admitting on a lower forecast is only safe if hierarchical inverse *construction* is bounded while it runs, not just checked before it starts. `admit_phase('factorization')` checks the forecast before construction. `CompressedFactor` caps the *retained* inverse. If construction can overshoot its forecast before either check fires, an optimistic admission could run out of memory instead of being refused. Codex's own note (an inverse-construction live set of about 19.5 GiB on the linear fallback) suggests construction is the term to watch.

### 2. If the pilot is revisited, use it only when it predicts a large reduction

The pilot's results split cleanly:

| Case | Pilot ÷ geometry forecast | Pilot vs actual |
|---|---:|---|
| Magnetic, 12,036 unknowns | 0.59 | over by 40% (safe) |
| Magnetic, 16,032 unknowns | 0.51 | over by 49% (safe) |
| Magnetic, 24,048 unknowns | 0.94 | over by 3.5× (safe) |
| Moderate dielectric and low loss, 9,584–14,376 unknowns | 0.92–0.93 | **under by up to 7.5%** |

Every unsafe case was one where the pilot found only a small (7–8%) reduction. A rule like "use the pilot only if it predicts at most 0.6× the geometry forecast, otherwise keep the geometry forecast" would have avoided all of them and kept the magnetic gains. That costs nothing in the mild cases, where the gain is tiny anyway.

I picked that threshold after seeing the data, so it needs a fresh held-out set before use, as Codex insists. Improvement 1 is still the better first step: it uses this run's own measurement and also covers the inverse.

### 3. Stop escalating to a finer mesh after a memory refusal

When the cubic mesh is refused for **memory**, the next steps (conservative retry, then the linear reference) are by construction larger meshes. They are certain to be refused too, and they took about 57 s here. Numerical rejections can still escalate as now, but a memory refusal of the smaller candidate could end the request immediately. The error would then lead with the closest miss (13.28 vs 12.00 GiB) instead of 33.57 GiB, which tells you what is actually needed.

### 4. Keep the dense advice for the user

The small magnetic reproducer now says the dense override fits (10.42 vs 11.87 GiB). That's exactly the actionable message intended. Codex's correction stands: that failed mesh is larger than the one the 23 s dense run solved, so a dense retry is likely to fit but not certain to be fast.

## Recommended order

1. **Commit and push** the two diagnostic changes (your call). They're correct and covered by tests.
2. **Check that hierarchical inverse construction is memory-bounded** (the prerequisite above). It's a read-and-test task, with no large solves needed.
3. If it is, implement **improvement 1**, plus **3**, which is small. Then retry the full-size 2 GHz bulk run (one solve, about 2–5 minutes, with your go-ahead).
4. Park the pilot unless improvement 1 proves insufficient.
