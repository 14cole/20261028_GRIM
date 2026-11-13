# Reproduce the review response

Read [REVIEW_RESPONSE.md](REVIEW_RESPONSE.md) first. This directory adds research only to parent commit `611f7fa3874cad8d366733e6dbcb38740fab05f0`.

## Evidence without rerunning expensive kernels

From this directory:

```sh
python unpack_evidence.py /tmp/fmm-review-response-evidence
python /tmp/fmm-review-response-evidence/analyze_review.py
```

Extraction verifies SHA-256 for every archive part, the combined archive, and every extracted file. Analysis requires NumPy and recomputes the retained numerical comparisons and timing arithmetic. Every matrix column was tested in the baseline experiments; only complete columns containing the worst entries are retained, together with their reference columns and decomposed worst entries. The archive does not contain every full matrix.

## Fresh numerical runs

Use a separate writable copy of the extracted evidence so the original results remain available. Set `GRIM_ROOT` to a checkout containing this branch's production tree. Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0 were used; `ENVIRONMENT.json` records the host limits. Native GHOST near assembly was available.

The unchanged research wrapper also requires FMM2D, even for imports into some cached cases. The native control used upstream commit `7e7509ecd6ebe31b9292cb00825410b478f44808`, built with default 32-bit Fortran integers and GNU Fortran 14.2. The tested Linux library SHA-256 was `4f40362629549126c66f966b39f88492dd0c97e9ce64d1fbc55b6cc65159fb13`. Follow the native build notes in the inherited `../solver-methods-research/` evidence. No external DLL or .so is redistributed here; the inherited licensing discrepancy remains unresolved.

```sh
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export FMM2D_LIBRARY=/absolute/path/to/libfmm2d.so
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
# Set LD_LIBRARY_PATH if your Fortran runtime is not installed system-wide.
cd /absolute/path/to/fresh-writable-evidence-copy
python run_review_checks.py
python region_plans.py
python thin_diagnostic.py "$GRIM_ROOT"
python accuracy_diagnostic.py "$GRIM_ROOT"
python analyze_review.py
```

`run_review_checks.py` preserves the original host's `LD_LIBRARY_PATH` setting; adapt that single environment assignment for a different runtime location. It starts a native control, two cached 4k runs and three complete-matrix comparisons in separate serial subprocesses, each with a 900-second timeout. Roughly 12 minutes on this host covered that batch. The thin and accuracy diagnostics add several minutes. Timing is host-dependent; compare native and cached runs on the same host. Do not run the large numerical jobs concurrently if comparing timings.

The final thin diagnostic is `THIN_DIAGNOSTIC.json`, using the normal near dispatcher and its eligibility rules. `THIN_INITIAL_DIAGNOSTIC.json` and the old `thin_diagnostic.py.log` are retained historical probes that forced the semi-analytic route on all support pairs; the final script supersedes that probe. `thin-final.log` records the final successful run. `run_diagnostics.py` and `run_thin_final.py` document the original asynchronous scheduling and contain host paths; the explicit sequential commands above are the portable reproduction sequence.

The native/cache outputs include full product vectors and exact sampled rows. Full-matrix JSON files record all-column maximum errors; their NPZ files retain selected complete columns. Variant NPZ files retain every checked column. Thin JSON files record complex integral values at each quadrature order/tolerance. `claude_reference/` contains the nine original review/evidence files, pinned and hash-verified by `CLAUDE_IDENTITIES.json`.

## Questions for Claude's next review

1. Does the channel-dependent quadrature stopping explanation agree with your independent thin-gap integration, while preserving dispatcher eligibility?
2. What accuracy policy controls the far-field discrepancies across tree-depth transitions without an excessive near-storage increase?
3. For the local H-matrix hybrid, what exact panel-pair partition avoids double counting continuous P1 support contributions?
4. Can the preconditioner remain effective when the product's near field is compressed or geometrically reduced? Include factor RAM and iteration counts.
5. Does hybrid or adaptive wideband win on identical fixed-frequency refinement and thin/coated cases at the same field accuracy?
6. Where does total setup plus 1/16/181-angle solve time cross over against existing Dense and Compressed?
