export MONOSTATIC_AUDIT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/ms/audits/codex-2026-11-14/monostatic-sweep-investigation OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
for tree in orig fixed; do
  if [ $tree = orig ]; then export GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/sr; else export GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/iu; fi
  for g in "1024 slot 20" "512 square 10" "1024 square 20" "1024 star 20" "512 slot 10" "2048 slot 40"; do
    set -- $g; echo START $tree $2 $1
    python3 -W ignore claude_lifecycle.py "{\"n\":$1,\"kind\":\"$2\",\"k\":$3,\"out\":\"$tree/$2-$1\"}" 2>&1 | tail -3
  done
done
echo ALLDONE
