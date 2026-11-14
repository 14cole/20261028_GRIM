#!/usr/bin/env bash
set -euo pipefail
: "${GRIM_ROOT:?Set GRIM_ROOT to the checkout root}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p results
python build_pair_kernel.py
for script in check_repairs.py check_norm_scope.py check_unseen.py check_flat_near.py check_storage.py check_stream_validation.py check_native_fallbacks.py; do
  python "$script"
done
mv native-fallbacks.json results/native-fallbacks.json
python -m compileall -q fmm *.py
