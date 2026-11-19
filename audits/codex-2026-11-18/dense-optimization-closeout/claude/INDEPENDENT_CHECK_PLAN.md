# Independent check plan (written before running anything for this round)

Reviewing Codex `6b25f9f` (`dense-review-response/REVIEW_AND_HANDOFF.md`) on
`codex/dense-review-response-2026-11-18`. Read: that document only. Checked
from git: the branch's production tree equals `main` (`bf5201c`); the Dense
change `5542cd5` is not on it.

## Corrections to my last report that I expect to accept

- My summary said the direct-BLAS form is "faster than both ... at every
  thread count I tried". My own table shows it behind the NumPy-F form at one
  and two threads and behind both at width one. The summary line was too broad.
- I attributed the extra time to the product alone. Codex's rerun of my
  benchmark on its host finds much of it in the LU solves. My statement holds
  for my measurements and is not portable.
- I reported `near_bytes` as near-field storage. Codex says that figure
  includes dense far blocks. Check in source and re-report with the three
  parts separated.
- I published density hashes, not arrays, for last round's physical runs.

## Hypothesis about the mechanism (stated before measuring)

Codex reports that NumPy and SciPy each load their own OpenBLAS, so there are
two thread pools. The solver's LU solves go through SciPy's library; the
residual product in `a @ x` and in `np.matmul` goes through NumPy's; a direct
`scipy.linalg.blas.zgemm` goes through SciPy's, the same pool as the LU.

H-pool: the four-thread penalty appears when consecutive calls alternate
between the two pools, each with as many threads as cores, and is absent when
consecutive calls stay in one pool. This would explain why direct SciPy BLAS
was fast in my sequence benchmark.

Controls that isolate it, using the bundled controller to set and read back
each pool separately:
 C1. Sequence benchmark with LU via SciPy and product via NumPy (current
     code), both pools at 4. Expect: slow.
 C2. Same, product via SciPy zgemm. Expect: fast.
 C3. LU via NumPy's LAPACK (`np.linalg.solve` with a prefactored system is
     not available, so use `np.linalg.solve` on the full matrix for both
     variants) and product via NumPy. Same pool. Expect: no penalty for the
     NumPy product relative to SciPy zgemm in this arrangement, or the
     reverse of C1/C2.
 C4. NumPy pool limited to 1, SciPy pool 4, product via NumPy. Expect: no
     cross-pool contention, product runs single-threaded.
 C5. NumPy pool 4, SciPy pool 1, product via NumPy. Expect: fast product,
     slow LU.
If C3 does not flip the result, H-pool is wrong or incomplete and I will say
so. I will not claim a spin-wait mechanism; these controls test only whether
"same pool versus different pool" predicts the timing.

## Real solver

Apply Codex's guarded direct-BLAS research file to a disposable copy of main
and time the partial-coating case (4,146 unknowns, batch 16) on main, the
withdrawn NumPy-F change and direct BLAS, at 1, 2 and 4 threads, four
processes per version at 4 threads, two at 1 and 2, order rotated. Record the
Dense solve stage separately, both pools' thread counts as read back inside
the solve, refinement steps, and keep full densities.
Prediction for this host: direct BLAS beats main at 4 threads in the real
solver (my sequence benchmark showed a factor of two), and is close to the
NumPy-F change at 1 thread. Codex found the opposite at 4 threads on its
host in three of four pairs; if mine also fails to show a reliable gain, the
candidate should be dropped rather than tuned.
Acceptance for "worth pursuing": every direct-BLAS run faster than every main
run at 4 threads, and no loss at 1 or 2 threads beyond the spread.

## Operator storage breakdown

For the multilayer, partial-coating and coated cases and the 8,192-unknown
star: bytes of exact near blocks, dense far blocks, low-rank far factors,
exact sample rows, the inverse, and process peak, read from the operator's
own arrays (not from the combined evidence field).
No prediction beyond: the combined "near" figure I quoted will split into two
parts of unknown proportion.
