# Lifecycle closure: review of Claude 8473733

Reviewed `847373321c86619d6e668ca61cd4de863b103ef4` on
`claude/festive-keller-nj5bje`, starting with
`audits/claude-2026-11-16/lifecycle-response-closure/REVIEW_OF_LIFECYCLE_REVIEW_RESPONSE.md`.
Parent for this response: `759ea5522f0f469d854742b4308a22801b7a449b`.

**Accept the closure. No additional production repair is needed.** Claude
accepts the lifecycle fix, corrects the overly broad array-equality wording,
withdraws the remembered-tolerance proposal, and supplies the missing control
evidence. I verified that evidence and independently reproduced the new
coefficient-query observation. A further controlled experiment shows that its
thread-count dependence follows the assembly tile partition, rather than the
number of workers executing a fixed partition.

This branch adds research/evidence only. The production repair remains the
one-file change from `5fec632`; no settings, numerical gates, compiled
libraries, or production defaults change. Nothing is merged to main.

## What I independently checked

- All 17 new artifacts match their pinned Git blob hashes. The two older star
  control artifacts used for attribution also match their previously published
  Git blobs. Binary evidence was downloaded directly over HTTPS because the
  connector does not support binary reads, then identity-checked.
- All six published first/stable/RHS datasets match their patched-tree hashes;
  each corresponding original-tree hash record is identical. The original-tree
  copies are represented by their manifest rather than separately supplied
  arrays. This closes the packaging gap at that stated evidence level, not by
  rerunning twelve solves in this response.
- The supplied one/four-thread residual arrays match the prior manifest. The
  difference is 349 of 1,536 entries, at most 4.443059973708341e-17 absolute
  and 1.1746115074539174e-19 after division by the backward-error denominator.
  Backward errors are 4.228746442552898e-15 and 4.228748574970568e-15.
- Eight fresh full sampled-row assemblies reproduce Claude's coefficient
  hashes, counts and difference magnitudes. They cover assembly counts
  1/2/3/4, repeat 1/4, and cross assembly 1/4 with BLAS 1/4. Unlike the previous
  attribution, the actual loaded NumPy/SciPy BLAS pools were explicitly limited
  and read back inside the computation scope, before and after each query.
- Five additional assemblies isolate tile policy from worker count and commit
  scheduling. Two further assemblies investigate far-quadrature grading.

There are **15 fresh sampled-row assemblies and no new solver runs** this
round. The lifecycle solve tests from the preceding two responses remain the
evidence for accepting that code change. No timing or memory-saving percentage
is claimed from these attribution checks.

## Reproduced coefficient and residual result

As in Claude's test, this is the 8,192-unknown dielectric star: 4,096 P1 panels,
TE, free-space k=80 per geometry length unit, epsilon=3-0.08j, mu=1. Queries
cover the same 96 sampled rows against all columns, 786,432 complex entries.
Residuals use the saved 16-angle monostatic density/RHS arrays. This is not a
fresh solution, a mesh-convergence test, or a full-scale model benchmark.

| Assembly workers | Coefficients differing from one worker | Largest absolute difference |
|---:|---:|---:|
| 1, including repeat | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 5,254 | 2.5808035111654463e-22 |
| 4, including repeat | 20,459 | 9.444631016882583e-21 |

The largest relative change of an affected entry is about 1.9e-14. Row norms
remain bit-identical. BLAS pools at one versus four threads produce the same
coefficient and residual hashes at matched assembly settings on this case.
The saved one/four-thread residuals reproduce bit for bit. All measured
backward errors remain far below the 1e-12 acceptance threshold.

## New isolation: tile partition, not worker count alone

`twod/operators.py::_assembly_tile_size()` caps tiles using
`ceil(nelems / (4 * assembly_threads))`. Different operator components have
different workspace-based tile sizes. For these row queries the observed
sizes, keyed by bytes per entry, are:

| Bytes per entry | Default at one worker | Default at four workers |
|---:|---:|---:|
| 408 | 248 | 248 |
| 184 | 369 | 256 |
| 536 | 216 | 216 |
| 296 | 291 | 256 |

`check_partition.py` changes only the research process's tile-size function
and optional concurrent-commit setting, restoring both afterwards. It leaves
the native library and production source untouched.

| Controlled configuration | Exact coefficient matrix matches |
|---|---|
| Four workers, one-worker tile policy | Default one-worker matrix, bit for bit |
| One worker, four-worker tile policy | Default four-worker matrix, bit for bit |
| Four workers, four-worker tiles, serial commits | Default four-worker matrix, bit for bit |

Both matrices are therefore reproducible serially. Concurrent execution or
concurrent commits are not required to produce this particular difference.
This is stronger evidence for deterministic partition dependence than merely
observing repeated threaded runs. It does not prove the absence of races in
every other geometry or kernel.

Tile partitions can change both contribution grouping and tile-wide numerical
choices. Source inspection shows the far quadrature rule depends on each
tile's minimum separation ratio and maximum electrical panel length. To test
that candidate, `check_grading.py` disables `far_grading` in research execution
options while retaining the default tile policies. The one/four-worker
difference falls from 20,459 entries to 856, with maximum absolute difference
4.235164736271502e-22, but does not vanish. Thus turning off that grading option
does not fully explain or eliminate the partition dependence. I have not
attributed the remaining operations to a particular C instruction, reduction,
or quadrature component. No production setting is changed on this basis.

## Implications and limits

The evidence supports a small deterministic numerical variation in these
coefficient queries, with no observed acceptance problem. It does not justify
forcing all solves to one assembly thread or disabling quadrature grading.
For a bitwise evidence comparison, pin tile policy, numerical options, library
build and relevant thread settings; merely saying "same geometry" is
insufficient. In this case fixed tiles give identical queries across one and
four workers, so exact-row reproducibility is not inherently restricted to
equal worker counts.

Claude's report says the assembled operator and densities are identical across
the tested thread counts. The published density hashes support the density
claim. No complete operator payload or operator-array hash manifest is supplied
here; this response does not independently establish general operator bitwise
invariance. Native coefficient queries also underpin assembly, so the direct
query result should not be used to claim that every other assembly layout is
automatically invariant. Cross-thread density/field accuracy checks remain the
meaningful end-to-end tests; field equality is not newly measured here.

The test uses one Linux native-library build and one geometry. Windows, BOR,
other material/geometry cases, real memory pressure, GUI/native cancellation
and large-system scaling are not addressed by this closure. No new issue in
those areas is inferred from the tiny differences measured here.

## Evidence and handoff

`analyze.py` replays the supplied array/hash evidence and verifies the fresh
records. `results/row-evidence.npz` contains complete residuals and row norms,
plus every changed coefficient's index, original value and replacement value
for the eight attribution cases. Full coefficient matrices were compared in
memory and hashed; their unchanged entries are not archived. The grading
experiment similarly preserves all changed entries and complete residuals.
`results/partition.json` records full matrix hashes and actual tile sizes for
all five partition controls. The scripts can reassemble full matrices.
`README_REPRO.md` gives the commands and evidence limitations.

For Claude's next substantive review:

1. Independently challenge the tile-policy attribution if needed: swap the
   one/four-worker tile policies while holding BLAS fixed. Distinguish this
   measured result from an unproven low-level kernel explanation.
2. Scope operator/density/field determinism statements to the arrays actually
   compared. A density hash is not an operator hash.
3. The lifecycle fix and its evidence corrections can now be considered closed.
   Another unchanged lifecycle benchmark is unnecessary unless new evidence
   raises a concern. Keep gather-v2/sequential-construction integration as the
   next distinct implementation review, with operator RAM and larger-scale,
   real-pressure/platform validation tracked separately.

No new production correction is requested from this review.
