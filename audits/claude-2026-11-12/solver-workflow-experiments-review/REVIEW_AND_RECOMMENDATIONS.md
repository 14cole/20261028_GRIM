# Solver workflow experiments: review of Codex's study, my own investigation, and what I would pursue

- **Reviewed:** `codex/solver-workflow-experiments-2026-11-12` at `b3c6b7c`, `audits/codex-2026-11-12/solver-workflow-experiments/HANDOFF_SOLVER_WORKFLOW_EXPERIMENTS.md`.
- **Runtime measured:** `cfe005a` (current candidate production code). No production code changed by Codex or by me.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13. Timings in this batch are single runs on a host that ran slower than in earlier rounds; I rely on ratios and stage shares, not absolute seconds.
- **Constraint from the project owner:** symmetry-based methods are out of scope, because symmetric geometry is too rare in practice.

## Recommendation in one paragraph

Pursue, in this order: (1) fix a scale-dependent accuracy loss in Compressed that I measured growing to 2e-5; (2) finish the already-agreed Automatic lean-Dense planning fix; (3) cut the Python overhead in Compressed assembly, which is where large solves spend most of their time; (4) parallelise the Compressed inverse build and solve, which run on one thread; (5) investigate reuse across a frequency sweep, which neither of us has measured. I would not pursue symmetry, out-of-core LU, lossless spool compression, single-precision inverse storage or Dense mixed precision.

## My investigation

### Finding A: Compressed accuracy depends on the physical scale of the model

Codex noticed that a dielectric case rescaled to the same electrical size gave a slightly different Compressed answer. I mapped it. One dielectric circle, 4,000 unknowns, electrical size fixed (k0 × radius = 100), solved at six physical scales. "Difference" is the largest Compressed-minus-Dense amplitude divided by the largest Dense amplitude, over all 38 values.

| Radius | Frequency | k0 (1/m) | Compressed against Dense |
|---|---|---|---|
| 100 m | 0.048 GHz | 1 | 4.7e-12 |
| 10 m | 0.48 GHz | 10 | 3.2e-11 |
| 1 m | 4.8 GHz | 100 | 5.2e-9 |
| 0.2 m | 24 GHz | 500 | 1.3e-7 |
| 0.05 m | 95 GHz | 2,000 | 8.7e-7 |
| 0.01 m | 477 GHz | 10,000 | 2.1e-5 |

These are the same mathematical problem. Dense gives the same answer at every scale (1.6e-11 between the 1 m and 0.05 m runs after the expected amplitude scaling). Compressed loses roughly a factor of 1,000 in agreement for every factor of 100 in wavenumber. A PEC-backed coating shows the same direction: 2.0e-9 at 1 m, 4.1e-8 at 0.05 m.

Why it matters:

- At 10 to 18 GHz with geometry in metres, k0 is 200 to 380 per metre. That puts ordinary Compressed dielectric and coated runs in the 1e-8 to 1e-6 band, which is what both of us have been recording (1.39e-6 on the coated circle).
- Every discrete quality gate passed in every run, so the gates do not see it.
- The first row shows the method itself reaches 5e-12. The loss is a scaling artefact, not a limit of compression.

Likely cause, not proven: the operator blocks have different physical dimensions (the single-layer block scales with length, the hypersingular block with one over length), so a tolerance relative to one overall norm under-resolves the smaller block as the model shrinks. Codex's observation that tightening the operator tolerance from 1e-12 to 1e-14 restores agreement fits that.

Suggested work: make the compression scale-invariant, either by solving in units where the wavenumber is of order one or by equilibrating the blocks before the tolerance is applied. The acceptance test is simple: the table above should become flat near 1e-11. This is the cheapest item on the list and the only one that improves accuracy.

### Finding B: where Compressed spends its time

Stack sampling every 5 ms over all Python threads, default threading, with the solver's own stage timers.

| Case | Unknowns | Wall | Assembly | Inverse build | Condition | Solve |
|---|---|---|---|---|---|---|
| PEC circle | 8,000 | 41 s | 23.5 s (57%) | 9.2 s | 3.9 s | 3.0 s |
| Coated circle | 6,480 | 54 s | 30.5 s (56%) | 14.1 s | 6.9 s | 4.4 s |
| Airfoil 6 GHz | 17,120 | 117 s | 87.8 s (75%) | 12.1 s | 6.6 s | 5.5 s |

Two separate limits show up.

**Assembly is held back by Python around small native calls.** On one thread, the native far-field kernel accounts for 38% of the samples in the PEC case; the rest is Python and NumPy bookkeeping around it. That is why assembly speeds up only 2.1 times from one to four threads (51 s to 24 s), where Dense assembly speeds up 2.9 times (47 s to 16 s). On the airfoil the largest single item is not a kernel at all: 11% of all samples are in a `numpy.unique` call made each time a scatter object is constructed, and about 6% are in process-table scans made by the live memory checks.

**The inverse build, condition estimate and solve run on one thread.** With default settings 35 to 38% of wall time has exactly one active Python thread on the two circle cases, and two thirds of that is inverse construction (block compression and QR) and triangular solves. BLAS is deliberately held to one thread there, which was the right fix for small blocks, but nothing else supplies parallelism.

Related caution: an explicit numeric BLAS thread count still hurts Compressed badly. With `blas_threads=4` the PEC solve phase went from 4.3 s (one thread) to 16 s, and the whole run was slower at four threads (60 s) than at two (49 s). The default `auto` setting avoids this. A user who sets the number by hand does not.

### What Dense looks like, for comparison

PEC circle, 8,000 unknowns, four threads: assembly 13.6 s, LU 11.7 s, solves about 6 s. Assembly is dominated by the native kernel and scatter, and LU is LAPACK. I see no comparable overhead to remove; Dense is close to what this hardware can do.

## Review of Codex's study

I did not rerun Codex's 119 workflow attempts or 17 factor benchmarks. I read the handoff and scripts and reproduced one item, the scale sensitivity, which my table above extends. My assessment of each candidate:

| Codex item | My view | Reason |
|---|---|---|
| Symmetry and reduced assembly (its top item) | Do not pursue | Out of scope by decision; the gains are real but apply only to rotationally symmetric bodies |
| Automatic storage-plan fix | Pursue | Already confirmed by both sides; small, removes a selection inconsistency |
| Scale-aware compression error budget (its question 8) | Pursue first | See Finding A; Codex found the symptom, the effect is larger than it reported |
| Single-precision inverse storage | Do not pursue now | Codex's own result: about 3% memory, no speed gain, because the operator and construction workspace dominate |
| Schur reuse across polarizations (single dielectric) | Low priority | 15% faster in one run, more memory, one formulation only, needs a full-LU fallback |
| Out-of-core LU | Do not pursue | Eight to ten times slower in Codex's factor tests, needs disk assembly and a second platform implementation; Compressed already covers that size range in a fraction of the memory |
| Lossless residual compression | Do not pursue | Slower on local disk, small gain on irregular geometry (71 to 73% of original size), adds a dependency |
| Dense mixed precision | Do not pursue | Codex's clean repeats show it slower after refinement |
| Looser Compressed preconditioner | Do not pursue | Triggered a rebuild and used more memory |
| Directional or multilevel compression | Long-term only | Correct direction for very large electrical size, but an architectural project |

Codex's handling of its own negative results is good: it kept the slow first runs, the refusals and the cases where a tempting change lost. Its warning that a slow first Dense run would have produced a false speed-up claim for mixed precision is the kind of control these comparisons need.

Two points where I would be more cautious than the handoff:

- The Fourier timings (35 s against 70 s on the PEC circle) come from three runs with ranges that overlap the comparison's range in places. That no longer matters given the scope decision, but the same host variability applies to the Schur and tile comparisons, which are single runs.
- The disk-LU result is presented as a capacity route. With a refined 8,000-unknown factor test taking 150 s against 19 s, and the matrix pair needing 75 GiB of disk at 50,000 unknowns, I do not think it is a practical route while Compressed exists.

## What I would pursue, with expected value

1. **Scale-invariant compression (accuracy).** Small change, clear acceptance test, removes a 1e-6 class disagreement between the two backends on ordinary models. It should come before any further rank or precision reduction, since those would be tuned against a moving error floor.
2. **Automatic lean-Dense planning.** Agreed in the last two rounds; price the lean plan whenever the in-memory plan misses the headroom and carry the chosen plan into execution.
3. **Compressed assembly overhead (speed, large problems).** Assembly is 56 to 75% of Compressed wall time and most of it is not the kernel. Concretely: fetch more coefficients per native call so the Python loop runs less often; build scatter index maps once per tile shape instead of calling `numpy.unique` each time; rate-limit the process-table scan in live memory checks. On this host I would expect assembly to approach Dense's thread scaling, which would take roughly a quarter off large Compressed runs; on machines with more cores the gain grows. This is an estimate from stage shares, not a measurement of a prototype.
4. **Parallel inverse build and solve (speed).** Sibling blocks of the inverse tree are independent, and 20 to 25% of wall time is spent there on one thread. Either build siblings in parallel or let BLAS use threads on blocks above a size threshold. Also apply the one-thread BLAS policy for small blocks when the user gives a numeric thread count.
5. **Frequency-sweep reuse (unmeasured).** Real runs are sweeps. Cluster trees, near-pair lists, quadrature geometry and the adaptive mesh decision do not change between neighbouring frequencies, and a neighbouring frequency's inverse may serve as a preconditioner. Neither study measured any of this. I would start with a measurement of how much of a second frequency's time is recomputing frequency-independent data.

Items 3 and 4 are speed only and do not change results beyond rounding. Item 1 changes Compressed results at the 1e-6 level, in the direction of Dense.

## Limits of my part

- Finding A is measured on two formulations (single dielectric, PEC-backed coating), one size, 19 angles. The cause is a hypothesis. PEC was not scanned across scale; at 1 m it agrees with Dense to 3e-12.
- Finding B is a sampling profile. It shows where threads are, not how much a rewrite would save.
- No prototype of any fix was built.
- Windows, larger hosts, sweeps and certified workflows were not run.

## Reproduction

```
cd audits/claude-2026-11-12/solver-workflow-experiments-review
ROOT=<checkout of cfe005a>
# scale scan (one line per scale and backend)
python sample_solve.py $ROOT '{"body":"diel","n":2000,"mode":"compressed","radius":0.05,"angles":19,"sample":false,"out":"c.npy"}'
python sample_solve.py $ROOT '{"body":"diel","n":2000,"mode":"dense","radius":0.05,"angles":19,"sample":false,"out":"d.npy"}'
# profile
python sample_solve.py $ROOT '{"body":"pec","n":8000,"mode":"compressed"}'
python run_opt.py $ROOT opt.jsonl
```

`fields/` holds the complete complex field arrays for every scale-scan run, so the differences in Finding A can be recomputed. `opt.jsonl` has the thread-count runs, `opt2.jsonl` the default-thread profiles with the single-thread breakdown, `opt_scale.jsonl` the extra scale points.
