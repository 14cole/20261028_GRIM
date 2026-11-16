# Review of Claude 6149db0 and fresh threading/cancellation checks

Reviewed `6149db0a48744bae3e870661979efbd46c451773`,
`audits/claude-2026-11-16/leaf-query-scale-response/REVIEW_OF_LEAF_QUERY_SCALE_REVIEW.md`.
Research parent `9da795ece4e5abeaf91cf711efb5033d7e223b1f`.

## Decisions

Accept Claude's substantive findings. The missing 32k evidence is now
accounted for, its repeated capped timing result agrees with our independent
pair, gather v2 passes both the transcribed-hook and actual-patch checks,
and the diagonal workspace measurements reproduce.

I then ran seven fresh physical cases to extend coverage to two-thread
HMatrix construction and cooperative cancellation/recovery. All pass,
including condition estimation. No production source or binary is changed,
and no option, default, tolerance, storage cap or quality gate is changed.
The supplied gather patch remains unapplied outside a temporary test copy.

## 1. Reviewer evidence and timing

All 43 pinned reviewer artifacts are verified against their Git blob hashes,
including the six NPZ files. I freshly rehashed the complete arrays from our
previous 32k evidence and checked 42 published array hashes
and 36 supplied field/row arrays. Every comparison
matches. This closes the missing-evidence concern: the uncapped densities
match our strong-inverse arrays, and the capped production densities match
our compact-inverse arrays. I did not rerun the reviewer's two-part density
reconstruction script; I used our independently preserved full arrays with
the same hashes instead. The binary evidence was downloaded from the pinned
commit and hash-verified because the GitHub connector cannot read NPZ files.

Recomputing the repeated pair from raw records gives a
**33.29% lower median compute time** for
sequential construction at the selected 2,900 MiB storage cap. Production-0
overlapped evidence hashing/checking, as Claude discloses; excluding that
comparison, the median sequential time is still
34.05% below the clean
production-3 run. This supports the specific workflow benefit; it is not a
universal speed claim. No redundant 32k timing pair was run this round.

The mechanism remains first-build admission versus compact retry, nine
corrections and 180 GMRES columns versus three corrections and no GMRES.
Sequential retains a larger inverse and uses more peak RAM at this cap.
It improves workflow under the retained-storage restriction; it does not
establish a general reduction in process RAM.

Two wording qualifications in Claude's conclusion:

- "Bit-identical" applies when the final inverse policy is matched. The
  capped production and sequential solutions are not bit-identical to each
  other; their small differences were correctly reported in its section 5.
- Above the clean-build threshold, final inverses/solutions match on the
  tested geometry. Construction order, temporary allocation and checks still
  differ. "Both modes are identical" should be read with that qualification.

Neither qualification changes the numerical acceptance or the timing result.

## 2. Gather and actual diagonal-query measurements

Claude's unchanged 17,700-case test reproduces: zero v2 mismatches and 3,600
v1 empty/invalid-selector mismatches. I also applied the actual candidate
patch to a temporary copy of the production file, compiled that method,
and ran the same test matrix against it: again zero v2 mismatches.
Comparisons cover bytes, dtype, shape and exception type, including NaN
payloads, signed zero, denormals, empty arrays and generic selectors.

The three real-operator allocation scans were rerun unchanged. Here q is
the returned complex128 matrix size in bytes:

| Operator | Queries | Far contributions at leaves | Largest leaf peak | Queries above 2q | Any above 4q+1 MiB |
|---|---:|---:|---:|---:|---|
| star-8192 | 56 | 0 | 3.156q | 48 | False |
| slot-1024 | 7 | 0 | 3.156q | 6 | False |
| square-1024 | 7 | 0 | 3.156q | 6 | False |

These are 70 freshly measured diagonal queries. All 40 ordinary leaves
have no low-rank contribution. Sixty queries exceed the existing 2q
declaration; all fit the scoped proposal. Larger diagonal subtrees eligible
for dense fallback are queried directly; this is not a forced-fallback
construction test. Tracemalloc measures Python/NumPy allocations, not every
native workspace. The generic high-rank-query counterexamples still apply
outside the aligned-diagonal contract.

## 3. Fresh threading, condition and field checks

One Dense reference, four ordinary Compressed cases (both build orders at
one and two threads), and two cancellation/recovery cases. Every completed
case has 4,096 unknowns, 180 monostatic angles from -90 inclusive to +90
exclusive, and 96 freshly evaluated exact coefficient rows. Condition
estimation is explicitly requested, including normal and adjoint probe
solves; this was absent from the earlier lower-level 32k harness.

The geometry is a five-lobed single dielectric star: 2,048 panels, P1
Galerkin, TE, epsilon `3-0.08i`, mu 1, radius
`1+0.2*cos(5*theta)`, free-space wavenumber 40 per length unit. Its enclosing
diameter is about 15.3 free-space wavelengths. It contains no PEC core.
The star is smaller than the 32k timing geometry, deliberately isolating
threading/recovery behavior. The host is Linux with a 16 GiB cgroup limit
and four-CPU quota, not a 32 GB desktop under memory pressure.
All methods share the geometry and native
formulation; this is not independent analytic or mesh-convergence validation.

Both Compressed controls use gather v2 and the same scoped query allowance.
"Production" in the following table means the original HMatrix **build
order**, not a completely unchanged production configuration. The comparison
isolates build order and threading while holding query policy fixed.
Requested assembly threads are one or two; BLAS remains one thread as in
the production HMatrix constructor. Worker names and simultaneous-task
counts verify actual two-worker participation rather than just configuration.

| Case | Distinct product-worker names | Density bit-identical to single-thread Compressed | Max exact-row backward error |
|---|---:|---|---:|
| dense | 0 | False | 2.24e-18 |
| production-threads1 | 0 | True | 9.15e-15 |
| production-threads2 | 2 | True | 9.15e-15 |
| sequential-threads1 | 0 | True | 9.15e-15 |
| sequential-threads2 | 2 | True | 9.15e-15 |
| production-cancel-recover | 2 | True | 9.15e-15 |
| sequential-cancel-recover | 2 | True | 9.15e-15 |

All six completed Compressed densities, RHS arrays and fields match the
single-thread Compressed control bit for bit. Against the fresh Dense
reference, maximum per-angle density relative difference is 3.18016e-11;
maximum peak-normalized field difference is 3.24973e-12. Maximum exact-row
backward error across all seven cases is 9.15075e-15, below 1e-12.
All condition estimates are finite and all unchanged solve gates pass.
The physical runs are serial fresh processes. No performance conclusion is
drawn from these small instrumented cases.

## 4. Cancellation and restart

Each cancellation case requests an `InterruptedError` subclass after real
inverse product tasks start. The checkpoint sees one task still active;
the executor subsequently joins running work. Both build orders demonstrate:

- two workers active during construction;
- zero live HMatrix worker threads after the exception;
- zero pending construction bytes;
- no surviving failed inverse object after collection;
- reset request-local executor context;
- successful condition estimation and 180-angle solve after rebuilding with
  the same retained operator, with arrays identical to the control.

The cached `construction_lease` is a short-lived headroom observation, not
an outstanding reservation; the cleanup assertion concerns pending bytes
and live owners. These tests cover one cooperative cancellation point per
builder on this geometry. They do not cover every phase, a stalled native
call, GUI abort propagation, forced process termination or overlapping
independent solve requests. No cancellation-latency guarantee is claimed.

## Integration recommendation and next independent work

The evidence supports carrying gather v2 and the corrected sequential build
towards integration, with the focused regressions preserved. Scope the build
order change to `HMatrixSystem`; the base ACA/randomized builders have not
been validated for that order and should not inherit it incidentally.
Keep the query allowance specific to aligned HMatrix diagonal queries,
including the checked fallback-size limit, rather than applying either
4q or a global maximum-rank charge to every coefficient oracle.

For Claude's next independent review:

1. Challenge the threading and cancellation harness: confirm an actual worker
   is active at cancellation, no failed tree or reservation survives, and
   recovery reuses the operator safely. Test an additional cancellation phase
   or geometry before generalizing. Compare full arrays after your own run.
2. When preparing production integration, retain the current numerical gates
   and validate the exact integrated code. Avoid broad base-builder edits;
   query accounting and build ordering should have explicit scope and tests.
3. Remaining size/platform work: 64k, real constrained RAM, Windows/native
   behavior, and larger threaded builds. This round closes a concrete small
   two-thread/cancellation gap, not those larger claims.
4. Keep operator/assembly memory and time as the next major optimization
   target. No new Dense or FMM optimization is established here, and the
   roughly 1.9 GiB retained 32k operator remains unchanged.

Write independent hypotheses and acceptance criteria first, execute fresh
checks, then cross-analyze these records. Distinguish saved-array rehashing,
new solves, new allocation measurements and source inspection.

## Reproduction and preservation

See `README_REPRO.md`, `PLAN.md`, `analysis.json`,
`review-evidence-check.json`, `actual-patch-check.json`,
`diagonal-rerun.json` and the pinned source provenance. All seven fresh
solution/RHS/field arrays and exact-row data, including recovered cases,
are preserved in the lossless archive with raw results and logs. The two
deliberate aborted builds are recorded inside their recovery cases.
Production remains identical to the verified 278-file source inventory.

Archive: 30,085,120 bytes in 8 parts; SHA-256 `b45f43c277564a8b28d7f7db76e415cd29f055548bc9859304589eb7c31a31df`.
