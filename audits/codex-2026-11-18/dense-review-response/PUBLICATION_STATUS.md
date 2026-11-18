# Publication status

The computations and local archive verification completed. During upload, the execution environment became unavailable. Its wait API subsequently reported that it was neither ready nor starting. This is an infrastructure interruption, not a numerical test failure or an approval rejection.

Recovered: the report, full analysis summary, reviewer replay summary, selected scripts, and the first archive part. Missing: 32 of 33 archive parts, the SHA-256 member manifest, the research replacement module, and several runners. `publication-inventory.json` records every intended file's byte count and Git blob identity and whether it was recovered. These identities were computed before the interruption. The partial archive cannot be extracted or independently replayed.

The report's measurements were computed and the complete local archive was unpacked, hash-checked, and reanalyzed before the outage. The resulting analysis was byte-identical to the original. That local verification does not substitute for publishing the missing arrays. Treat the fresh physical field comparisons as reported measurements until the archive can be restored or the experiments independently rerun.

Claude's complete pinned review evidence is included under `claude/` using its original Git blob objects, and remains independently available at df18342afb09cd6c6cd3b954c5ef1d8afb3b3894. It must not be confused with the missing fresh Codex arrays.

Next recovery step: restore `/workspace/postmerge-review-response` from the execution environment, compare every remaining file with its recorded Git blob identity, upload the missing artifacts, and re-run archive extraction and analysis from the published files. If the environment cannot be restored, rerun the experiments and identify them as new measurements. Do not reconstruct numerical arrays from the summaries.

No production files change. Keep main at bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c and withhold optimization 5542cd5.
