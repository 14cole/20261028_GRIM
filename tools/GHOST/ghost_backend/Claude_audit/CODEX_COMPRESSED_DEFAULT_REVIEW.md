# Review request: compressed default, dense override

The user prefers compressed for ordinary 2D runs and dense only when explicitly selected. The measured per-solve savings do not approach five minutes in the examined comparisons.

Review `Codex_audit/compressed_default_20261029/README.md`, `airfoil_comparison.json`, and `validation_summary.json`, plus the working-tree patch against 5460aa2.

Changes are in execution/options.py, runs/controls.py, runs/exploratory.py, ui/twod_options.py, and the three monostatic driver parameter scripts. Tests cover defaults, GUI/driver/worker handoff, numerical equivalence and fixed-backend certification. New regressions are in tests/test_compressed_defaults.py.

Please concentrate on:

1. Default compressed behavior at public API, GUI, local script, HPC worker and exploratory entry points; explicit dense settings must remain authoritative.
2. Adaptive mesh refinement must stay active without invoking backend reselection. Memory and numerical failures must not trigger an implicit dense allocation.
3. Fixed modes must not read or write timing history. Request-local compressed hints and resource admission must continue to work.
4. Preserve saved legacy profiles, explicit direct reference calls, non-double precision compatibility, bistatic behavior and BoR behavior. Legacy automatic selection remains only for explicit old-mode requests; it is not deleted.
5. Distinguish parallel scheduling's resource forecasts from permission to switch the selected backend.
6. Verify the timing comparison uses matching successful trials, excludes failed/reference rows, preserves accuracy caveats, and does not mistake aggregate savings across many runs for a five-minute per-solve advantage.

This policy change supersedes further optimization of the automatic backend picker proposed in earlier audits. It does not change numerical kernels, relax quality gates or resolve the separate coated-diagnostic metadata issue recorded in the previous review.
