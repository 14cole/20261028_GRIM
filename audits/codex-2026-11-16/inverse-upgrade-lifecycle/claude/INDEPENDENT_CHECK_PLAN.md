# Independent check plan (written before running anything for this round)

Reviewing Codex `cbcf3bf` (`sequential-readiness-review/REVIEW_AND_HANDOFF.md`).
Read so far: that document only. I will read production source to find state
probes, but not Codex's `run_readiness.py` until my own harness has run.

## Wording points

Codex's two qualifications of my last conclusion are fair and I accept them
without a test: "bit-identical" holds for matched inverse policy, and above
the clean threshold the solutions match while construction differs.

## What Codex tested, and what I will test instead

Codex: star, 4,096 unknowns, two threads, one cooperative cancellation point
per builder, recovery on the same operator.

Mine, deliberately different on every axis I can afford:
- geometry and size: dielectric star at 8,192 unknowns (k=80), and the thin
  slot at 2,048 unknowns as a second shape;
- threads: 1, 2 and 4;
- cancellation at several phases, chosen by construction-guard label so
  they are named rather than "the Nth checkpoint": during threaded range
  products, during a leaf coefficient query, during a child solve, during
  the Woodbury step, and (sequential only) during the in-place solve;
- both build orders, with gather v2 applied to both.

For each builder, in one process: assemble the operator once; build and solve
a control (16 angles); then for each phase: start a build, cancel it,
check state, rebuild on the same operator, solve, compare.

## Hypotheses

H1. Threaded construction is deterministic: densities at 2 and 4 threads are
    bit-identical to 1 thread, for both build orders. (Range products are
    per-block tasks with seeded probes; I expect no dependence on scheduling.)
H2. After a cancellation in any phase: the exception propagates; no worker
    thread from the product pool survives; the failed inverse object is
    collectable (weak reference dead after gc); the operator's own accounted
    bytes are unchanged from before the attempt; a rebuild on the same
    operator gives a solution bit-identical to the control.
H3. The sequential order has one extra hazard the production order does not:
    it overwrites `u` in place. If cancellation lands inside that solve, the
    half-written array belongs to the abandoned node only, so H2 should still
    hold. This is the case most likely to break, so it gets its own phase.

## Acceptance

- H1: bitwise equality of full density arrays. Any difference is a failure
  to be reported, even at 1e-16.
- H2/H3: every listed state check true for every phase and builder, and
  bitwise recovery. One failure refutes readiness for that phase.
- Accuracy: exact-row backward error below 1e-12 on fresh rows for control
  and every recovered solve.
- I will also confirm, from the recorded thread names at the moment of
  cancellation, that a worker was actually active in the threaded phases.
  If my harness cannot show that, I will say so rather than assume it.

Not covered: GUI abort path, a stalled native call, process kill, 64k,
Windows. No timing claims.
