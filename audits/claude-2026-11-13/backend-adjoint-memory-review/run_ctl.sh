#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
one(){ [ -s results/$1.time ] && return; python3 timed.py $1 $2 "$3"; }
one c-comp-4096   compressed_control.py    '{"n":4096,"k":80,"out":"results/c-comp-4096"}'
one c-dense-4096  dense_control.py         '{"n":4096,"k":80,"out":"results/c-dense-4096"}'
one c-fmm-4096    corrected_fmm_control.py '{"n":4096,"k":80,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/c-fmm-4096"}'
one c-comp-2048   compressed_control.py    '{"n":2048,"k":40,"out":"results/c-comp-2048"}'
one c-fmm-2048    corrected_fmm_control.py '{"n":2048,"k":40,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/c-fmm-2048"}'
one c-comp-8192   compressed_control.py    '{"n":8192,"k":160,"out":"results/c-comp-8192"}'
one c-fmm-8192    corrected_fmm_control.py '{"n":8192,"k":160,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/c-fmm-8192"}'
one c-comp-16384  compressed_control.py    '{"n":16384,"k":320,"out":"results/c-comp-16384"}'
one c-comp-4096-fallback compressed_control.py '{"n":4096,"k":80,"fallback":true,"out":"results/c-comp-4096-fallback"}'
GRIM_CANDIDATE_ROOT=$GRIM_ROOT python3 physical_product_benchmark.py > results/physical-product-paired.json 2> results/physical-product-paired.stderr
