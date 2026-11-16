# Reproduce this review

Pinned Claude review: `632cbcfe4509d4fc002859972059035f8fa08e1d`.
Original production: `cbcf3bff24f6ab392d38a576187cfb2a23fbad20`.
Repaired production: `5fec63200d48d6dd7536221d992b3e1836a1647c`.

For a read-only replay of the published records and saved arrays, from this
audit directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analyze.py
```

For fresh computations, use a clean copy of this audit directory with its
`results/` directory moved aside. The runner refuses to overwrite results.

```sh
export BASE_GRIM_ROOT=/absolute/path/to/cbcf3bf-checkout
export GRIM_ROOT=/absolute/path/to/5fec632-checkout
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
python run_checks.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analyze.py
```

The runner executes the pinned Claude harness unchanged. It saves raw stdout,
stderr, return codes, records and the first/stable density/RHS arrays. Other
sequence comparisons are recorded by that harness at runtime; no complete
far-field arrays are produced. Exact equality with Claude's numerical records
is asserted by `analyze.py` because that is what this host reproduced; investigate
rounding differences rather than assuming this equality on every platform.

`source-provenance.json` pins every imported Claude artifact by Git blob hash.
`verification.json` records the executed source identities and parse checks.
