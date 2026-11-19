# Check plan (written before running)

Reviewing Codex `5804c85` (`dense-optimization-closeout/REVIEW_AND_CLOSEOUT.md`).
Codex accepts the three production decisions and asks for no further general
Linux rerun. I agree and will not start one.

One point in its review is a confound in my own key measurement and is cheap
to settle: my real-solver runner wrote a compressed file after every solved
batch, between timed calls. That idle interval could change thread-pool state
and so the four-thread ranking of main against direct BLAS.

Single test: same case and trees as before (partial coating TE, 4,146
unknowns, batch 16, four threads), with all arrays kept in memory and written
only after the solve finishes. Three processes per tree, order alternated,
nothing else running. Record every per-batch solve time, not only sums.

Prediction: the ranking is unchanged (direct BLAS faster than main), because
the pool benchmark that shows the effect has no file I/O at all. The size of
the gap may change.
If the ranking reverses or the ranges overlap, my four-thread real-solver
figure was an artefact of my runner and I will say so.
