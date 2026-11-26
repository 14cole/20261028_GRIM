# Reproduce the review

The evidence archive contains scripts, result JSON and small complete field arrays. Unzip it into a fresh writable directory. Run the examples below from the extracted `evidence` directory. `GRIM_ROOT` must point to the full application checkout at `ed90b65ff89826274adacae01bcfbafe143e9819`. The checked-in Windows and Linux native libraries are in that checkout. The archive contains audit inputs and outputs.

The fresh runs used Linux x86-64, Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0 and offscreen PySide6 6.12.0. The host had a 16 GiB cgroup memory limit. Use the GHOST GUI and build dependencies, including setuptools, wheel, and a Linux C compiler for the packaging check. One thread is sufficient for the focused numerical runs. Run the speed diagnostic with the machine's normal BLAS settings so an unrelated BLAS warning does not hide the demonstrated false success.

```bash
export GRIM_ROOT=/absolute/path/to/GRIM
export GHOST_AUDIT_ROOT="$GRIM_ROOT"
export PYTHONPATH="$GRIM_ROOT/tools/GHOST"
export QT_QPA_PLATFORM=offscreen
export MPLCONFIGDIR="$PWD/mpl"
export XDG_CACHE_HOME="$PWD/cache"
mkdir -p replay
sha256sum -c SHA256SUMS
python packaging/reproduce_distribution.py "$GRIM_ROOT" --output "$PWD/replay/distribution"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python line/line_checks.py --output replay/line.json
python cgroups/probe_nested_cgroup.py "$PYTHONPATH/ghost_backend/twod/solver.py" > replay/cgroups.json
python cgroups/probe_request_budget.py replay/cgroups.json > replay/request-budget.json
python numerics/cylinder_check.py --output replay/cylinders
python numerics/dense_spool_check.py --output replay/dense-spool
python numerics/check_fallback.py --ghost-source "$PYTHONPATH" --native-results replay/cylinders --output replay/fallback
python check_gui_defaults.py
python gui/tiled/audit_gui.py
python gui/bor/audit_bor.py
python bor/test_s5_bor_near_publish.py
python bor/test_c5_long_panels.py
python bor/test_r3_input_and_warnings.py
(cd replay && python ../bor/sphere_pair.py native && python ../bor/sphere_pair.py fallback)
```

The cgroup harness is pinned to the original source and records the **erroneous** old budgets. To validate a repair, use an independent revised harness and assert the correct budgets for the new revision. The Line Expansion and package scripts record observations. Read the warnings, field errors, archive contents and diagnostic outputs. A zero exit code alone does not certify those features. Some GUI scripts write results next to themselves and expect a new output path. Extract a fresh copy for each replay.

For historic scale results, `archive/replay_archives.py --output replay/archive.json` reads immutable public JSON from GitHub. It also accepts `--cache` with the original relative file layout for offline use. To replay the NPZ comparisons, supply the five files below to `python archive/recompute_fields.py`. The script checks Git blob IDs before loading them. They are from Claude commit `7a5e9fdabe0e22de1fd74ef01bb4a22f07567733`.

- [32k matched sweep arrays](https://github.com/14cole/20261028_GRIM/tree/7a5e9fdabe0e22de1fd74ef01bb4a22f07567733/audits/claude-2026-11-15/monostatic-sweep-review/results), file `fields_and_row_checks.npz`
- [65k cap-only, combined and mixed arrays](https://github.com/14cole/20261028_GRIM/tree/7a5e9fdabe0e22de1fd74ef01bb4a22f07567733/audits/claude-2026-11-14/fmm-scale-response-review/results), files `cap-only-65536.npz`, `combined-65536.npz` and `mixed-65536.npz`
- [65k double FMM array](https://github.com/14cole/20261028_GRIM/tree/7a5e9fdabe0e22de1fd74ef01bb4a22f07567733/audits/claude-2026-11-14/fmm-scale-validation-review/results), file `fmm-65536.npz`

The fresh cylinder script implements its own analytic solution. The sphere check uses the repository's Mie reference. A separate stand-alone JavaScript quadrature calculation for the BoR near-rule counterexample is in `bor/independent_bor.js` and can be run with Node. For a second review, use an independently written fixture first, then compare with these scripts.
