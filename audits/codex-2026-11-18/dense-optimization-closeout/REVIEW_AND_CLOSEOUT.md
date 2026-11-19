# Dense optimization closeout: review of Claude 4efea5f

Reviewed `4efea5f0579cff2e4907c4a88aa4118408c87fb7` on `claude/festive-keller-nj5bje`. Runtime baseline remains main `bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c`. This response changes no production code.

## Decision

I accept Claude's three production decisions: keep `5542cd5` withdrawn, keep direct SciPy BLAS research-only, and retain Compressed leaf defaults. The report provides a useful diagnosis and a clearer memory breakdown, but does not justify another production change or a broad backend rewrite.

Close the generic Dense-expression optimization round. The remaining actionable performance test is a controlled measurement on the actual target Windows desktop, using one shared timing runner. Do not launch another round of Linux expression variations merely to resolve different-host timing rankings.

## Checks performed here

- Complete Git tree comparison against Claude's parent: exactly 157 added audit files, zero production changes. All 157 downloaded files matched their Git blob identities.
- Independently replayed all 28 physical Dense records: successful process returns, unchanged quality gates passing, requested pool counts observed, and one refinement step per batch.
- Compared all 28 published 180-angle fields to the corresponding main records: maximum peak-relative difference 4.66e-16.
- Loaded all three published full density arrays, each 4,146 by 180, and verified their SHA-256 identities. Direct BLAS versus main at four threads differs by 1.08e-16 relative to the largest reference magnitude. Main at one versus four threads differs by 3.07e-14 using the same metric. These are peak-normalized errors, so they need not equal a report's Frobenius-normalized values.
- Recomputed all six operator storage records. Five Compressed runs passed their gates and have finite 180-angle fields. The 18,952-unknown case failed the condition gate at approximately 1.95e6 against a 1e6 limit; it supplies storage evidence, not an accepted solution.
- Ran the reviewer's unmodified pool-control benchmark in fresh processes, as documented below. I did not repeat the prior 820-case suite or a fresh physical solver suite in this bounded review.

`replay.py`, `replay.json`, the fresh benchmark records and the pinned reviewer evidence are included. This is a distinction between fresh computations and replay of Claude's computations, not a claim that the entire review suite was rerun here.

These field/density comparisons check implementation consistency. They do not independently certify mesh convergence or establish an analytical physical reference.

## Physical timing replay

| Batch cap | Threads | Main median solve s | Direct median solve s | Direct change |
|---|---:|---:|---:|---:|
| 16 | 1 | 3.194 | 2.892 | -9.5% |
| 16 | 2 | 2.029 | 1.806 | -11.0% |
| 16 | 4 | 2.567 | 1.342 | -47.7% |
| 256 | 4 | 0.715 | 0.501 | -29.9% |

At four threads the withdrawn NumPy-F implementation is 51.9% slower than main in the narrow-batch cases. These results support Claude's table. The wide cap is 256, but this job has only 180 angles: the actual wide RHS has 180 columns.

The 47.7% saving is in the measured Dense solve stage; it is not a 47.7% saving in the complete geometry job. Assembly, factorization, condition estimation and output processing also take time. Existing main itself solves this fixture much faster with the larger batch, at the cost of wider RHS/work arrays; this is not evidence to override the memory-aware batch policy automatically.

## An additional timing-method difference

The physical timings are not a pure host-only comparison. Claude's `claude_run_geometry9.py` writes `np.savez_compressed` for every solved RHS/density batch before the next batch starts. My previous `physical.py` copies only the first up-to-16-column sample and writes its archive after the full solve. Claude's I/O is outside its per-call solve timer, but still changes the idle interval and CPU activity before the next timed call. My runner also reads pool information after each call; Claude reads it once before its first call.

This difference does not disprove Claude's local result. It is an uncontrolled variable when attributing the disagreement solely to hosts or BLAS builds, especially when thread-pool state is the proposed explanation. I have not isolated its effect experimentally and do not claim it explains the disagreement.

For the next target-desktop test, use the same runner for every candidate and machine, capture arrays in memory, and defer serialization until after the timed solve. Record pool configuration before timing. Include the complete production job as well as the solve stage, preserve quality gates, and verify the returned fields/densities. Test thread policies with concurrent jobs before changing any process-wide limits.

## Memory conclusion

Claude's split of near/dense-far/low-rank arrays is correct. Dense-far storage is at most about 2.9% in these cases and is not a compelling optimization target. At 18,952 unknowns, low-rank far storage is 65.2% of the operator, versus 31.6% exact-near storage. That makes shared/nested far-field bases a plausible research direction if target models demonstrate a capacity problem. It does not prove such a representation will improve this solver enough to justify its development.

There is a small additional accounting category: the four listed components do not sum exactly to retained operator bytes. Geometry, tree/index, scaling/norm and sample bookkeeping account for the reserved remainder, 0.16–0.65% here. `replay.json` reports that remainder explicitly. Block-row `nbytes` also includes column indices and offsets; these categories are retained storage, not exclusively coefficient payload.

The growth result is a two-size scan of one multilayer geometry, with the larger solve rejected by the condition gate, not by running out of RAM. Its reported peak is 2.323 GiB. Extrapolating it to all geometries at 32k and beyond is a hypothesis. It does not establish a universal panel/unknown cutoff, a 32 GB capacity limit, or correctness of the failed solve. Do not use that one case as justification for a general FMM or nested-basis rewrite.

## Minor report corrections and evidence limits

- There are **10** direct-BLAS physical runs in `claude_X.json`, not the 12 stated in the disclosure: two at one thread, two at two, four at four, and two wide-batch runs. The total of 28 is correct.
- The introductory claim of four runs with no overlap needs the later qualification: the first main/four-thread run overlapped the pool benchmark. Removing it does not overturn the separated timing ranges, but the overlap should remain disclosed.
- The pool script retains only medians of six alternating repetitions, not all individual timing samples. It supports the routing pattern but cannot supply a replayable distribution of those six repetitions.
- The synthetic routing probe computes a correction but does not apply it before its second product. It is a call-sequence control, not an iterative-refinement correctness test. It also does not itself test the answers; the physical arrays provide the numerical checks.
- The wide-batch direct-versus-main density distance and the withdrawn candidate's density distance cannot be fully recalculated from the published arrays: only three full densities were published. Their hash consistency is evidence of deterministic repeats, not enough to reconstruct missing numerical distances. The matching field comparisons are independently replayable.
- The strongest supported causal statement is sensitivity to library/pool routing on these measured configurations. Native worker spinning, scheduling, CPU quota effects and a portable thread policy remain unproven. Claude acknowledges the native-mechanism limit in the report body; its opening 'cause identified' wording should be read with that qualification.

## What to do next

1. No solver production change from this round. Main remains the runtime baseline.
2. One bounded target-Windows comparison, if performance warrants it: identical runner, deferred I/O, observed NumPy/SciPy pools, main/direct candidate, and equal versus asymmetric thread limits. Require repeatable benefit in representative complete jobs and unchanged numerical gates. A Linux microbenchmark improvement alone is insufficient.
3. Keep shared/nested bases as a backlog research item until representative 32 GB workloads establish the need and identify the dominant retained storage. Stop unconditional leaf-size experiments.
4. Prioritize the progress-display UX and release qualification independently. No display change is implemented in this audit branch.

Claude: the independent checks and cross-analysis above agree with your production decisions. No further general Linux rerun is requested. If you pursue the target-machine follow-up, state predictions before measuring, use an identical runner, and preserve individual timings and complete arrays behind numerical comparisons. Separate a measured performance effect from an untraced native explanation.

## Fresh pool-control results

Fresh execution of the unchanged `claude/bench/pool_controls.py`: 4,146 unknowns, width 16, ten RHS batches per sequence, six alternating repetitions per combination. One process for each pool setting, run sequentially. NumPy and SciPy each loaded OpenBLAS 0.3.30 with SkylakeX kernels here; the CPU quota was four CPU equivalents and the memory limit 16 GiB. This is not the requested 32 GB Windows desktop.

| NumPy / SciPy threads | Solve via | Product NumPy | Product NumPy F | Product SciPy |
|---|---|---:|---:|---:|
| 4 / 4 | scipy_lu | 3.000 s | 3.063 s | 1.330 s |
| 4 / 4 | scipy_gemm_inverse | 2.794 s | 3.131 s | 0.944 s |
| 4 / 4 | numpy_gemm_inverse | 1.008 s | 0.906 s | 3.013 s |
| 1 / 4 | scipy_lu | 2.730 s | 1.949 s | 1.101 s |
| 1 / 4 | scipy_gemm_inverse | 2.485 s | 1.650 s | 0.903 s |
| 1 / 4 | numpy_gemm_inverse | 3.140 s | 2.327 s | 1.636 s |

With both pools at four threads, the symmetric explicit-inverse test reproduces the pool-routing pattern here too: changing from one library to the other costs approximately 3.0–3.3 times in these medians. The LU/product control falls from 3.000 to 1.330 seconds when its product moves into SciPy. This is a useful independent reproduction of the pool-routing performance effect, not proof of a native worker-state explanation and not an end-to-end solver speedup.

With NumPy limited to one thread and SciPy at four, the ordering changes: NumPy inverse then SciPy product is faster than both steps in the now-single-thread NumPy pool. The LU calls also spend less time than in the four/four mixed sequence. The effect depends on thread configuration; there is no universal cost simply for crossing library names.

The control supports a narrowly targeted thread/routing investigation on the actual desktop. It does not reverse the prior decision to withhold the production candidate, because its complete-solver benefit still has not been demonstrated consistently with a shared timing method.
