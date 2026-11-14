#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
until [ -e results/all.done ]; do sleep 20; done
python3 timed2.py mixed-65536 native_fmm_control.py '{"n":32768,"k":640.0,"op_tol":0.01,"inv_tol":0.01,"preconditioner_storage":"complex64","detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":false,"out":"results/mixed-65536"}'
touch results/all2.done
