#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
while [ ! -e results/phase1.done ]; do sleep 10; done
BASE=$1; CAND=$2
one(){ [ -s results/$1.time ] && return; GRIM_ROOT=$2 GHOST_AUDIT_ROOT=$2 python3 timed.py $1 $3 "$4"; }
GRIM_ROOT=$CAND GHOST_AUDIT_ROOT=$CAND python3 check_norms.py > results/check_norms.json 2> results/check_norms.err
one norms-4096 $CAND norms_benchmark.py '{"n":2048,"k":40,"threads":1,"out":"results/norms-4096"}'
one comp-base-4096 $BASE compressed_control.py '{"n":4096,"k":80,"out":"results/comp-base-4096"}'
one comp-cand-4096 $CAND compressed_control.py '{"n":4096,"k":80,"out":"results/comp-cand-4096"}'
one comp-cand-8192 $CAND compressed_control.py '{"n":8192,"k":160,"out":"results/comp-cand-8192"}'
GRIM_ROOT=$CAND python3 build_pair_kernel.py > results/build_pair_kernel.log 2>&1
GRIM_ROOT=$CAND python3 validate_native_pairs.py > results/validate_native_pairs.json 2> results/validate_native_pairs.err
GRIM_ROOT=$CAND python3 check_native_fallbacks.py > results/check_native_fallbacks.json 2> results/check_native_fallbacks.err
one fmm-ref-4096 $CAND native_fmm_control.py '{"n":4096,"k":80,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":false,"profile":false,"dense_reference":false,"out":"results/fmm-ref-4096"}'
one fmm-nat-4096 $CAND native_fmm_control.py '{"n":4096,"k":80,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":false,"out":"results/fmm-nat-4096"}'
one fmm-nat-8192 $CAND native_fmm_control.py '{"n":8192,"k":160,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":false,"out":"results/fmm-nat-8192"}'
one comp-cand-16384 $CAND compressed_control.py '{"n":16384,"k":320,"out":"results/comp-cand-16384"}'
one fmm-nat-16384 $CAND native_fmm_control.py '{"n":16384,"k":320,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":false,"out":"results/fmm-nat-16384"}'
