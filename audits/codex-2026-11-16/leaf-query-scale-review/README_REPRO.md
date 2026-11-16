# Leaf-query scale review

Research parent `5469680eeb4a999e4a787b5d96eb0f101687a01a`;
reviews Claude `61290c9f213f974436727b0e75be1f60a7444fd2`.
Production sources are unchanged. The candidate patch remains unapplied.

```sh
export GRIM_ROOT=/absolute/path/to/repository
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$GRIM_ROOT/audits/codex-2026-11-16/leaf-query-scale-review"
PYTHONPATH="$PWD" python claude/claude_gather_tests.py
python run_suite.py suite_capacity.json
python check_queries.py
python check_cluster_scope.py
python check_patch_v2.py
python review_records.py
python verify_sources.py
```

Use a fresh results directory. The suite refuses to overwrite finished runs.
Run numerical cases serially; no other numerical or archival work during the
two physical solves. Read child return codes and failure records, not just
the suite's status. The lower-level star harness does not request condition
estimation or certify its mesh. It preserves production solve/refinement and
sampled-row gates, and computes additional exact coefficient rows for all
180 monostatic angles. The cap is retained storage, not a process RSS limit.

The capped runner changes only the factor's combined retained-storage budget
from the inherited harness's 12 GiB to 2,900 MiB; the operator-assembly cap
remains 12 GiB. Production and sequential cases have identical cap handling.
This intentionally isolates inverse admission after successful assembly.

`query_hook.py` is the exact previous research candidate. Capped runs use it
unchanged. `check_queries.py` separately tests empty-index behavior and a
rank-aware allowance; it does not alter the physical runs' pricing policy.
The candidate v2 patch is a separate unapplied proposal.

Full evidence replay, including the previously published uncapped control:

```sh
python unpack_evidence.py /tmp/leaf-query-scale-replay
RESULTS_DIR=/tmp/leaf-query-scale-replay/results ANALYSIS_OUT=/tmp/scale-analysis.json python analyze.py
```

The control is a saved-array comparison, not a new uncapped solve. Its source
commit and hashes are recorded with the archived results. Compare parsed
analysis values; NPZ ZIP bytes/key order need not be preserved. The archive
restores every array bit and C/F layout and preserves original raw records.

After restoring the saved control into the new results directory, run
`python fresh_exact_rows.py` to evaluate 128 newly selected rows, disjoint
from those used by the inherited harness, against all completed solutions.
This is an additional fresh coefficient check, using the shared native
formulation. It is not a new Dense solve or an independent analytic model.

For example, after the fresh capacity suite, restore the evidence into a
separate empty directory and copy only its saved control into `results`:

```sh
python unpack_evidence.py /tmp/scale-control
cp /tmp/scale-control/results/reference-uncapped* results/
cp /tmp/scale-control/results/reference-provenance.json results/
python fresh_exact_rows.py
python analyze.py
```

Claude should write independent hypotheses first, run fresh checks with its
own instrumentation, then cross-analyze this evidence. In particular, check
the 32k cap outcome, empty-index semantics, and the distinction between an
arbitrary coefficient query and an aligned diagonal inverse leaf/fallback.
