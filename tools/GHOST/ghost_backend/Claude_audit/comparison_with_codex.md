# Claude vs Codex: 2D factorization audits compared

Date: 2026-10-29
Compared: `Claude_audit/2d_factorization_audit.md` and `Codex_audit/2d_factorization_audit.md` (with `Codex_audit/size_forecasts.json`).

## Short version

The two audits agree on the answer: dense saves seconds, not minutes (largest saving 14.5 s in both), the gain is about problem size rather than frequency, `hierarchical` and `auto` should go as user choices, and dense and compressed should stay. They differ mainly on the 12 ft compressed memory and on how far to simplify the automatic selection. On the 12 ft memory, Codex's numbers are the safer planning basis, because they are what the solver itself will enforce.

## Where they agree

| Point | Claude | Codex |
| --- | --- | --- |
| Largest dense saving on one solve | 14.5 s | 14.5 s |
| Dense advantage tied to size, not frequency | Yes; dense wins at all 10 GHz on adaptive mesh | Yes; same observation |
| Dense faster on adaptive mesh | 60 of 60 | 60 of 60 |
| Compressed only mode to finish | 64 cases | 64 cases |
| Drop `hierarchical` as an option, keep its code | Yes | Yes (keep forced access as a diagnostic) |
| Drop `auto` | Yes; never fastest | Yes; never fastest |
| Keep dense and compressed | Yes | Yes |
| No validated reference in the trial | Yes | Yes |
| Dense RAM for 12 ft at 10 GHz | about 410 GiB | 415 GiB |
| 12 ft unknowns at 1 GHz, adaptive | about 13,000 (estimated) | 13,618 (forecast) |

## Where they differ

| Topic | Claude | Codex | Assessment |
| --- | --- | --- | --- |
| 12 ft compressed RAM | Fit to measured RSS: about 4 GB at 3 GHz, 14 GB at 10 GHz | Planner forecast: 13.6 GiB at 3 GHz, 132 GiB at 10 GHz | Real value is likely between them. The forecast ran 1.5x to 3x above measured RSS in the trial, but it assumes rank growth that my fit cannot see. Plan with Codex's numbers, since they decide admission. My audit now shows both. |
| 12 ft time | Gives estimates (compressed 13 to 25 min, dense LU 14 h at 10 GHz) | Declines to estimate time; says near-linear extrapolation is not supported | Codex is more cautious. My times are order-of-magnitude only. |
| Sweep total | 84 s saved by dense over a whole 1 to 10 GHz adaptive sweep | Not computed; gives a 100-job arithmetic example (about 17 min) | Both framings are fair. Batch or optimisation work is where the seconds add up. |
| `adaptive` selection | Keep as the one automatic choice but simplify to a size-and-memory rule; names the 826 lines of planning code | Keep it as "Automatic" unchanged; says upkeep savings are not shown | Codex is more cautious about removing code without a broader test set. I would still simplify, but only after Codex's step 4 (converged references across PEC, dielectric, mixed and thin-gap cases). |
| Compressed failures | 4 cases on its own limits: 2 rank-limit errors plus 2 retained-storage-cap refusals | 2 rank-limit failures | Codex missed the 2 storage-cap cases at 8 GHz P2, which are recorded as memory errors. |
| Forecast quality | Flags compressed's forecast as too conservative (20 refusals at 8.2 to 12.8 GiB while similar cases measured 5 to 6 GB), and one case that went over budget (10.2 GB) | Not discussed | A point only in my audit, and it matters for 12 ft. |
| `dense` mislabelled above 10,000 unknowns | Notes "dense" trial timings above 10,000 unknowns are HODLR, not LU | Notes dense can use hierarchical internally | Same fact; mine ties it to how to read the data. |
| Interface | Two modes plus automatic | One Automatic default, Dense and Compressed as advanced overrides, keep old names as aliases | Effectively the same. Codex's alias and migration step is a good addition. |

## Combined recommendation

1. Expose one Automatic choice, with Dense and Compressed as advanced overrides. Map `hierarchical` and `auto` to aliases so saved configurations still load.
2. Keep dense: it is the only cross-check compressed has, and it is the fast path below about 6,000 unknowns.
3. Lower the automatic LU to HODLR switch from 10,000 to about 6,000 unknowns, to keep `hierarchical`'s few seconds of gain without the mode.
4. For 12 ft work, spend the effort on compressed: the rank limit (133), the retained-storage cap, and a better memory forecast. Then run one feasible 12 ft case (1 GHz adaptive fits both backends) to replace both audits' extrapolations with a measurement.
5. Only simplify the planning code after converged references exist for a few representative geometries.
