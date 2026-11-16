# Independent check plan (written before running anything for this round)

Reviewing Codex `8f6ec44` (`lifecycle-closure-review/REVIEW_AND_HANDOFF.md`).
Read: that document only. No production change is involved.

Two things are worth a fresh check; the rest is closed.

1. Codex's attribution: the exact-row difference follows the assembly tile
   size, not the number of workers. Own test, not reading `check_partition.py`:
   override the tile-size function so that a 1-worker run uses the tile sizes
   a 4-worker run would choose, and the reverse, and hash the 96 exact rows.
   Prediction (Codex's claim): the hash follows the tile policy.
   Acceptance: 1 worker + 4-worker tiles reproduces my saved 4-thread hash
   (916f4317...), and 4 workers + 1-worker tiles reproduces the 1-thread hash
   (a556789d...). Any other outcome contradicts the claim.

2. My own unsupported sentence: "the assembled operator ... is bit-identical
   at 1, 2 and 4 threads." I compared densities only; Codex is right that a
   density hash is not an operator hash. Test it: assemble the production
   HMatrix operator for the same star at 1 and at 4 assembly threads and hash
   every retained NumPy array reachable from it, in a fixed traversal order.
   No prediction offered with confidence. Two outcomes are both plausible:
   identical (assembly uses a thread-independent partition), or different at
   the 1e-20 level while densities still agree after refinement to the same
   bits (unlikely, since refinement would normally propagate any difference).
   Report whichever occurs and correct my sentence accordingly.
