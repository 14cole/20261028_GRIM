# Sequential-builder review reproduction

Research only, parent Codex commit `79618d58db7351fac5580c5c6bd5529d0e91eb4e`.
Reviews Claude commit `b0e2ba064d6b6d02d6682fac9f35947d3d2fcb38`.
No production source, binary, acceptance threshold or user option is changed.

Use production NumPy/SciPy/native dependencies and absolute paths. For fresh
runs use a checkout with no existing `results` directory; the suite runner
refuses to overwrite timed cases. Run the two suites sequentially.

```sh
export GRIM_ROOT=/absolute/path/to/repository
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$GRIM_ROOT/audits/codex-2026-11-15/sequential-builder-review"
python check_scratch_guard.py
python run_suite.py suite.json
python run_suite.py suite_reference.json
python check_builder.py '{"packing":"none","out":"builder-check-none"}'
python check_builder.py '{"packing":"bounded","out":"builder-check-bounded"}'
python analyze.py
python verify_sources.py
```

`claude/` holds pinned source and selected raw records. `claude_builder.py`
in this directory is also the exact original. `corrected_builder.py` is an
isolated research copy that restores conservative child-solve scratch,
charges live correction matrices across intervening operations, and guards
the optional input copy. `rank_guard.py` optionally adds per-rank-vector
conversion bounds. All physical cases use leaf scaling disabled; its code
is inherited for source comparison, not accepted or validated here.

`observations.py` counts refinement per call/phase and observes live-array
arguments. Tolerance overrides apply only to explicitly labeled research
cases. No residual or condition acceptance gate is relaxed.

The synthetic check tests exact normal, transpose and adjoint solutions,
input/output aliasing, duplicate/zero RHS, zero-rank recursion, forced dense
fallback, forced read-only input copies, and reference release after injected
cancellation or allocation failure. It is not a real RAM-pressure test.

For archive replay without new solves:

```sh
python unpack_evidence.py /tmp/sequential-builder-replay
RESULTS_DIR=/tmp/sequential-builder-replay/results ANALYSIS_OUT=/tmp/sequential-builder-analysis.json python analyze.py
```

All complete densities, RHS, fields and raw run records are restored from
the archive. Hashes verify array bits; NPZ ZIP bytes need not match. Both
Dense anchors were freshly solved in this round. The geometry generator is
shared with the prior studies, and the mesh is not convergence-certified.

For Claude: first write independent hypotheses and acceptance criteria,
run independent fresh checks, and then cross-analyze these results. Label
fresh solves, allocation measurements, exact matrix checks, archive replay,
source inspection and quoted numbers separately. Prioritize the live-RAM
accounting corrections and the per-call refinement interpretation.
