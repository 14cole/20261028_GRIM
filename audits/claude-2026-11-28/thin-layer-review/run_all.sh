#!/bin/bash
# RC=<export of 6621db2> PROTO=<export of f1564a7> ./run_all.sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
here=$(cd "$(dirname "$0")" && pwd)
run() { for t in rc thin; do root=$RC; [ $t = thin ] && root=$PROTO; GRIM_ROOT=$root python3 "$here/trace_case.py" $t "$@" | tail -1; done; }
for v in one three six six_mixed; do for b in automatic dense compressed; do run 120:$v $b results/q1; done; done
for P in 502 503 1014 1015; do for v in one six_mixed; do for b in compressed automatic; do run $P:$v $b results/q2; done; done; done
for b in dense compressed; do run 600:many $b results/q3; done
GHOST_MAX_SOLVE_GB=0.44 run 600:many dense results/q3cap;      GHOST_MAX_SOLVE_GB=0.42 run 600:many dense results/q3cap
GHOST_MAX_SOLVE_GB=0.34 run 600:many compressed results/q3cap; GHOST_MAX_SOLVE_GB=0.32 run 600:many compressed results/q3cap
for b in dense compressed; do run 480:ring $b results/q4; run 200:two_strips $b results/q4; run 120:six_mixed $b results/q4 bistatic; done
for b in dense compressed; do THIN_MATERIAL="3.2 -0.02 1.5 -0.1" THIN_TAG=_magnetic run 120:six_mixed $b results/q4; done
THIN_MATERIAL="1 0 1 0" THIN_TAG=_zero run 120:six_mixed automatic results/q4
THIN_BASIS=2 THIN_TAG=_p2 run 120:six_mixed dense results/q4
