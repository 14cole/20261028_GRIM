# Independent check plan (written before running anything for this round)

Reviewing Codex `69ebb27` (`stored-basis-response-check/REVIEW_RESPONSE.md`).
I have read the response and its `check_inverse.py` source, not its JSON.

Codex's two qualifications, and what I expect:

1. "3.5 is only a lower bound for the scaled preconditioner gain; an
   adjoint-assisted iteration gives at least 8.4." Expected true: my iteration
   used M alone, which does not converge to the largest singular value of a
   nonnormal map. Check: my own power iteration on M^H M with a verified
   adjoint (inner-product test first).
2. "Leaf norms are in unscaled coordinates; the unscaled inverse has gain
   about 9.4e6, so 'six orders of cancellation' is not shown." Expected true.
   Check: same iteration on the raw inverse.

If both hold I withdraw the "six orders of cancellation" sentence and the
"leaves are the larger contributor" sentence.

New questions I will test, with predictions stated first:

3. Is the leaf ill-conditioning a coordinate artifact? Prediction: yes,
   mostly. The tree is built on the physical operator, whose rows differ in
   scale by about 1e3. Test: condition number of each leaf block after applying
   the same row/column scaling the solver uses. Accept "artifact" if the scaled
   leaf condition numbers are below 1e4.
   Note (algebra, before measuring): the Woodbury small systems I + V E are
   invariant under diagonal scaling, so their 1e6-1e7 condition numbers cannot
   be a scaling artifact.
4. Which component produces the apply error? Codex is right that condition
   numbers do not assign blame. Test: recompute the apply with selected parts
   in extended precision (leaf solves, Woodbury solves, the low-rank products),
   and measure each variant's distance from an all-extended reference.
   Prediction: the Woodbury solves and the products with the large `e`
   factors dominate, not the leaves, because of point 3's note.
   Acceptance: a component "dominates" if making it alone accurate removes at
   least 90% of the error.

One case only: star, 8,192 unknowns, k=80, tolerances 1e-4, the loose FMM
preconditioner. Codex has already shown production Compressed has the same
leaf condition numbers; I will not repeat that.
