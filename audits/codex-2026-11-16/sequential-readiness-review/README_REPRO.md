# Sequential readiness review

Parent: `9da795ece4e5abeaf91cf711efb5033d7e223b1f`.
Reviewed Claude: `6149db0a48744bae3e870661979efbd46c451773`.
Research only: production files, defaults and numerical gates are unchanged.

```sh
export GRIM_ROOT=/absolute/path/to/repository
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$GRIM_ROOT/audits/codex-2026-11-16/sequential-readiness-review"
PYTHONPATH="$PWD" python claude/claude_gather_v2_tests.py
python check_actual_patch.py
python run_suite.py suite_readiness.json
python analyze.py
PYTHONPATH="$PWD" python claude/claude_diagonal_queries.py diagonal-rerun.json
python verify_sources.py
```

Run the suite in a fresh results directory. It refuses to overwrite finished
runs. Every child must return zero. The cancellation cases deliberately
abort one inverse build, verify cleanup, then recover and complete a solve.
These are cooperative Python-checkpoint tests, not GUI cancellation tests,
forced process termination, or cancellation inside a stalled native call.

Both Compressed controls use gather v2 and the scoped `4q+1 MiB` diagonal
query declaration. The tested difference is original versus corrected
sequential HMatrix build order, at one and two requested assembly threads.
BLAS stays at one thread, as production HMatrix construction requires.
Condition estimation is explicitly requested; all 180 field columns and
96 fresh exact coefficient rows are checked. No mesh certification is claimed.

Replay complete new arrays without solving:

```sh
python unpack_evidence.py /tmp/sequential-readiness-replay
RESULTS_DIR=/tmp/sequential-readiness-replay/results ANALYSIS_OUT=/tmp/readiness-analysis.json python analyze.py
```

To independently cross-check the reviewer publication, first restore the
previous `leaf-query-scale-review` evidence into `/tmp/prior-scale`; then:

```sh
PRIOR_RESULTS=/tmp/prior-scale/results python check_review_evidence.py
```

This rehashes the complete prior arrays and checks all newly published
fields/row data. It uses our already published full densities, rather than
rerunning Claude's two-part reconstruction script. The checked digests agree
with its manifest. Pinned reviewer files are Git-blob verified, including
the six NPZ files; see `source-provenance.json`.

For the next review, write independent hypotheses first, run fresh checks,
then cross-analyze the attached arrays and records. Distinguish this round's
seven fresh physical solves and three fresh operator-allocation scans from
the replay of previous 32k arrays and Claude's repeated timing measurements.
