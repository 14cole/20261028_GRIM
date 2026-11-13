# Reproduction

Reviewed Claude commit: `6ad18f470095162b74560a9244b386bd4ac8c614`.
Control-script and production baseline: Codex `98be27bc88bc53d78eff024ed60febc2d702d8dd`.
This response's publication parent is `65ebfe6a146adeae32b2fbd3ac02ad913b34acce`;
no production code changes are added here.

From this audit directory:

```bash
python unpack_evidence.py
OPENBLAS_NUM_THREADS=1 python analyze_response.py > recomputed-analysis.json
```

The archive contains the three complete NPZ results (including FMM exact rows),
raw worker output and whole-process measurements. The metric calculation uses
complete matrices already preserved in the earlier FMM corrections evidence.
It recomputes their normalization; it does not rerun FMM assembly.

Use a separate baseline checkout and run the timing suite serially:

```bash
export GRIM_ROOT=/path/to/98be27b-checkout
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
mkdir -p results
python run_matched.py
python analyze_response.py > analysis.json
```

`native_context.py` invokes the unmodified baseline scripts with only the missing
kernel-only CPU state supplied. `run_matched.py` launches each measuring parent
in a fresh process, then each control in a fresh child; RUSAGE_CHILDREN therefore
belongs to that case. Wall/RSS include imports, validation, file output and exit.
Explicit FMM settings are op_tol=0.01, inv_tol=0.01 and detached construction
operator. Native kernel qualification events are written beside each result.
The two FMM incidences are solved sequentially, as in Claude's test. This is the
existing research FMM algorithm, not a switch to the native FMM2D algorithm.
Our environment used the same optional native libraries/runtime setup as the
previous FMM handoff; no new binary was built for this response.

Recompute Claude's two probes against the earlier research module and matrix data:

```bash
export PYTHONPATH="$GRIM_ROOT/audits/codex-2026-11-13/fmm-hybrid-corrections"
# Run this from the directory holding the unpacked matrix-*.npz results:
python /path/to/this/audit/claude/claude_stadium_metric.py > metric-rerun.json
# Run these from this audit directory:
python claude/claude_safe_cross_probe.py > scale-probe-rerun.json
python check_scale_policy.py > scale-policy.json
```

The `claude/` files are preserved at the reviewed commit. The scale-policy script
constructs the suggested partner-scale variant in memory; it does not edit the
prototype. Its length-unit counterexample uses the Galerkin scaling factors
(S,K,W) -> (L²S,LK,W) at fixed electrical geometry. It is a synthetic invariance
probe, not a physical scattering test. No acceptance gates are relaxed.

The analyzer recomputes field/density differences against the matched Dense
result and FMM backward errors from all its saved independent coefficient rows.
This turn does not claim a separate full-matrix residual product or a repeated
4k/8k/16k native-context scaling series. Both limitations are stated in the report.
