# Independent check plan (written before running anything for this round)

Reviewing Codex `0be5dc3`: a production change to three files under
`tools/GHOST/ghost_backend/compressed/` (gather v2 in `hmatrix.py`, a new
`hmatrix_build.py`, and a four-line override in `hmatrix_factor.py`).
Read so far: the production diff only. Not opened: Codex's report, tests,
suites or results.

This is production code. The object under test is the integrated tree itself,
with no research hooks changing behaviour, compared with its parent tree.

## Code review notes made from the diff (before any run)

Compared line by line with the base `CompressedSystem.build`:
- Scope: only `HMatrixSystem` gets the new order; the base class is untouched.
- Accounting: `u` and `v` are reserved at compression; `e` overwrites `u`; no
  later subtraction. Final charge is `v12 + v21 + e1 + e2`, same as the base.
- The Woodbury matrix is passed as live to the second child solve and the
  second correction step. The in-place solve keeps the base allowance
  `8*u.nbytes + 1 MiB`. Leaf queries are priced `4q + 1 MiB`.
- Small nodes keep the base order so a rejected compression can fall back to a
  dense leaf.
Things I could not settle by reading and will test:
 (a) the copy path in `_solve_in_place` (non-complex128 or read-only input):
     is the byte accounting right before, during and after?
 (b) a large node whose compression is rejected now fails after its children
     are built instead of before. Same exception; confirm nothing else changes.
 (c) `e` now has the memory layout of `u` instead of a fresh F-ordered array.
     Could that change rounding in later products? Only bitwise comparison of
     solutions can answer.

## Hypotheses

H1. With no storage cap biting, the integrated tree gives bit-identical
    densities and fields to its parent, on every case, with unchanged
    condition estimates, refinement counts and final inverse size.
H2. Its accounted inverse high-water equals its final inverse size
    (unpacked), where the parent's is larger.
H3. Under my allocation audit the integrated build has zero guard shortfalls
    above 1 MiB, including the leaf-query guard that the parent under-declares.
H4. At storage caps between the two thresholds the integrated tree builds
    cleanly where the parent retries (multilayer 690 MiB) or fails (650 MiB);
    at 32,768 unknowns with a 2,900 MiB cap it reproduces the reference
    solution bit for bit in one build.
H5. Threads and cancellation: densities bit-identical at 1, 2 and 4 threads;
    cancelling in each named phase leaves no worker, no live inverse, and a
    bit-identical recovery.
H6. Process peak memory is not meaningfully changed (within about 2%).

## Cases

Chosen to include material types I have not yet used for this change:
- multilayer TM (two dielectrics over PEC), partial coating TE and TM
  (junctions): the hard cases from earlier rounds, with my Dense anchors;
- new for this round: a PEC circle, a concave PEC cavity, and a coated PEC
  body, each with a fresh Dense anchor. PEC uses a different oracle kind and
  a different default inverse tolerance, so it exercises a path the dielectric
  star does not;
- dielectric star at 8,192 (threads, cancellation) and 32,768 unknowns (cap).
All through the production solver with condition estimation and strict
quality gates where the geometry runner is used.

## Acceptance

- H1: bitwise equality of full density and field arrays, old tree vs new.
  Any difference, however small, is reported and explained or the change is
  not accepted as "numerically neutral".
- Accuracy against Dense: density 1e-7, field 1e-8 (the limits used
  throughout), all production gates passing.
- H3: zero shortfalls above 1 MiB.
- H4, H5: as stated; one failure refutes that item.
- Unit tests of (a) with a stub system: reserved bytes after the call equal
  the bytes of the returned array, and the storage check is asked for the
  growth before the copy is made.

No timing claims unless a paired, order-alternated comparison is run.
