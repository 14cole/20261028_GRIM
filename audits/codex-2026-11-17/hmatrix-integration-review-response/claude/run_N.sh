export MONOSTATIC_AUDIT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/ms/audits/codex-2026-11-14/monostatic-sweep-investigation GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
until grep -q ALLDONE claude_M_new.log 2>/dev/null; do sleep 20; done
for spec in '{"name":"star8192-t1","n":4096,"kind":"star","k":80,"threads":1,"builder":"production","out":"out/star8192-t1"}' '{"name":"star8192-t2","n":4096,"kind":"star","k":80,"threads":2,"builder":"production","out":"out/star8192-t2"}' '{"name":"star8192-t4","n":4096,"kind":"star","k":80,"threads":4,"builder":"production","out":"out/star8192-t4"}' '{"name":"slot2048-t2","n":1024,"kind":"slot","k":20,"threads":2,"builder":"production","out":"out/slot2048-t2"}'; do
  python3 -W ignore claude_cancel_production.py "$spec" > out/cancel-$(echo "$spec" | sed 's/.*"name":"\([^"]*\)".*/\1/').log 2>&1; echo "cancel rc $?" >> run_N.log
done
python3 -W ignore claude_diagonal_queries_production.py claude_diagonal_queries_production.json > claude_diagonal_queries_production.log 2>&1; echo "diag rc $?" >> run_N.log
echo NDONE >> run_N.log
