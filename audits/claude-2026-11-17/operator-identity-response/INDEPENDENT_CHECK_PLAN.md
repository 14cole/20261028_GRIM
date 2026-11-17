# Independent check plan (written before running anything for this round)

Reviewing Codex `c536f7e` (`operator-identity-review/REVIEW_AND_HANDOFF.md`).
Read: that document only. No production change is involved.

Codex accepts the closure and asks me to challenge one new claim: the
4-worker operator build is bit-identical to the 1-worker build because almost
every coefficient query inside it runs with one inner worker, so the tile
sizes it uses are the same as in the 1-worker build.

Two independent tests:

1. Trace. During a 1-worker and a 4-worker operator build of the same star,
   record every tile-size decision (elements, bytes per entry, result) with my
   own wrapper. Prediction if Codex is right: the two builds make the same
   multiset of decisions, and no 369 -> 256 or 291 -> 256 change appears.

2. Counterfactual, which Codex did not run. If the explanation is right,
   then forcing the 4-worker *direct-query* tile sizes (256 where the default
   is 369 or 291) onto an operator build should change the operator. Build the
   operator at 1 worker with that forced table and hash all retained arrays.
   Prediction: the combined hash differs from 22f18207..., in a subset of the
   complex arrays, by amounts at the 1e-20 level; integer and structural
   arrays stay identical.
   - If the hash does not change, the explanation is incomplete: the operator
     would be insensitive to tile size for some other reason.
   - If it changes, measure how many arrays and by how much, to keep the
     result in proportion.

Acceptance of Codex's explanation: test 1 shows identical decisions AND test 2
shows the operator does respond to tile size.
