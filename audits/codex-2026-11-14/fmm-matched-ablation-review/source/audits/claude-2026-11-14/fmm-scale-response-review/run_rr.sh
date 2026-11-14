#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
one(){ [ -s results/$1.time ] && return; python3 timed2.py "$@"; }
python3 check_adaptive_sketch.py > results/check_adaptive_sketch.log 2>&1; echo "rc=$?" >> results/check_adaptive_sketch.log
one mixed-65536 native_fmm_control.py '{"n":32768,"k":640.0,"op_tol":0.01,"inv_tol":0.01,"preconditioner_storage":"complex64","detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":false,"out":"results/mixed-65536"}'
one cap-only-65536 compressed_control.py '{"n":32768,"k":640.0,"adaptive_sketch":false,"initial_rank_cap":256,"storage_budget_gib":10,"out":"results/cap-only-65536"}' 12.9
one combined-65536 compressed_control.py '{"n":32768,"k":640.0,"adaptive_sketch":true,"initial_rank_cap":256,"storage_budget_gib":10,"out":"results/combined-65536"}' 12.9
touch results/all.done
