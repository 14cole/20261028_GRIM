# Inverse-upgrade lifecycle repair

Baseline `cbcf3bff24f6ab392d38a576187cfb2a23fbad20`; reviewed Claude
`ecc046c21a480c5534e32f987e05f013bda84271`.
One production file changes: `tools/GHOST/ghost_backend/compressed/factor.py`.
Gather v2 and sequential construction remain separate research proposals.

Create separate baseline and fixed checkouts. Then:

```sh
export GRIM_ROOT=/absolute/path/to/fixed/repository
export BASE_GRIM_ROOT=/absolute/path/to/baseline/repository
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$GRIM_ROOT/audits/codex-2026-11-16/inverse-upgrade-lifecycle"
python test_upgrade_lifecycle.py
python run_suite.py suite_lifecycle.json
python analyze.py
python review_records.py
```

Run in a fresh results directory; the suite refuses overwrites. Ten fresh
processes produce 41 complete field-solve results. All process return codes
must be zero. The cancel case deliberately aborts one build and recovers.
The hint and tightening cases inject one fault to exercise the corresponding
production branch; they do not relax any acceptance gate. The physical suite
uses the actual production build order and gather implementation.

For Claude's unchanged original reproduction, use a separate working directory
containing `gather_v2.py` and an `out` directory, set `GRIM_ROOT` to the baseline,
and run `claude/claude_slot_attribution.py` with this audit on `PYTHONPATH`.
Its published script installs gather v2; our separate lifecycle suite does
not, demonstrating that the issue and repair do not depend on that proposal.
The original rerun is preserved in `out/slot_attribution.json` and its log.

Replay complete new numerical evidence without solving:

```sh
python unpack_evidence.py /tmp/upgrade-lifecycle-replay
RESULTS_DIR=/tmp/upgrade-lifecycle-replay/results ANALYSIS_OUT=/tmp/upgrade-analysis.json python analyze.py
```

The archive preserves every density, RHS, field and sampled-row array, along
with all raw outcomes. NPZ container bytes need not be identical; array bits
and C/F layouts are verified. Baseline/fixed comparisons distinguish ordinary
rebuilds, operator tightening and intentionally suppressed hint fallback.

The code change affects a private build method, not user-facing options.
After a successful ordinary fresh build it permits one optional upgrade
again; the rejected-hint fallback requests `allow_upgrade=False`. Successful
upgrades still require the existing payload and live-RAM admission checks.

Claude should independently reproduce the lifecycle, challenge the rejected
hint and cancellation cases, then compare complete arrays and state records.
The supplied nine focused tests use controlled builders/headroom for state
transitions; the separate physical suite provides native numerical checks.
