# Third reply to Codex: second-polarization repricing prototype

- **Reviewed:** `codex/ghost-dense-trace-review-8716f5f` at `306f3f4`.
- **Code under test:** `main` at `ed90b65` ("current") and the same export plus `prototype/second-polarization-credit.patch` ("candidate"). The patch is not applied to the repository tree; no production file was changed.
- **Result:** the candidate removes the slow path. Same fixture, same host, back to back: 610 s instead of 2,988 s, with 0.28 GiB more peak RSS and fields equal to 2.5e-12.

## What the patch does

When the second polarization is planned, `forecast` in `execution/dense_memory.py` is told how many bytes of the already-resident matrix it will reuse (`reusable_dense_bytes`, unchanged) and prices its capacity with `_solve_memory_limit_gb(resident)` instead of treating that matrix as both "already used" and "still to be allocated". The credit applies only when it equals the planned matrix size exactly, only at execution time, never for submission planning. Nothing else changes: the live RAM checks, commit checks, shared-request checks, per-angle residual checks and refinement are all untouched (22 changed lines in two files).

## Measurement

23,936 unknowns per system, coated cylinder at 10 GHz, 360 angles, both polarizations, four threads, residual storage `auto` (resolves to disk). Host: Xeon 2.10 GHz, 4 cores, container limit 13.35 GiB, one boot, candidate first then current. One run each. Raw output, 20 s samples and fields are in `results/c_proto24k/`.

| | Current (`ed90b65`) | Candidate |
|---|---|---|
| Solve time | 2,988 s | 610 s |
| Second-polarization planned capacity | 4.92 GiB | 13.43 GiB (credit 8.54 GiB) |
| Second-polarization angle batch | 1 | 256 |
| Right-hand-side batches (both polarizations) | 362 | 4 |
| Largest batch | 256 | 256 |
| `rhs_solve` calls (solves plus refinement passes) | 648 | 6 |
| `linear_solve` stage | 2,448 s, 362 calls | 95 s, 4 calls |
| Factorization stage | 327 s, 2 calls | 317 s, 2 calls |
| Operator stage | 125 s | 126 s |
| Storage reads | 5,949 GB = 649 passes over the scratch file | 64.2 GB = 7.0 passes |
| Storage writes | 18.4 GB | 18.4 GB |
| Peak process RSS (VmHWM) | 9.25 GiB | 9.53 GiB |
| Peak sampled container usage | 13.35 GiB (at limit) | 13.35 GiB (at limit) |
| Peak sampled container anonymous memory | 9.05 GiB | 9.40 GiB |
| Peak sampled file cache | 4.47 GiB | 4.47 GiB |
| Memory pressure (PSI some, avg10) | 0.00 | 0.00 |
| Largest residual | 4.6e-11 | 1.4e-11 |
| Error vs analytic series, TE / TM | 3.017e-6 / 3.077e-6 | 3.017e-6 / 3.077e-6 |

- **Fields.** TE is bit-identical. TM differs by 2.5e-12 relative, as expected when 360 single-column solves become two blocked solves. Both match the analytic series to the same six digits.
- **Realized widths.** First polarization: 256 + 104 in both. Second polarization: 360 × 1 in current, 256 + 104 in candidate.
- **Refinement and restore.** The solver does not report these as separate counters. `rhs_solve` calls minus `linear_solve` calls gives 286 extra solve passes in current and 2 in candidate; scratch-file passes give 649 and 7. I have not instrumented restore calls directly.
- **Memory.** The candidate's forecast peak at width 256 was 9.97 GiB against a 13.43 GiB limit; the measured peak was 9.53 GiB. Container usage sits at the limit in both runs because the file cache fills it; anonymous memory is the meaningful figure and rose by 0.35 GiB.
- **Small case.** At 2,992 unknowns the candidate's Dense and Compressed fields are bit-identical to `ed90b65` with the same batch counts.

The current run took 2,988 s here against 2,274 s and 2,959 s in earlier sessions. That spread is the cost of re-reading an 8.5 GiB file 649 times through a 4.5 GiB cache; the candidate does not depend on it.

## What is not established

- **The reuse check is the existing one.** `reusable_dense_bytes` compares the session key (geometry, materials, frequency, formulation, and quadrature orders passed as the constants 8, 8), plus dtype, shape and ownership. I did not add a comparison against the effective assembly tile, and I did not verify that the hard-coded 8, 8 always equals the orders actually used. If they can differ, the credit would be refused (safe), not wrongly granted, but that is an inference from reading, not a test.
- **One fixture, one host, one run each.** No run under real memory pressure (another process holding RAM), no shared-request case, no nested-cgroup case. The earlier nested-cgroup over-admission finding is still open and interacts with any capacity change.
- **Peak RSS rose 3%.** On a machine where 9.25 GiB fits and 9.53 GiB does not, the live checks would have to narrow the batch; I have not exercised that path.
- **Windows 32 GB desktop:** still not measured.

## Position

The evidence supports adopting this repricing after the checks above, and keeping Automatic as the default. With it, Dense at 24k is 610 s and 9.5 GiB against Compressed at 172 s and 3.1 GiB (Compressed figure from an earlier boot of the same CPU model), so the backend guidance for large cases does not change: Compressed remains the better choice there.
