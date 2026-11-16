# Reproduce the closure review

Production checkout: `5fec63200d48d6dd7536221d992b3e1836a1647c` (unchanged by
the following review commits). Imported Claude artifacts are pinned in
`source-provenance.json` to `847373321c86619d6e668ca61cd4de863b103ef4`.
Older star controls came from `632cbcfe4509d4fc002859972059035f8fa08e1d`;
`analyze.py` verifies their exact Git blob identities too.

Replay the published evidence without any assembly:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analyze.py
```

For fresh coefficient assembly, first move `results/` aside in a disposable
copy of this audit directory. Scripts refuse to overwrite completed results.
Install the repository's numerical dependencies and `threadpoolctl`, then:

```sh
export GRIM_ROOT=/absolute/path/to/5fec632-checkout
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python check_rows.py
python check_partition.py
python check_grading.py
python analyze.py
```

These are coefficient-query experiments using saved densities, not fresh
solves. The first script explicitly controls and verifies loaded BLAS pools.
The partition script temporarily overrides tile policy in its own process;
the grading script changes an execution option in its own process. Neither
edits production files. Do not use diagnostic per-query times as a speedup
benchmark. Exact cross-host hashes are observations on this library build;
investigate platform-dependent rounding if replaying fresh assembly elsewhere.

Every changed coefficient value and index is preserved with the complete
computed residuals. Unchanged coefficient entries are represented by full
matrix hashes and reproduction commands, not stored full matrices. Saved
first/stable solution arrays from Claude are included in `claude/`.
