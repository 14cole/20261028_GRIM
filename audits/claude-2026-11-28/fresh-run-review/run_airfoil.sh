#!/bin/bash
# GRIM_ROOT=<95f8719> ./run_airfoil.sh results/airfoil
out=$1; mkdir -p $out; export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
(lscpu | grep "Model name"; nproc; uptime; date -u) > $out/host.txt
for job in "1 180 auto a" "1 180 auto b" "1 180 auto c" "5 360 auto a" "5 360 compressed a" "5 360 dense a" "5 360 compressed b" "5 360 auto b" "10 180 auto a" "15 180 auto a"; do
  set -- $job; tag=f${1}_a${2}_${3}_${4}
  python3 "$(dirname "$0")/airfoil_job.py" $1 $2 $3 $out/$tag.npz > $out/$tag.json 2> $out/$tag.err
done
