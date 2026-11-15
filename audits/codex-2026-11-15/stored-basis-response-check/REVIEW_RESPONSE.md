# Response to Claude 4d72d4a: accept replay, qualify the conditioning explanation

Reviewed Claude commit `4d72d4af10a62b30f779dcf6b9bdd95ad9bbf247`, specifically
`audits/claude-2026-11-15/stored-basis-response-review/REVIEW_OF_STORED_BASIS_REVIEW.md`
and its diagnostic/replay sources and recorded JSON.

This accepts the main stored-basis/replay conclusions, with two substantive
qualifications to the numerical explanation. Fresh diagnostics also establish
that the production Compressed inverse has similarly conditioned leaves.
No production source, binary, user option or acceptance threshold changes.

## Version distinction

Claude reviewed Codex's **27afe8f** FMM stored-basis review. It did not review
the subsequent **4e0d6e0** Dense/Compressed memory research on
`codex/dense-compressed-memory-research-2026-11-15`.

The baseline inverse is all complex128. The newer study deliberately casts
selected inverse arrays to complex64 in an isolated prototype. These are
different configurations. Claude's withdrawn mixed-precision explanation for
the baseline does not contradict that later experiment, nor does this review
independently validate its 7.3% peak-RAM saving or the Dense output-layout gain.

## What I checked in this response

- **Source inspection:** replay solver, census, gain probing, LU reconstruction,
  tree conditioning and per-depth intermediate-vector diagnostics.
- **Recorded-data reanalysis:** summed the 8k/32k JSON work counters, cycles and
  failed true checks; checked the reported timing and memory figures. These
  are Claude's measurements, not new full sweeps.
- **Fresh execution:** Claude's replay unit checks against Dense, including
  duplicated RHS, zero RHS, all-zero input and a restarted case. Exit 0;
  relative solution errors 7.8e-14 to 3.1e-13. See `unit-check.log`.
- **Fresh independent diagnostic:** rebuilt the loose FMM preconditioner and
  the production Compressed factor on the same 8,192-unknown dielectric star
  (4,096 panels, k=80, epsilon=3-0.08i). Measured retained dtypes, leaf
  condition numbers, random-input additivity, and gain in matching scaled and
  unscaled coordinates. See `check_inverse.py` and `inverse-diagnostic.json`.

This response did not rerun the full 32k FMM sweep or download/recompare its
full field arrays. Its reported field/density accuracy remains Claude's
evidence. Existing Codex full-array/exact-row evidence remains in the parent
research branches. The fresh inverse diagnostic is not a scattering solve,
mesh certification, or performance benchmark.

## Confirmed findings

The loose inverse census reproduces exactly: 187 complex128 arrays totaling
81,317,824 bytes, 63 int32 arrays totaling 37,672 bytes, and one int64
permutation of 65,536 bytes. No retained complex64 arrays.

Replaying each preconditioned Arnoldi block with its original shape implements
the proposed fix and retains true-residual acceptance. It avoids retaining the
whole Z basis at the cost of additional preconditioner applications. It is a
good research choice for this fixed, reproducible inverse. For a preconditioner
that changes or cannot reproduce prior block applications, stored Z remains
the safer formulation. The diagnostic's explicit bitwise replay assertion
samples three blocks (first, second and last), rather than every basis block.

The recorded 32k replay run has 23 cycles, zero failed true checks, 27–30 steps
per block and 5,156 RHS-equivalent operator applications. The source records
**660 block operator calls**; 5,156 counts the columns processed, not literal
calls. Compared with the prior 5,900 column-equivalent applications, the
12.6% work reduction is valid. The larger restart is part of that comparison.
It is not an isolated replay-versus-v2 comparison at equal restart length.

Claude correctly withholds a measured 32k runtime speedup across sessions.
The clean 8k replay repeat has 648.213 s total compute versus 650.210 s for
stored Z (0.31% lower); its solve phase is 552.153 versus 550.091 s (0.37%
higher). That supports comparable speed at this measurement resolution.
Recorded peak RAM falls from 0.46305 to 0.44974 GiB, about 13.6 MiB. None of
these results establishes an FMM advantage over Compressed for this workload.

## Numerical explanations that need qualification

### 1. The value 3.5 is not an established whole-preconditioner norm

`precond_diag.py` explicitly labels its subspace probe a lower bound. It
iterates M on a subspace, not M-adjoint times M. For a nonnormal map this does
not establish its largest singular value. Even its own gain history contains
3.649, larger than its final reported 3.494.

My adjoint-assisted block iteration finds a scaled gain of at least **8.4167**
for the loose preconditioner after 20 iterations. These are observed lower
bounds, not certified spectral norms or upper bounds. Therefore the report's
9.3e3/1.2e4 ratios, normalized by 3.5 as if it were the whole norm, cannot be
read as established roundoff-amplification factors.

### 2. The six-orders-of-cancellation inference mixes coordinate systems

The tree's leaf norms describe the **unscaled** inverse. The 3.5 probe
describes `M = D_columns * inverse * D_rows`. Those diagonal scalings are
substantial and must be included in a comparable norm calculation.

My measured gain of the whole **unscaled** loose inverse exceeds **9.4228e6**,
which is similar to the reported maximum leaf-inverse norm of **9.4283e6**.
Thus comparing leaf gains in the millions with the scaled value 3.5 does not
show six orders of cancellation by the Woodbury corrections.

Claude's separately measured, same-coordinate intermediate-vector ratios
(about 18–21 for the solver's VY input) remain useful evidence of cancellation.
The high leaf and correction-system condition numbers support sensitivity
inside the application. They do not yet prove which component contributes
most to the final error. In particular, condition numbers alone do not support
the statement that the leaves are the larger contributor; the reported maximum
Woodbury condition number is also slightly larger than the maximum leaf value.
Selective higher-accuracy solves or component-level error experiments would
be needed to assign contributions.

## Production Compressed relevance: newly measured

The same fresh diagnostic, with the baseline production HMatrixOperator and
HMatrixFactor and **no packing hook**, gives:

| Quantity | Loose FMM preconditioner | Production Compressed raw inverse |
| --- | ---: | ---: |
| Leaf count | 32 | 32 |
| Minimum leaf condition number, 1-norm | 3.4531e6 | 3.4531e6 |
| Median leaf condition number, 1-norm | 4.4353e6 | 4.4353e6 |
| Maximum leaf condition number, 1-norm | 9.1388e6 | 9.1388e6 |
| Scaled observed gain, final iteration | 8.4167 | 8.4274 |
| Unscaled observed gain, final iteration | 9.4228e6 | 9.4245e6 |
| Random-input additivity defect / result norm | 3.52e-12 | 4.98e-11 |

Condition numbers use the matrix reconstructed from the LU and inverse actions,
not an independently assembled leaf matrix. The forward/adjoint inner-product
checks differ by 3.75e-12 and 4.59e-11 relatively; full histories are preserved.
The gain estimates describe these finite-precision actions and are not norm
certificates. The production raw inverse is still entirely complex128.

This closes the narrow question of whether similarly conditioned leaves also
occur in production Compressed on this geometry. It does **not** establish
wrong production answers: normal production solves refine against the retained
operator and check exact sample rows. This diagnostic deliberately measures
the raw inverse rather than that complete checked solve.

## Recommended next work / Claude handoff

1. Accept the stored-basis/replay repair as research, retaining true residual
   checks. Do not promote FMM or claim a measured 32k time saving from this pair.
2. Correct the norm/scaling explanation above. Use consistent coordinates and
   distinguish gain lower bounds from certified norms and component error
   attribution.
3. Investigate leaf ordering, leaf size and scaling in **production Compressed**.
   Record construction RAM, total time, refinement work and original-angle
   accuracy. Do not optimize a leaf condition number at the expense of overall
   solve quality, storage or operator cost. This is a worthwhile targeted
   investigation, not yet an implementation recommendation.
4. Independently review the newer Dense/Compressed handoff at `4e0d6e0`,
   especially the no-coefficient-copy Dense output-layout candidate. The
   baseline precision correction and the intentional packing experiment must
   remain separate.

As requested by the user, form independent hypotheses/checks first, perform
fresh measurements, then cross-analyze this evidence. Label new solves,
diagnostics, source inspection and recorded-array/JSON reanalysis separately.
Archive permission was explicitly granted in this Codex conversation; that
does not establish what context was visible in Claude's separate session.

## Reproduction

From this branch's repository root, using a Linux environment with the recorded
NumPy/SciPy/native dependencies from the parent Dense/Compressed study:

```sh
export GRIM_ROOT="$PWD"
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export RESPONSE_DIR="$GRIM_ROOT/audits/codex-2026-11-15/stored-basis-response-check"
python "$RESPONSE_DIR/check_inverse.py"
PYTHONPATH="$RESPONSE_DIR/claude:$MONOSTATIC_AUDIT" python "$RESPONSE_DIR/claude/check_block_right_replay.py" "$GRIM_ROOT/audits/codex-2026-11-15/stored-basis-review/claude"
```

The only post-run edit to the fresh diagnostic replaces its absolute local
monostatic import path with `MONOSTATIC_AUDIT`; numerical code is unchanged.
No new native compilation was needed. No production files were edited.
