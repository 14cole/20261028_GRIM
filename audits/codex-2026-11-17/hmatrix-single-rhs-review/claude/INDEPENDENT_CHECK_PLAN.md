# Independent check plan (written before running anything for this round)

Reviewing Codex `caab534` (`hmatrix-integration-review-response/REVIEW_AND_HANDOFF.md`).
The handoff file named in the request (`hmatrix-production-integration/REVIEW_AND_HANDOFF.md`)
is unchanged since my review `f364689`; this newer branch is Codex's response
to that review. Read: the response only. Production is unchanged (`0be5dc3`).

## Corrections to my review that I expect to accept

1. I said the README should mention `BASE_GRIM_ROOT`. Codex says it already
   does. Check the file; if so, my remark was wrong.
2. "A few MiB" for the larger leaf-query allowance understates the largest
   dense fallback (33 MiB more at side 1,024). Arithmetic: 4q+1 minus 2q with
   q = 16 MiB is 33 MiB. Accept.
3. My test scripts print results instead of asserting. Accept; fix going
   forward.

## The new item: tight headroom

Codex shows with a synthetic leaf that the integrated build refuses a leaf
query at a reservation where the old build would enter it, and is careful to
say this does not show an old full solve would have completed there.

The question that matters to a user is the one Codex leaves open: on a real
solve under a tight RAM budget, does the integrated tree need a larger budget
than the old one?

My expectation before measuring: no. Leaf queries happen when little is
retained, and the largest admission requests come from guards near the root
(block compression and child products), which are identical or smaller in the
integrated build. My audit last round showed the largest accounted request
was lower in the new tree (342 against 356 MiB on the multilayer). So I
predict the minimum workable RAM budget of the integrated tree is equal to or
lower than the old tree's.

Test: production geometry solver with `ram_budget_gib` lowered step by step,
both trees, on two real cases (partial coating TE, 4,146 unknowns; PEC circle
TE, 3,144 unknowns). Bisect the smallest budget at which each tree completes
with all gates, to 4 MiB resolution. Record the rejection message just below
each threshold, so it is clear which guard refused.

Acceptance: if the integrated tree's threshold is not higher than the old
tree's on both cases, the earlier-rejection effect is confirmed as real in
isolation but not binding in these solves. If it is higher on either case,
report by how much and which guard is responsible; that would be a
user-visible regression worth weighing.

Limit known in advance: the RAM budget is the solver's own ledger limit, not
operating-system pressure, and the measured threshold depends on this host's
resident memory at the time.
