#!/bin/bash
# serial, fresh process per case, resumable; /usr/bin/time gives the whole-process peak
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
one(){ name=$1; script=$2; spec=$3; [ -s results/$name.time ] && return
  python3 timed.py $name $script "$spec"; }
one e2e-fmm-4096      preconditioned_solve.py '{"n":4096,"k":80,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/e2e-fmm-4096"}'
one e2e-comp-4096     compressed_control.py   '{"n":4096,"k":80,"pol":"TE","out":"results/e2e-comp-4096"}'
one e2e-dense-4096    dense_control.py        '{"n":4096,"k":80,"pol":"TE","out":"results/e2e-dense-4096"}'
one e2e-fmm-stream-4096 preconditioned_solve.py '{"n":4096,"k":80,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"near":"stream","out":"results/e2e-fmm-stream-4096"}'
# fixed panels per wavelength: k and panels grow together
one ppw-fmm-2048      preconditioned_solve.py '{"n":2048,"k":40,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/ppw-fmm-2048"}'
one ppw-comp-2048     compressed_control.py   '{"n":2048,"k":40,"pol":"TE","out":"results/ppw-comp-2048"}'
one ppw-fmm-8192      preconditioned_solve.py '{"n":8192,"k":160,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/ppw-fmm-8192"}'
one ppw-comp-8192     compressed_control.py   '{"n":8192,"k":160,"pol":"TE","out":"results/ppw-comp-8192"}'
