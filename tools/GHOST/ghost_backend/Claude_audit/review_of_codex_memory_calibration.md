# Review of Codex's memory calibration round (commit 50d2c64, 2026-10-29)

Reviewed:
- `Claude_audit/codex_memory_calibration_implementation_20261029.md` (the handoff)
- `Codex_audit/claude_followups_review_20261029/`: Codex's review of my last audit, plus the pagefile snapshot
- `Codex_audit/memory_calibration_20261029/`:
  - README, `study_summary.json` and the nine run folders
  - both pressure ramps, with the pagefile before and after
  - the validation summary
- The source diff of `50d2c64` in:
  - `execution/memory.py` and `execution/memory_budget.py`
  - `compressed/runtime.py`
  - `hpc/scheduler.py` and `twod/solver.py`
- The earlier dielectric runs (`memory_implementation_20261029` and `memory_followups_20261029`), for timing comparison

GitHub `main` is at `50d2c64`. I read code and saved results only; I ran no tests or solves.

## Verdict

**The three changes are correct.**

- **Idle tile workers are now closed when a mesh switches to hierarchical assembly.** This is a real, measured saving: peak RAM 2.28 → 1.88 GiB and commit 2.85 → 2.28 GiB on the ordinary inlet, with identical fields.
- **The commit-limit growth logic is safe:** no double counting, and no refunds of memory that is still held.
- **HPC submission forecasts no longer read the submitting PC's RAM.**

Codex's corrections to my last review are right, and I accept them below.

Two findings change what to do next:
1. **The slowdown is the PC, not the code.** In Codex's A/B test, the *old* code took 156.6 s, but the same old commit took 124.0 s when it was first measured. Everything run on your PC since about 11:00 has been about 25% slower, whichever code ran.
2. **The new commit-growth code is unlikely to add capacity on this PC by itself.** Windows didn't grow the pagefile even with commit at 95% of its limit for 10 seconds. The measured way past the 80% ceiling is a pagefile minimum of about 4 GiB or more, which is your call.

## Codex's corrections to my last review: accepted

| My claim | Correction | Position |
|---|---|---|
| Switch to a system-managed pagefile | It already is: system-managed, 2,048 MiB allocated (`pagefile_snapshot.json`) | **Accept.** |
| My commit formula ("free RAM plus pagefile room, minus committed") | Commit headroom is the system commit limit minus current commitment. The limit is roughly RAM plus pagefiles. | **Accept.** |
| Spool writes went from 5 to 11, costing 2.6 → 5.7 s | Those were sampled progress notifications. Actual spool-write calls were 320 in both runs, taking 0.15 vs 0.17 s. | **Accept.** It was a measurement error on my part. |
| "Operators" stage of 65 → 83 s | Stage times are inclusive and overlap, so this is close to hierarchical assembly time rather than an exclusive total | **Accept.** The slowdown conclusion stands; that figure was loosely labelled. |
| Calibrate workers from the saved USS | Those are 16 tail samples, not busy-stage peaks | **Accept.** Codex has now measured busy-stage peaks; see below. |
| "About 22 GiB of storage" | Arithmetic that depends on 28 GiB free and enough commit, not a measured capacity | **Accept.** |

## Implementation checked

| Change | What the code does | OK? |
|---|---|---|
| **Commit-limit growth** | `windows_system_commit()` reads `CommitLimit` and `CommitTotal` via `GetPerformanceInfo`. Only growth of the *limit* (not lower usage elsewhere) raises the group's capacity, once, under the lock, and never above 90% of initial physical RAM. Each request's held reservation is `max(previous, admitted)`, so a shrinking limit or a tighter cap never refunds bytes that may already be allocated. A missing probe never adds capacity. The initial commit is now the smaller of process and system headroom. | Yes |
| **Idle worker release** | `release_obsolete_tile_workers` runs only on a real hierarchical mesh admission (`activate_memory_plan`), never on speculative forecasts. It closes idle teams only; busy teams are kept. The forecast is repriced without the team, and a later tile mesh recreates it through normal admission. | Yes |
| **HPC submission forecasts** | `submission_planning=True` on both scheduler entry points uses the historical 2 GiB payload estimate and never touches the local ledger. It refuses to combine with plan activation. Compute-node admission is unchanged. | Yes |
| Tests | 621 tests and 114 subtests pass across 44 files: the union of both earlier sets plus new ones. This also closes my earlier "391 is not 467" note. | Yes |
| Numerical runs | All nine study runs certify, with zero field difference in every case | Yes |

## Finding 1: the 25% slowdown is the PC, not the code

| Ordinary inlet, 15 GHz, 4 workers | Wall time |
|---|---:|
| `63429ba`, first measured (about 10:30) | 124.0 s |
| `b233c19`, follow-up round | 155.8 s |
| **`63429ba` again, in Codex's A/B** | **156.6 s** (both repeats) |
| `b233c19`, in Codex's A/B | 156.4–157.2 s |
| `50d2c64`, final tight-cap run | 154.8 s |

The same old code that took 124.0 s now takes 156.6 s on the same geometry and settings, with identical numerics. So the code is cleared, as Codex's A/B shows. But the PC itself got about 26% slower some time between the two sessions, and it has stayed that way.

The dielectric inlet shows the same shift: 162.9 s, then 192.0 s, then 193.2 s. Every stage is slower (assembly 82 → 99 s, factorization 49 → 53 s, solve 17 → 24 s). This was not covered by the A/B, but it fits the same pattern.

The sampler explains only about 7 s, and the reported CPU frequency is a fixed 4,700 MHz value, so it doesn't help. Things worth checking on the PC:
- Windows power mode (Balanced vs Best performance)
- Defender real-time scanning of the scratch and snapshot folders
- thermal throttling
- anything left running since about 11:00

If one quiet run of the old commit comes back at about 124 s again, the cause was temporary. **One old-code dielectric run** (about 3 minutes) would also confirm the dielectric slowdown has the same cause. Either needs your go-ahead.

## Finding 2: commit-limit growth won't happen on its own here

During the held ramp:
- System commitment reached **33.81 of 35.54 GB (95.1%) of the commit limit and stayed there for 10 seconds.** The limit never moved, and the pagefile stayed at 2,048 MiB.
- Windows' system-managed pagefile on this PC grew neither at 90% nor at 95%.

Meanwhile, the solver keeps a 10% commit reserve, so it never pushes the system all the way to the limit. The new growth path will only fire if something else on the PC drives commit to the limit. The code is correct, but it doesn't change the 80% ceiling on this PC.

**What would:** at the start of the held ramp, 16.8 GiB of RAM was free, but commit headroom was only 15.0 GiB. Other programs had committed more than they kept resident. The solver's physical limit is 0.9 × 16.8 = 15.1 GiB, and its commit limit is 0.9 × 15.0 = 13.5 GiB. So raising the commit limit by about **2 GiB or more** makes physical RAM the binding limit, which is your 90% goal. In practice that means setting a pagefile minimum of about 4–6 GiB instead of the current 2 GiB system-managed allocation. Costs:
- a few GiB of disk
- no paging, because the solver's live physical-RAM check still caps it at 90% of real RAM

This is an OS setting and your call. Codex rightly didn't change it. If you do it, the next step is the full near-90% numerical solve that's still unqualified.

## Finding 3: worker calibration is now low priority

Busy-stage peaks, measured this round:

| Workers | Peak private commit (all workers) | Allowance | Allowance ÷ measured |
|---:|---:|---:|---:|
| 2 | 0.36 GiB | 0.95 GiB | 2.6x |
| 4 | 0.70 GiB | 1.89 GiB | 2.7x |
| 8 (narrow inlet) | 1.43 GiB | 3.79 GiB | 2.6x |

That's a steady 0.18 GiB per worker against a 0.47 GiB allowance. But since idle workers are now closed on hierarchical meshes, the allowance only applies to the small tile meshes, which are never the memory-binding ones. Reducing it would gain little for large inlets. Codex is right not to reduce it on metal-only evidence, and I'd now leave it.

A side note: 2 workers took 225.7 s against 156 s for 4. The worker count matters a lot for speed, so don't reduce workers to save RAM.

## Minor notes

- The 2 GiB submission payload is the historical value. It only caps the forecast on the tile path; hierarchical forecasts include the full operator and inverse. Fine for now. If large tile-path HPC jobs ever get refused on the node, look here first.
- `stable()` now returns the current admitted value while holding the reservation at its maximum. A factor already built keeps its original cap, which Codex documents. That's fine.

## Recommended order

1. **Check the PC's 25% slowdown** (power mode, Defender exclusions for the scratch folders, background tasks). Optionally run one old-code dielectric run, which needs your go-ahead. Any future timing comparison is unreliable until this is understood.
2. **Your call:** a pagefile minimum of about 4–6 GiB to lift the commit ceiling.
3. Then the full near-90% numerical solve on the 32 GB machine.
4. No further worker-allowance work for now.
