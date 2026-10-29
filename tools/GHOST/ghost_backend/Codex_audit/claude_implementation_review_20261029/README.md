# Review of Claude's implementation audit — 29 October 2026

Claude identifies useful remaining work, but its conclusion that all accounting issues are fixed is too broad, and its concurrency finding is more important than described. I reproduced the reload problem and a duplicate-credit counterexample using the current implementation. Correct these before relaxing the retained-storage allowance.

Reviewed [Claude's report](../../Claude_audit/review_of_codex_memory_implementation.md), the source and saved evidence for commit `63429ba0cf5d20f49324675e0cdc4b61588f9cfc`. Local HEAD and GitHub `main` both resolve to that commit. The report's statement that everything is uncommitted at `5460aa2` is stale. This review makes no production changes and performs no commit or push.

## Confirmed: the earlier fixes remain useful

The original shrinking-constructor allowance is fixed. Payload budgets stayed constant in the three recorded large trials; numerical and mesh certification passed, and their fields matched the references exactly. Known-zero handling, the local available-RAM scheduling policy, disk/resident distinctions, per-frequency batch reset and bounded telemetry are present in the source.

The 467-test evidence is valid for its tested cases; it does not cover the counterexamples below. The recorded timings and RAM peaks do not show an obvious large regression, but they are not a controlled proof of no performance regression. The implementation report already discloses overlapping host regression work during portions of the trials.

## 1. Shared-process residency credit can be spent twice — fix before larger allowances

Claude correctly observes that `stable()` calls other requests' `owned()` while holding the global reservation lock, and that those calls mutate their telemetry. However, calling this cosmetic or telemetry-only understates the problem.

`owned()` bounds each request's tracked numeric bytes by **the same process-wide RSS growth**, measured relative to that request's baseline. It does not partition that growth among requests. If two requests overlap, both can receive credit for the same increase. Numeric byte counts do not guarantee every page is resident; paging or not-yet-resident arrays make this distinction consequential.

The deterministic counterexample uses actual accounting code and synthetic observations:

| Quantity | GiB |
|---|---:|
| Initially available RAM | 24.0 |
| Initial 90% target | 21.6 |
| First two reservations | 12.0 and 9.6 |
| First two tracked numeric payloads | 10.0 and 9.0 |
| **Combined observed process RSS growth** | **10.0** |
| Credit assigned to the two requests | **10.0 and 9.0** |
| Third reservation admitted afterward | 9.0 |
| **Sum of three reservations** | **30.6** |

The static caps do not solve this: their sum was admitted using duplicate credit. This can understate outstanding memory commitments and permit oversubscription. It is a same-process overlapping-request problem, not a demonstrated failure of the separately reserved frequency-worker processes. The test does not allocate these GiB or demonstrate an actual out-of-memory event.

Using cached credit, as Claude suggests, avoids cross-thread sampling side effects but **does not fix credit attribution**. Stale cached credit can also outlive residency. Use a synchronized process-level credit pool that cannot assign the same observed growth twice, conservatively withhold ambiguous credit for overlapping requests, or isolate requests in separately measured worker processes. Sampling/reporting should not mutate another request during reservation calculations. Add adversarial overlap, paging/partial-residency and stale-sample tests.

## 2. Reload accounting still produces false refusals — confirmed

`admit_reload()` computes `max(process RSS, private commit) + reload payload + workspace`, then compares that whole quantity through `limit()`, which credits only registered ownership against remaining availability. This charges untracked existing memory again and mixes physical RAM with private commitment.

Reproduction with the temporary workspace explicitly zeroed to isolate the accounting:

- Initial available RAM: 20 GiB; stable reservation: 18 GiB; initial headroom reserve: 2 GiB.
- Existing process baseline: 4 GiB; later registered payload: 4 GiB; current process RSS: 8 GiB.
- Current availability after other applications consume memory: 6 GiB.
- Reload needs another 2 GiB. It fits the 4 GiB live headroom, and the resulting 10 GiB total fits the stable 18 GiB reservation.
- Current code nevertheless refuses: **10 GiB required versus an 8 GiB live total limit**.

A separate probe uses 1 GiB RSS, 10 GiB private commit and plentiful commit capacity. A 1 GiB reload is refused against 6 GiB physical headroom because the code compares **11 GiB of commitment-based total** with the physical-RAM limit. Actual current RSS plus reload would be 2 GiB.

For reloads, test the additional payload and workspace directly against current physical and commitment headroom, each in its own units and domain. Check the appropriate total separately against explicit/stable reservations. Keep spool cleanup, cancellation, per-tile checks and the retained-storage cap.

The same distinction matters for phase forecasts. A controlled phase case with 4 GiB tracked payload, 0.5 GiB already-resident baseline, an 8.3 GiB total forecast and 4 GiB live headroom also refuses, although the modeled additional need is only 3.8 GiB. This does **not** justify subtracting the entire forecast overhead: geometry, cache capacity and workspace may still need to grow. Credit only the matching component demonstrably already present. Claude's quoted GUI baseline range is not a measurement from these trials.

## 3. Workspace-based storage sizing is sensible, with two corrections

The fixed 60% payload share can prevent otherwise feasible storage-heavy problems from using the full reservation. That is a useful next capacity improvement. It has not been demonstrated to be the dominant limit for all large geometries: the recorded runs had ample headroom, and rank, workspace and numerical behavior vary by geometry and material.

First, the saved inlet's solve-phase **non-storage allowance is 3.145 GiB**, not 1.5–2.5 GiB. It includes the non-overlapping process/geometry/worker allowance, angle workspace, GMRES and projection cache. Factorization's corresponding allowance is about 2.601 GiB after subtracting the retained inverse from its construction peak. These are forecasts, not measured component residency, and must not be reused as constants for larger geometries.

Second, **do not make 60% an unconditional floor**. With a 10 GiB total budget and 6 GiB workspace requirement, only 4 GiB remains for payload. A 60% floor grants 6 GiB payload and produces a 12 GiB total. A fallback policy when a reliable workspace forecast is unavailable is different from a floor that overrides a known requirement.

Derive allowances from each actual phase's non-overlapping live set, including old/new factor overlap and retained partners/workers. Assembly, construction, reload and solving need separate envelopes. Preserve user caps, scheduler reservations and current-pressure checks. Where components are uncertain, retain conservative allowances; do not subtract overlapping fields or assume all workspace exists at once. This also avoids promising a fixed amount of reclaimed RAM on every 32 GiB machine.

## Recommended order

1. Correct shared-process residency attribution and synchronized reservation bookkeeping. It affects safety; caching another request's last credit alone is insufficient.
2. Separate additional physical allocation, additional commitment and total reservation checks for reloads and later phases. Add the demonstrated false-refusal regressions.
3. Introduce phase/workspace-based payload sizing, with no floor that can exceed the remaining reservation.
4. Validate bounded near-capacity and concurrent-request cases, followed by real near-90% physical-availability trials on the target machine. Profile worker components before reducing their future-growth allowances.

The fixes already delivered remain valuable. The conclusion is that the **initial storage-budget defect is fixed, while consistent near-limit accounting still needs these follow-ups**. Neither the old nor the new evidence establishes that arbitrary large geometries or concurrent jobs can reliably use 90% of physical availability yet.

## Evidence and scope

[verify_review.py](verify_review.py) exercises the real admission methods with patched probes and synthetic ownership counts. [verification.json](verification.json) records the counterexamples, forecast arithmetic and reviewed-file hashes. All implementation source hashes match the pushed version. These are allocation-free accounting tests, not new large solves, threaded stress tests or physical-RAM exhaustion experiments. Existing production code and historical numerical evidence were preserved.
