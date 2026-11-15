# Reproduction

This branch contains a review response, fresh research tests and evidence only.
The reviewed Claude commit is `e5883eed97dc97651f9ad0b453e47891dc130f5d`.
`claude/block_gmres_right.py` is copied unchanged from that review and depends
on `_basis` in the previous Codex audit. Claude's original result JSON and
field archive are supplied for replay; its unpublished densities are not.

From this directory, with dependencies and native libraries from the repository:

```bash
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

# Restore prior Dense references, if not already restored:
(cd "$MONOSTATIC_AUDIT" && python unpack_arrays.py restored)

# Restore this response's four NPZ files (three new full-array cases plus
# Claude's field/row archive), verifying all SHA256 hashes:
python restore_evidence.py
python check_review.py
python check_physical.py
```

`check_review.py` replays all 11 Claude field comparisons, checks logged work
counts and acceptance, and runs independent small-system tests. It writes
`review-checks.json` and `original-check-replay.json`; small-test timing values
will vary. `check_physical.py` checks the complete new fields/densities/RHS
against the original Dense references and recomputes sampled backward errors.

To obtain **new** numerical timings, copy this directory's scripts and `claude/`
to a separate working directory, leaving `reproduced/` absent, and run:

```bash
(cd "$MONOSTATIC_AUDIT/research" && python build_pair_kernel.py)
python run_physical.py
python check_physical.py
```

The runner refuses an existing `.time.json`, runs three fresh child processes
serially, and retains stdout/stderr and return codes. It uses the original
`monostatic.py` harness with only the research block-solver function replaced
in memory. Production files are not edited. Set `MONOSTATIC_AUDIT` and
`GRIM_ROOT` to the same reviewed checkout to avoid mixing implementations.
The published `.time.json` records use `returncode`, not the older runner's `rc`.

Fresh physical cases are square TE, thin slot TE and thin slot TM, each with
512 panels / 1,024 unknowns, 180 angles from -90 through 89 degrees, k=10,
epsilon=3-0.08i, preconditioner tolerances 1e-4 and Krylov width 8. Both
assembly and BLAS use one thread. The original harness supplies the exact
geometry, quadrature, projection, tolerances and validation rows.

The checks do not rerun Claude's 8k/32k timing measurements. In Claude's reduced
archive the density/RHS norms needed to recompute exact-row backward error are
missing; the raw row residuals cannot independently establish those bounds.
The three new cases include the full arrays needed for both density comparisons
and sampled backward-error replay. These are algebraic checks, not production
condition or mesh certification.
