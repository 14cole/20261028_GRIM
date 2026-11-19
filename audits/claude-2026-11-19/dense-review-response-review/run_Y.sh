until [ "$(grep -c END claude_X.log)" = 28 ]; do sleep 15; done
MONOSTATIC_AUDIT=/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/ms/audits/codex-2026-11-14/monostatic-sweep-investigation TREES='{"main":"/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/pm_old"}' python3 claude_run_suite_trees.py claude_Y.json > claude_Y.log 2>&1
echo YDONE >> claude_Y.log
