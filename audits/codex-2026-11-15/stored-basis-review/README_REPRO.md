# Reproduce the stored-basis review

The parent branch contains the original monostatic harness and its full Dense
reference archive. The reviewed Claude commit is
`0328f1fde93a63062ea9938cfff154a8893b2730`. Its v3 and stored-Z solver sources are
copied unchanged under `claude/`; `run_case.py` selects one in memory without
editing production code. Source hashes and environment details are recorded
beside the final report.

Set paths from a checkout containing this response:

```bash
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
(cd "$MONOSTATIC_AUDIT" && python unpack_arrays.py restored)

# From this response's directory: restore and verify all local-run arrays.
python unpack_arrays.py restored
RESTART_RESULTS="$PWD/restored/results" \
  RESTART_ANALYSIS="$PWD/replayed-analysis.json" python analyze_results.py
python check_independent.py
PYTHONPATH="$MONOSTATIC_AUDIT" python claude/check_block_right_z.py "$PWD/claude"
python check_fresh_rows.py
```

The copied Claude density archives are already stored under `claude/densities/`.
They contain full densities, fields and row-validation arrays, with RHS at the
sample rows. Their declared hashes are checked during analysis. The fresh-row
script regenerates 16 disjoint exact coefficient rows and original RHS for the
supplied 32k/24 solution. It does not run another 32k solve.

To rerun physical benchmarks, copy this directory's source, suite files and
`claude/` into a separate working folder with no `results/` directory, then:

```bash
(cd "$MONOSTATIC_AUDIT/research" && python build_pair_kernel.py)
python run_suite.py
python run_suite.py suite_extra.json
python analyze_results.py
```

Run all numerical commands serially with no other numerical jobs. The main
suite runs one instrumented eight-angle diagnostic, a full 180-angle v3 control,
a full stored-Z sweep, and square/slot TE/TM stored-Z checks. The extra suite
runs a fresh 8k Compressed control. Runners retain stdout/stderr and return codes,
and refuse to overwrite an existing timing record. Times are single observations.

`diagnostic_solver.py` is an instrumented v3 copy that retains both the
preconditioned basis and its accurate operator images. At each candidate it
evaluates both reconstruction formulas and measures the equation effect of their
difference. Extra diagnostic operator calls are not included in the original
work counters, and extra stored vectors are not included in its original
capacity counter. Exclude this diagnostic from timing/work/memory comparisons.

`analyze_results.py` compares every fresh FMM/Compressed field and density with
the archived Dense references at matching angles, recomputes row backward errors,
checks the physical RHS, and compares the fresh 8k solutions with Claude's newly
published v3 density. Its canonical array layout makes archived replay stable.
`check_independent.py` tests new random dense systems with both double and
deliberately single precision preconditioner arithmetic; the latter is a
controlled synthetic example, not a description of the physical inverse.

The full local arrays use the earlier lossless deduplication/XOR/LZMA archive
format. Part hashes, payload hashes and every reconstructed array hash are
verified. `archive-verification.json` records the additional local byte-for-byte
comparison with the original NPZ numerical arrays. ZIP packaging bytes and memory
layout may differ after restoration; numerical array bytes in C order do not.

These are 2D single-interface dielectric research cases with unchanged accuracy
gates, not mesh/condition certification, distribution benchmarks or evidence of
a full 32k stored-Z sweep. No production code or shipped native library changes.
