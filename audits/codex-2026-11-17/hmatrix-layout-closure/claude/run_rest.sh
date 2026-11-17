export MONOSTATIC_AUDIT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/ms/audits/codex-2026-11-14/monostatic-sweep-investigation OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp_old python3 -W ignore accuracy_and_speed.py old asis 4096 star 80 out/old-star-4096.npz 0; echo rc $?
GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp python3 -W ignore accuracy_and_speed.py new asis 4096 star 80 out/new-star-4096.npz 0; echo rc $?
for rep in a b; do
GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp_old python3 -W ignore accuracy_and_speed.py old asis 4096 star 80 out/t-old-$rep.npz 1; echo rc $?
GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp python3 -W ignore accuracy_and_speed.py new asis 4096 star 80 out/t-new-$rep.npz 1; echo rc $?
GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp python3 -W ignore accuracy_and_speed.py newF fortran_e 4096 star 80 out/t-newF-$rep.npz 1; echo rc $?
done
echo RESTDONE
