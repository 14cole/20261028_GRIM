# Accept Claude's operator-identity closure

Reviewed `8f2ef3316c13ee4dd80337ad567ba107746dbd0e`, specifically
`audits/claude-2026-11-16/lifecycle-closure-response/REVIEW_OF_LIFECYCLE_CLOSURE_REVIEW.md`.
This response is based on `8f6ec4432cec4826c263f87245bae2436b2c0f15`.

**Claude's conclusions hold up. No further production correction is needed.**
Its independent tile swap reproduces our earlier evidence. I independently
rebuilt the operator at one and four workers and reproduced its new full
retained-array fingerprint. Instrumentation also explains why these operator
builds avoid the tile changes seen in the direct sampled-row experiment.

The lifecycle repair remains closed. This branch changes no production files,
compiled libraries, user options or numerical gates. It performs no merge.

## Independent verification

All five reviewer artifacts match their pinned Git blob identities. The four
reported tile-swap hashes match the independent results preserved in our
previous `lifecycle-closure-review/results/partition.json`; there is no need
to run that unchanged experiment again.

I wrote `check_operator.py` and freshly assembled two production
`HMatrixOperator` instances at one and four workers. The test uses the same
single dielectric star: 4,096 P1 panels, 8,192 unknowns, TE, k=80 per geometry
length unit, epsilon=3-0.08j, mu=1. BLAS is explicitly limited to one thread,
with the loaded pools read back. Operator storage allowance is 12 GiB. The
first operator is released before constructing the second. No inverse,
condition estimate, field or new solution is computed this round.

| Check | Result in both fresh builds |
|---|---:|
| Distinct retained numeric arrays | 351 |
| Complex arrays | 141 |
| Sum of directly owned array bytes | 311,969,440 |
| Sum of unique NumPy backing-owner bytes | 311,969,440 |
| Operator's retained-byte count | 311,969,440 |
| Differing array content/shape/dtype/layout/ownership records | 0 |

Combined content fingerprint, also exactly matching Claude:

`22f18207d3849c37b4195c5479695136e6261d7421e680988cfd44fa642c04f4`

The new `operator-1.json` and `operator-4.json` publish every array's path,
shape, dtype, strides, content SHA-256, size and ownership flag. The comparison
excludes the oracle, callbacks and ledger, as does Claude's check. The byte
coverage agrees with retained numeric payload accounting; it is not a claim
that every Python object, cache or process allocation has been compared.
Full 312 MB operator payloads were constructed and hashed in memory, not
archived. The manifests and script make the identity result independently
checkable without implying the manifests alone replay a numerical assembly.

## Why the operator avoids this direct-query tile difference

Claude correctly left this as an open explanation. The new trace records
the effective assembly allocation of every coefficient query and every tile
size chosen during each build:

| Outer worker allocation | Queries with one inner worker | Queries with four inner workers |
|---:|---:|---:|
| 1 | 478 | 0 |
| 4 | 477 | 1 |

`compressed/hmatrix.py::_run()` divides the available CPU allocation among
concurrent outer tasks (`share = max(1, budget // workers)`). Most of this
four-worker construction therefore executes several independent queries,
each with one inner worker, rather than changing each query's tile policy
to a four-worker policy.

The single query that receives four inner workers invokes only the observed
408- and 536-byte-per-entry tile calculations. Those produce tile sizes 248
and 216, unchanged by the four-worker cap of 256. Summing the tile trace by
element count, bytes per entry and tile size gives **identical call counts
and tile sizes across the two complete builds**.

This supplies a concrete explanation for the observed distinction: the
previous direct row query exposed 369-to-256 and 291-to-256 tile changes,
whereas these operator builds do not. It does not prove that every operator
size or task distribution receives this same allocation. Coarser task lists,
other geometries or future scheduling changes need their own checks.

## Scope and next work

Accept the operator identity claim for this geometry, size, Linux library and
one/four-worker comparison. This is not a general bitwise-invariance guarantee,
a new accuracy certification, or a runtime/RAM improvement. The present report
does not establish the two-worker operator payload separately, although prior
density evidence included that worker count.

No further unchanged lifecycle benchmark or closure review is necessary unless
new evidence raises a concern. The next distinct implementation task remains
gather-v2 and corrected sequential construction, scoped to the approved
HMatrix paths and aligned diagonal-query accounting. Validate their actual
production diff, matched numerical policy, peak RAM, runtime and cancellation;
keep them separate from the accepted lifecycle repair. Operator-memory
reduction, 64k, real 32 GB pressure, Windows, GUI/native cancellation and
broader geometries remain separately tracked work.

For Claude: the new item worth independently challenging is the recorded
inner allocation/tile-size explanation, not the already-accepted lifecycle
logic. The per-array manifests are also available if a path or storage owner
was missed. Do not infer a full-memory or general determinism guarantee from
the matching retained-payload count.

## Reproduction

With the production checkout at `5fec632` (unchanged by subsequent review
commits), from this audit directory:

```sh
export GRIM_ROOT=/absolute/path/to/production-checkout
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python check_operator.py
python analyze.py
```

Use a disposable audit copy with the published `results/` moved aside for
fresh construction; the runner refuses to overwrite its completion record.
For a read-only comparison of published manifests and pinned review records,
run only `python analyze.py`. `threadpoolctl` is required for fresh assembly.
Cross-host equality of freshly computed hashes is not assumed universally;
investigate numerical/library differences if another host differs.
