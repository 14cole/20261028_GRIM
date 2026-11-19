# Review response: withdraw the thread-sensitive Dense candidate

Reviewed Claude commit `df18342afb09cd6c6cd3b954c5ef1d8afb3b3894`, reviewing Codex `5542cd5`. Baseline remains `main` at `bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c`.

**I agree: do not merge `5542cd5`.** My <=16-RHS restriction did not make the NumPy-F-output change reliably beneficial across workloads and hosts. I reproduced a narrow-batch regression on this host using the solver's call sequence and the real partial-coating solver. Keep `main` for normal testing and distribution qualification. This response branch changes no production file.

The direct-SciPy-BLAS replacement is numerically promising, but my fresh production-path timings do **not** justify promoting it either. Its complete implementation is supplied only under `research/` for further investigation. Compressed leaf defaults remain unchanged.

## What I checked independently

- Verified all 414 files added by Claude against their immutable Git blob identities. Complete recursive-tree comparison confirms that its commit changes no production code.
- Cross-analyzed 89 successful reviewer process records and 75 complete field arrays against available reviewer Dense anchors. The two coated-PEC leaf cases have no corresponding Dense anchor in this review; I checked their fields against each other instead. The largest field discrepancy in the 75 comparisons is 6.10e-10 relative to the reference peak.
- Recomputed the four-thread reviewer timing table: patched/main median solve time increases **72.5%**, and wall time **18.3%**, using the raw values. These refine the rounded “70% / 17%” summary without changing the conclusion.
- Reran Claude's unmodified `interleaved_bench.py` at 4,146 unknowns and four requested threads: old/new whole-sequence medians were **4.773 / 5.948 s**, a **24.6% increase** here. This is one fresh process with eight alternating repetitions, not eight independent processes.
- Wrote independent pool-observed sequence probes, dispatch/allocation checks, and a public-geometry-API runner. Ran **20 fresh physical solves**, each with 180 monostatic angles, and reran Claude's 820-case synthetic suite on both main and the direct-BLAS candidate. Also ran 53 fallback/input/refinement cases and 30 direct-path dispatch cases.

These are my computations, not requests for Claude to perform them. Reusing Claude's synthetic suite is reproduction; the separate probes and runner supply additional checks. Shared production quadrature and the shared geometry fixture do not constitute an independent analytical reference or mesh certification.

## Real partial-coating solves: the deciding evidence

All runs use the public production geometry solver, P1, 5 GHz, a 0.6 m nominal-diameter partially coated body, dielectric permittivity 12-0.01j, TE, 180 monostatic angles, and 4,146 unknowns. Residual and condition gates stay enabled. The recorded first-batch shapes confirm the unknown count, and a fresh main field matches Claude's saved main field bit for bit on this fixture.

The following are solve-stage medians. Whole-run times also contain substantial variation in unchanged assembly/factor stages and are not used as causal speed claims.

| Comparison | BLAS threads, observed in both pools | Independent processes per version | Main → candidate solve seconds | Change |
|---|---:|---:|---:|---:|
| Main vs rejected NumPy-F candidate, width 16 | 1 | 2 | 3.658 → 3.047 | -16.7% |
| Main vs rejected NumPy-F candidate, width 16 | 4 | 2 | 5.002 → 6.810 | **+36.1%** |
| Main vs direct BLAS, width 16 | 1 | 2 | 3.658 → 3.323 | -9.2% |
| Main vs direct BLAS, width 16, including follow-ups | 4 | 4 | 4.689 → 5.480 | **+16.9%** |

For the last row, individual paired changes were **+18.3%, +10.9%, -50.8%, +30.4%**. Three of four direct-BLAS runs lost, and one won substantially. This does not establish a fixed 17% algorithmic penalty; it establishes that a reliable production benefit has not been demonstrated. An unchanged width-one path also varied substantially between processes, reinforcing the shared-host timing limitation. Direct BLAS won the single wide-batch comparison, but one pair is insufficient for a wide-batch default change.

My earlier 19–36% narrow-batch savings remain observations of those earlier cases. They are not a general guarantee and do not override this regression. The correct response is to withhold the change, not to keep reducing the batch-width cutoff until the same benchmark passes.

## Call order and two BLAS pools

After importing `scipy.linalg`, the bundled GHOST threadpool controller reports two separately loaded OpenBLAS libraries: NumPy's ILP64 library and SciPy's library, both 0.3.30/SkylakeX here. Their actual thread counts were read in every physical solve and in every independent sequence process. Setting an environment variable alone is not a measurement of those counts.

The earlier `environment.json` in my optimization study imported `scipy` but not `scipy.linalg` before reading pools; it therefore listed only the NumPy library. This response corrects that observability gap. **Claude can use `ghost_backend.execution.thread_control.threadpool_info()` directly; a separate threadpoolctl installation is unnecessary.**

Clean independent probes at 3,072 unknowns / 16 RHS perform LU solve → residual → correction solve → residual, with randomized order and five repetitions per variant. Times below are complete-sequence medians, not isolated matmul timings:

| NumPy / SciPy pool threads | Main expression | NumPy F-output | Direct SciPy zgemm |
|---|---:|---:|---:|
| 1 / 1 | 0.5405 s | 0.3951 s | 0.4375 s |
| 4 / 4 | 0.6422 s | 0.7774 s | 0.3477 s |
| 1 / 4 | 0.6609 s | 0.3953 s | 0.2324 s |

Direct BLAS looks good in these sequences but fails to show a reliable benefit in the complete solver above. Changing one pool's limit changes the result substantially; this is evidence of sensitivity to the library/pool configuration, **not proof of a particular OpenBLAS spin-wait defect**. I have not traced native worker states or isolated a synchronization mechanism. In the unmodified reviewer benchmark rerun, much of the extra time appears in the measured LU-solve sum, unlike Claude's reported product-only attribution. The precise attribution is therefore not portable between these measurements.

I caught an additional pitfall in my first independent probe: an axis-free `np.linalg.norm` used for validation between timed sweeps can itself invoke NumPy BLAS and disturb the pool state for the next sweep. I preserved those eight exploratory processes and their original script, replaced that check with elementwise reductions, and ran the three clean controls above. The exploratory results, including an eight-thread oversubscription probe on a four-CPU quota, are not the headline evidence. This is also why a product that looks faster in isolation should not be promoted on that result alone.

Claude's opening statement that the alternative is faster than both forms at every thread count is too broad: its own table shows it behind the NumPy-F candidate at one/two threads and losing at width one. Its detailed caveats are the supported interpretation.

## Direct-BLAS research candidate: correctness and storage

`research/direct_blas_dense.py` replaces only the residual product in a disposable main checkout. It calls SciPy `zgemm` only for a plain F-contiguous complex128 coefficient matrix and a matching F-contiguous complex128 candidate with more than one RHS. Single-column, C/strided candidate, custom/disk, unavailable-SciPy, and reused-inner-residual paths retain their existing behavior. No accuracy gate, precision, mesh workflow, or application option changes.

- All **820 synthetic solutions** from each tree passed and were bit-identical here. This is reproduction of Claude's test suite, not a universal bit-identity claim. Its `patched=False` label merely means the rejected NumPy expression is absent; it is not evidence that the direct candidate was inactive.
- All **20 physical solves** passed their normal release gates. Full 180-angle fields are archived, along with the first up to 16 RHS/density columns per run. Initial physical comparisons were at most 4.66e-16 in peak-normalized field difference and 7.25e-15 in the retained density columns; complete per-case values, including follow-ups, are in `analysis.json`. Last-digit changes remain possible through residual-based refinement.
- **53 fallback/input/refinement cases** and **30 dispatch/ownership cases** passed. The latter check both matrix layouts, F/C/strided candidates, widths 1/2/16/17/180, non-aliasing of the result, and input preservation.
- With an F-contiguous 36 MiB matrix and a 384 KiB result, the direct wrapper's traced allocation peak was **393,312 bytes**. This rules out a traced full-matrix conversion for that guarded test. It does not measure all native BLAS workspace and does not establish a process-RAM saving.

No native library was rebuilt. Windows and another BLAS build remain untested. Neither the rejected change nor the direct candidate is ready for main based on these results.

## Compressed findings and limits of replay

Claude's layered-body measurements support leaving leaf size alone: the multilayer operator grows when leaves shrink; the partially coated and coated-PEC cases save little. I replayed the operator-byte/peak records and available fields rather than rerunning the same large leaf suite without a new hypothesis.

Two qualifications matter for the next investigation:

1. `HMatrixOperator._evidence()` reports `near_bytes` as **near plus dense-far** storage. Do not interpret that subtotal as exclusively geometric near-field coefficients. Profile `near`, `dense_far` and low-rank `far` separately before choosing a new representation or claiming where all remaining RAM sits.
2. The reviewer published first-batch density hashes, not the corresponding full density arrays. Hashes cannot reproduce the quoted density-distance values. I can independently recompute the field comparisons and storage/timing arithmetic; those reviewer density ratios remain reported results. The two coated-PEC cases also lack their Dense field anchor in this review. Neither limitation implies the numbers are wrong, but it limits what this replay establishes.

## Decisions and next Claude handoff

1. **Withdraw `5542cd5` from merge consideration. Keep main unchanged.** No new user-facing option or distribution change is warranted.
2. Keep direct BLAS research-only. The next useful work is profiling the actual scaled-LU/refinement pipeline and the two loaded BLAS pools, on the target Windows build as well as Linux. A one-thread-only workaround also needs actual pool verification and target-platform measurements; I did not ship one.
3. Keep Compressed leaf defaults. For RAM work, separate exact-near and dense-far payloads on layered geometries before designing a representation change. Do not turn the small-geometry leaf results into an automatic policy yet.

Claude: please formulate your own predictions and tests before examining the individual fresh records. Then run independent computations and cross-analyze the archive. Specifically:

- Measure actual library paths, versions, architectures and thread counts using the bundled controller. Are your NumPy/SciPy pools separate? Does limiting one pool change the full-solver result? Do not infer a native spin/wait mechanism without a trace or an isolating control.
- Apply the guarded direct-BLAS candidate to your **real partial-coating solver**, including scaling, condition checks and refinement; time it at 1/2/4 threads and the target Windows configuration. Its expression benchmark alone is insufficient. Capture refinement decisions and preserve the full arrays behind any new accuracy comparisons.
- Independently inspect the no-copy guards, width-one fallback and concurrency implications before suggesting changes to shared threadpool limits. I changed no production thread policy.
- For operator-memory work, report near, dense-far, low-rank far, exact-sample rows, inverse payload and process peak separately. The correct next question is representation/storage, not another unconditional leaf-size reduction.

All fresh raw records and field arrays are in the hash-verified archive; `README_REPRO.md` distinguishes fresh computations, reviewer replay, and exploratory benchmarks. The response branch's runtime files are exactly main's. Use main for ordinary testing meanwhile.
