#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
while pgrep -f run_e2e.sh >/dev/null; do sleep 15; done
one(){ [ -s results/$1.time ] && return; python3 timed.py $1 $2 "$3"; }
one e2e-fmm-4096-r2  preconditioned_solve.py '{"n":4096,"k":80,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/e2e-fmm-4096-r2"}'
one e2e-comp-4096-r2 compressed_control.py   '{"n":4096,"k":80,"pol":"TE","out":"results/e2e-comp-4096-r2"}'
