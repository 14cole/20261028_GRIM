# Bundled BLAS thread control

GHOST imports `threadpool_limits` and `threadpool_info` from this package.
No separate threadpoolctl installation is required. An installed copy is not
used by GHOST, so source copies and HPC workers use the reviewed version.

| Python | Implementation | License |
| --- | --- | --- |
| 3.10 and newer | `_threadpoolctl.py`, threadpoolctl 3.6.0 | `LICENSE-3.6.0.txt` |

The implementation file and BSD 3-Clause license are copied without content
changes from the official distributions. Their bytes were checked against the
installed distribution's RECORD hashes. The source filename is changed to
keep imports private to GHOST.

Upstream: https://github.com/joblib/threadpoolctl

| File | SHA-256 |
| --- | --- |
| `_threadpoolctl.py` | `12fb9526b6a74d2e686b7ec148dc165c3587999b14fa86984aa180e10802400b` |
| `LICENSE-3.6.0.txt` | `81ac619075248b06e53660b652d10e485f4675f5d0ae0f97ea22370da1f7e23b` |

Copy this entire directory with the backend. NumPy and SciPy remain external
dependencies. Thread limits apply to their supported native BLAS libraries;
they do not replace those libraries or the solver's assembly-thread controls.
