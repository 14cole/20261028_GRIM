#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 timed2.py fmm-mixed-32768-16ang native_fmm_control.py '{"n":16384,"k":320.0,"op_tol":0.01,"inv_tol":0.01,"preconditioner_storage":"complex64","native_pairs":true,"profile":false,"dense_reference":false,"angles":[0,22.5,45,67.5,90,112.5,135,157.5,180,202.5,225,247.5,270,292.5,315,337.5],"out":"results/fmm-mixed-32768-16ang"}'
python3 timed2.py compressed-32768-16ang compressed_control_angles.py '{"n":16384,"k":320.0,"angles":[0,22.5,45,67.5,90,112.5,135,157.5,180,202.5,225,247.5,270,292.5,315,337.5],"out":"results/compressed-32768-16ang"}'
touch results/ma.done
