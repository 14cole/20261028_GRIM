# Reproduce the post-merge optimization checks

Baseline production is `main` at `bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c`. Candidate production differs only in `tools/GHOST/ghost_backend/linalg/dense.py`. Use distinct checkouts and Python with NumPy, SciPy, psutil, and threadpoolctl. The ordinary repository dependencies and native Linux libraries suffice for physical solves. No FMM library or prior audit helper is required.

Set `BASE_GRIM_ROOT` and `NEW_GRIM_ROOT` to those checkout roots. Also prepare a disposable baseline copy as `PROTOTYPE_GRIM_ROOT` and replace its `tools/GHOST/ghost_backend/linalg/dense.py` with the supplied `prototype_dense.py`. This preserves the all-width exploratory implementation separately from the final narrow-only change. Run from this audit directory. Each physical case runs in a fresh process, with one BLAS thread except the explicitly four-thread suite. Do not run the suites concurrently when measuring speed. Use an empty results directory; existing results are not overwritten.

```sh
export BASE_GRIM_ROOT=/absolute/path/to/baseline
export NEW_GRIM_ROOT=/absolute/path/to/candidate
export PROTOTYPE_GRIM_ROOT=/absolute/path/to/prototype
export RESULTS_DIR=/tmp/postmerge-fresh-results
python run_suite.py suite_leaf.json
python run_suite.py suite_dense.json
python run_suite.py suite_scale.json
python run_suite.py suite_dense4.json
python run_suite.py suite_final.json
python analyze.py
OPENBLAS_NUM_THREADS=1 python check_dispatch.py "$NEW_GRIM_ROOT" /tmp/check-dispatch.json
OPENBLAS_NUM_THREADS=1 python check_dense.py "$BASE_GRIM_ROOT" /tmp/check-dense-base
OPENBLAS_NUM_THREADS=1 python check_dense.py "$NEW_GRIM_ROOT" /tmp/check-dense-new
OPENBLAS_NUM_THREADS=1 python product_probe.py 2048 /tmp/product-probe.json
```

`run_case.py` also accepts a JSON specification directly; `root` must point to the chosen source checkout. Geometries are self-contained in `common.py`. `n` is the number of P1 panels/nodes; dielectric unknown count is twice `n`, PEC unknown count is `n`. These are 2D extruded cross-sections, not 3D surfaces. The dielectric is homogeneous, isotropic, relative permittivity `3-0.08j`, relative permeability 1, in vacuum. The polygonal narrow slot is 0.02 m wide and 1.5 m deep. Nominal star/circle radius is 1 m. All sweeps use 180 monostatic angles from -90 inclusive to 90 exclusive.

`leaf_divisor` is a research-only constructor argument, not a new application option. It changes both the spatial operator and inverse leaf sizes. It leaves precision, tolerances, independent residual checks, and production defaults unchanged. The four repeated scale solves use 8,192 unknowns; no 32 GB pressure or 64k solve is claimed.

Replay the complete saved fields and residual evidence without solving:

```sh
python evidence.py unpack /tmp/postmerge-replay
RESULTS_DIR=/tmp/postmerge-replay/results ANALYSIS_OUT=/tmp/postmerge-replay-analysis.json python analyze.py
```

The manifest verifies archive parts and every extracted member. All 55 physical runs include full complex field arrays at every angle, the independently sampled residuals, row norms, solution infinity norms, RHS sample rows, and raw timing records. Full density/RHS arrays are additionally retained for the three narrow-slot leaf variants and the first narrow-slot Dense pair; other densities have SHA-256 identities in their records. The synthetic-check solution arrays are also archived. Replaying residual evidence verifies recorded arithmetic; fresh independent assembly is still required to challenge the coefficient oracle.

The optional `worker_checks.py` uses PySide6 and runs four GUI-worker request-path solves plus pre-canceled requests. Set `NEW_GRIM_ROOT` for its candidate checkout. It is a synchronous worker check, not interactive GUI cancellation.

The initial checks grew from 34 to 35 cases with hierarchical coverage. After the wide-batch regression was found, the final implementation was restricted to <=16 RHS and the final checks expanded to 53 cases per revision, including 17 and 180 RHS. Eight dispatch checks verify both sides of that boundary. The original 52 physical runs used main or the all-width prototype (record paths named candidate refer to that then-current prototype; its exact source is prototype_dense.py and prototype-source-verification.json). Three additional physical runs validate the final source; suite_final.json uses NEW_GRIM_ROOT. The final desktop-worker checks were also rerun. No timing result for the all-width implementation is relabeled as a fresh final implementation measurement. Runtime smoke configuration and dependency setup are excluded from solve timings.
