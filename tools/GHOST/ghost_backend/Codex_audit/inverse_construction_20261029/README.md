# Inverse construction implementation and shadow measurements

Implemented after the review of `Claude_audit/review_of_codex_impedance_followups.md` on 2026-10-29.

## Delivered

### Incremental construction checks

`compressed/construction.py` registers an unfinished inverse while its tree is being built. The normal factor object does not yet own that tree, so its storage was previously absent from request-owned accounting during construction. Temporary arrays are counted by their backing allocation, avoiding duplicate counts for views. Registration ends on success, failure or cancellation; the construction helper uses a weak reference so it cannot delay releasing an old inverse.

Allocation groups check current physical/commit headroom and the request allowance before expensive operations. Pending group allowances are separate from resident payload and receive no residency credit. A shared lock makes check-and-hold atomic across requests; peers cannot claim the same pending headroom. Holds end when each operation finishes, including exceptions. A tile reload covered by its enclosing allocation group is not charged twice.

The checks cover sampled range growth and projection, QR/SVD/output work, ACA construction, leaf coefficient reads, LU, child inverse products, and Woodbury corrections. Off-diagonal blocks enter retained accounting individually, before constructing their partner. Retained capacity is checked before leaf and correction allocations. Optional preconditioner upgrades keep the old inverse counted during replacement construction.

These are explicit allocation models plus live checks, not a promise to survive arbitrary external memory consumption or every vendor-specific allocator behavior. Pending holds can temporarily make a peer's admission conservative while an allocation group is executing. No forecast discount is enabled by these changes.

### Avoid large coefficient conjugation copies

Hierarchical adjoint range products now conjugate the small input/output arrays instead of copying the retained coefficient factors. A per-level workspace estimate covers product results and reductions. Matrix coefficients, tolerances, residual checks and mesh certification are unchanged.

### Same-request shadow measurements

After a validated hierarchical field solve, metadata records operator/inverse forecasts against actual retained storage, construction check statistics, and process-memory observations. For a later larger mesh with the same existing request identity and polarization, metadata also compares a hypothetical storage correction using the previous measured/forecast ratios and a 1.5 margin, capped at the original forecast.

This is diagnostic only: it never changes the plan, retained cap, inverse accuracy or admission. It records when the hypothetical correction would have underestimated the next mesh. The latest observation per key is bounded to 16 keys, contains no matrices, and is discarded with the request. Cross-frequency sharing remains disabled. This creates no persistent database of earlier solves.

Construction process observations are samples at allocation checkpoints; they can miss an intermediate native-library peak. Whole-process observations can include concurrent work. `peak_accounted_build_bytes` is an accounted allocation allowance, not a measured resident peak. These distinctions are preserved in metadata.

## Timing and accuracy

The isolated benchmark uses a complex Helmholtz operator, two assembly workers, one BLAS thread, an 8 GiB request cap, and three timed inverse constructions after warmup. It compares committed source `743d6391dfa18a7b71c369e4553d5d7b39194155` with the implementation in separate serial processes. Baseline source is loaded only inside the benchmark process; production files are never swapped.

| Unknowns | Previous median | New median | Added time | Solution difference |
|---|---:|---:|---:|---:|
| 1,536 | 0.080 s | 0.262 s | 0.183 s | Bit-for-bit identical |
| 4,096 | 0.241 s | 0.632 s | 0.391 s | Bit-for-bit identical |

These low-rank inverse microbenchmarks show noticeable relative overhead, although the added absolute time is under half a second. They are not end-to-end large-inlet speed estimates. The unrefined inverse residuals were about 8.30e-12 and 1.26e-11 respectively. Whole-process sampled private-memory peaks were essentially unchanged: approximately 244.6 versus 245.3 MiB and 516.2 versus 516.5 MiB. Thus these cases do not establish a total peak-RAM reduction. Avoiding coefficient-sized temporary copies is a concrete code-level saving, not a demonstrated large-geometry capacity result.

Numerical regression coverage also exercises public PEC, impedance, dielectric, lossy magnetic, coated, layered, thin-gap, acute and reentrant solves, plus the analytic 10,000-panel cylinder under a 2.5 GiB cap. Final validation: **260 tests and 39 subtests passed across 19 files in 193.28 seconds**, with no failures. Results are recorded in `validation_summary.json`.

## Deliberately unchanged decisions

- Compressed remains the default. Dense and surface impedance remain explicit overrides.
- The existing RAM target, explicit limits, scheduler reservations and numerical acceptance gates are unchanged.
- The experimental pilot and same-request storage discounts remain disabled. A larger model is not newly certified to fit simply because these checks exist.
- No blanket stop after `MemoryError` was added. Existing retries still price their actual mesh before assembly. The earlier review established that the recorded later refusals cost less than 2.17 seconds altogether; changing recovery based only on increasing unknown counts could remove a viable path.
- The full-size 2 GHz bulk run was not repeated because its admission forecast remains unchanged. The conditional discounted-admission experiment should follow independent qualification, not be presented as already enabled.

## Validation and follow-up

New tests force rejection before sampled products, QR/SVD and tree allocations; check pending allowances, cancellation, shared-process headroom, temporary-view accounting, partial-tree release/retry, and old-inverse ownership; and verify request isolation and non-mutating shadow observations. A rebuild test caught an initial bookkeeping reference cycle, fixed with weak ownership. A separate old test expected the removed automatic picker; it now asserts compressed-default behavior while retaining the analytic accuracy and memory checks. Raw failed and successful runs are retained for review.

Next qualification should gather independent lossy, low-loss, concave and coating cases across refinement steps, with external peak monitoring and tight allowances. Only then consider a production forecast correction. This implementation adds the checks and evidence needed for that study; it does not claim that a 12-foot inlet at 15 GHz is now proven to fit 32 GB.

All five source/test files from the prior diagnostic implementation still match their saved hashes. `source_hashes.json` records the ten production/test files touched by this implementation. Patch whitespace checks passed. Temporary test directories were removed; raw result records and benchmark evidence remain. Nothing was committed or pushed in this implementation turn.
