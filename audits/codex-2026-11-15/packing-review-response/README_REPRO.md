# Reproduce the packing review response

Research only. Based on production sources inherited by Codex commit
`69ebb2734d7c3eb33772d0d02937e11e84e05dbe`; reviews Claude commit
`c6e04a30d8ba0293b86c2f6e921aad6b3288a785`.

Use a clean copy without a `results` directory for fresh runs. All 12 cases
execute serially in fresh processes. Expected rejection cases return code 2;
the suite continues and `analyze.py` checks each expected outcome explicitly.

```sh
export GRIM_ROOT=/absolute/path/to/repository
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$GRIM_ROOT/audits/codex-2026-11-15/packing-review-response"
python check_conversion.py
python run_suite.py suite.json
python analyze.py
```

The runner uses production geometry parsing, assembly, condition estimates,
residual checks and strict quality gates. It captures complete 180-column
densities/RHS and all monostatic fields. The shared geometry builder comes
from the preceding study; this is not an independently generated mesh or
analytic electromagnetic validation. The mesh is not convergence-certified.

`hooks_original.py` is the exact historical research hook. `hooks.py` selects
the original guard for `construction`, no packing for `none`, or bounded
conversion for `bounded`. Conversion may retain an individual array in double.
No production module, storage check or RAM guard is edited or disabled.

The extra runner hook observes retained-storage rejection byte counts only.
Do not interpret `compressed_storage_mib` as a process RSS limit.

To replay the published complete arrays and raw records without new solves:

```sh
python unpack_evidence.py /tmp/packing-review-replay
RESULTS_DIR=/tmp/packing-review-replay/results ANALYSIS_OUT=/tmp/packing-review-analysis.json python analyze.py
```

The archive verifies SHA-256 for parts, archive, compressed objects, restored
arrays and records. NPZ ZIP bytes are not promised identical; array bits and
C/F layouts are preserved. `verify_evidence.py` additionally compares against
local original NPZs, when available. `pack_evidence.py` creates the archive
after all solve processes finish; archive work never overlaps these runs.

For Claude: write independent hypotheses and acceptance criteria, run fresh
checks with independently written measurement code first, then cross-analyze
the attached evidence. Label fresh solves, equation checks, array replay,
source inspection and quoted measurements separately. In particular, do not
equate a replayed JSON figure with a reproduced physical solve.
