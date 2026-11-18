# Review-response plan before fresh measurements

Pin Claude review df18342 and production main bf5201c. Do not merge 5542cd5; the reported host-dependent narrow-batch regression is sufficient to withhold it even if this host differs.

1. Verify the raw reviewer timing/field records and re-run its unmodified solver-order benchmark on this host.
2. Independently test old, NumPy-F-output and direct SciPy zgemm residuals in the LU/product/correction/product sequence. Read actual loaded pool sizes using the bundled threadpool controller after importing scipy.linalg; do not infer thread count from an environment variable. Explore separate NumPy/SciPy pools as a possible mechanism, but do not claim a cause from correlation alone.
3. Validate a research-only direct-BLAS candidate: plain F-contiguous complex128 coefficient matrix, matching F-contiguous complex128 candidate, >1 RHS, SciPy available. Keep width 1, C/strided inputs, custom/disk operators, NumPy fallback and reused residuals on the old path. Guard the inputs to avoid an implicit full-matrix conversion. No production file on the published response branch changes.
4. Fresh physical solves and correctness/fallback/allocation checks must accompany any favorable expression timing. Preserve complete fields and targeted density/RHS evidence. Windows and other BLAS builds remain open; a single Linux host cannot qualify a default replacement.
5. Keep Compressed leaf defaults. Cross-check the reviewer layered results against its saved Dense references. No need to repeat a large unchanged leaf sweep merely to rediscover the measured tradeoff.

Claude should independently challenge the new candidate and run its own computations before cross-analyzing these results. In particular, distinguish the two BLAS libraries/pools and distinguish pure replay from fresh numerical runs.
