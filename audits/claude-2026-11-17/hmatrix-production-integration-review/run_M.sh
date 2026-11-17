export MONOSTATIC_AUDIT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/ms/audits/codex-2026-11-14/monostatic-sweep-investigation
GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp_old python3 claude_run_suite.py claude_M_old.json > claude_M_old.log 2>&1
GRIM_ROOT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/hp python3 claude_run_suite.py claude_M_new.json > claude_M_new.log 2>&1
echo ALLDONE >> claude_M_new.log
