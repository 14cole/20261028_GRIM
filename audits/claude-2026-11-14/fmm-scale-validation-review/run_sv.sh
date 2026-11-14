#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
one(){ [ -s results/$1.time ] && return; python3 timed2.py "$@"; }
bash run_checks.sh > results/run_checks.log 2>&1; echo "run_checks rc=$?" >> results/run_checks.log
python3 check_adaptive_sketch.py > results/check_adaptive_sketch.log 2>&1; echo "rc=$?" >> results/check_adaptive_sketch.log
one adaptive-32768        compressed_control.py '{"n":16384,"k":320.0,"adaptive_sketch":true,"initial_rank_cap":256,"storage_budget_gib":4,"out":"results/adaptive-32768"}'
one compressed-32768      compressed_control.py '{"n":16384,"k":320.0,"out":"results/compressed-32768"}'
one adaptive-no-cap-32768 compressed_control.py '{"n":16384,"k":320.0,"adaptive_sketch":true,"initial_rank_cap":null,"storage_budget_gib":4,"out":"results/adaptive-no-cap-32768"}'
one compressed-32768-r2   compressed_control.py '{"n":16384,"k":320.0,"out":"results/compressed-32768-r2"}'
one storage-32768-te      native_fmm_control.py '{"n":16384,"k":320.0,"op_tol":0.01,"inv_tol":0.01,"preconditioner_storage":"complex64","native_pairs":true,"profile":false,"dense_reference":false,"out":"results/storage-32768-te"}'
one fmm-65536             native_fmm_control.py '{"n":32768,"k":640.0,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":false,"out":"results/fmm-65536"}'
touch results/phaseA.done
one adaptive-no-cap-65536 compressed_control.py '{"n":32768,"k":640.0,"adaptive_sketch":true,"initial_rank_cap":null,"storage_budget_gib":10,"out":"results/adaptive-no-cap-65536"}' 13.2
