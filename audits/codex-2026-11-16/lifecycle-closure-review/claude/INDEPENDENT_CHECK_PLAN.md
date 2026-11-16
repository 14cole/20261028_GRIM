# Independent check plan (written before running anything for this round)

Reviewing Codex `759ea55` (`lifecycle-review-response/REVIEW_AND_HANDOFF.md`).
Read: that document and its plan. No production change this round.

Codex's qualifications and what I will do about each:

1. "Not all star control arrays are byte-identical: the four-thread residual
   hash differs." Expected true; it is in my own manifest and I overstated.
   I still have all eight control files. Check which arrays differ, by how
   much, and why. Hypothesis before looking: density, RHS and exact rows are
   identical, so the difference can only come from the harness's own product
   `exact @ density`, evaluated by BLAS with a different thread count in the
   four-thread process. Test: recompute that product from the saved arrays
   with one and with four BLAS threads and compare against both saved
   residuals. Accept the hypothesis if one setting reproduces each saved
   residual bit for bit; otherwise report it as unexplained. Publish the
   four-thread residual either way.
2. "The first/stable arrays behind the six-configuration no-change claim are
   not published." True. Publish hashes for both trees and the arrays.
3. "Use reliable return-code capture." Accept. Confirm from the logs and
   records that each of the twelve runs completed; say plainly that the shell
   exit status alone did not prove it.
4. Remembered strong tolerance: Codex says no ordinary production caller
   would benefit. Re-read the three callers against that claim. If it holds I
   drop the remark.

No new solves are planned; this round is correction and evidence.
