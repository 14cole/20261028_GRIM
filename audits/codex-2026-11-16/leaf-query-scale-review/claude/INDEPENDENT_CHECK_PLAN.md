# Independent check plan (written before running anything for this round)

Reviewing Codex `5469680` (`leaf-query-review/REVIEW_AND_HANDOFF.md`).
Read so far: that document, `candidate-gather.patch`, `query_hook.py`, and
the production `BlockRow` class and its three call sites. Not opened: Codex's
check scripts or results.

## 1. My own statement that Codex corrected

"Outside that window the two builds behave identically" was too broad. Codex
predicts and reports that at 650 MiB production's retry is rejected and the
sequential retry is admitted. I expect this to reproduce: the retry inverse
has its own construction transient, which the sequential order also removes.
Check with my instrumentation (build attempts, corrections per phase).

## 2. Gather patch: exact behaviour

Source reading before testing:
- `BlockRow.values` has three callers. Two pass `(None, slice)` and cannot
  reach the new branch. The third, `_get_positions`, passes two 1-D integer
  arrays and adds the result into another array with `+=`.
- So only values, shape and dtype matter there; layout and ownership of the
  returned array cannot affect results.
Tests (own, written before reading `check_query.py`): randomised comparison of
original and patched `values` over index dtypes (int32, int64, uint32),
repeats, negatives, empty, unsorted; C-order, F-order and strided `u`;
complex128 and complex64 `u`; boolean and list selectors and slices (must take
the old path); the low-rank path (must be untouched). Compare values
bitwise, dtype, shape, and report flags (C/F contiguity, owns data, writeable)
even though the caller does not depend on them.
Acceptance: bitwise-equal values, same dtype and shape, in every case; any
flag difference is reported, not hidden.

## 3. Workspace contract for the leaf query

My analysis before measuring: `_get_positions` holds the q-byte result, and
for each contributing block row a gathered chunk, the fancy-index temporary of
`result[ix]`, and their sum. For a dense row covering the whole query that is
about 4q, which matches Codex's `4q + 1 MiB`.
Predicted gap: the low-rank path computes `u[rows] @ v[:, columns]`. Its
operands are `rank x (rows + columns)`, which is not bounded by q when the
stored rank exceeds the query side. So a rule that is a multiple of q alone
cannot be a general bound.
Test: synthetic low-rank block rows with rank above and below the query side;
measure traced peak of a full query against `2q` and `4q + 1 MiB`.
Then check whether this matters physically: record the largest stored
operator rank against leaf size at 8k-unknown multilayer and at 32k star.

## 4. Scale: sequential build at 32,768 unknowns

Codex asks for 32k/64k before promotion. One 32k dielectric star, production
build against Codex's corrected sequential build:
- densities and fields bit-identical (prediction: yes);
- accounted inverse high-water and final size (prediction: sequential
  high-water equals its final size when unpacked, as at 9.5k);
- allocation audit shortfalls by guard label, with the original query and
  with direct gather plus Codex's pricing;
- process peak (prediction: no meaningful change).
Runs are traced, so no timing claims. 64k is not planned: it needs about
12 GiB here and would leave no margin under tracing.

Acceptance for "holds at 32k": bit-identical solution, zero shortfalls above
1 MiB outside the leaf-query label, and the predicted high-water relation.
