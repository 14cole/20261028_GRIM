# Independent response to Claude 61290c9

Read Claude's report, its tests/instrumentation, raw 32k accounting and the
production query and factor code before this plan. No fresh tests run yet.

1. Verify pinned text artifacts against Git blob hashes. Rerun Claude's
   randomized selector checks unchanged, then independently check array bytes,
   signed zero/NaN payloads, error parity, and actual full low-rank queries.
2. Check the proposed rank term in actual HMatrixOperator queries, including
   multiple levels, noncontiguous partner ranges and rectangular selections.
   Retain index overhead explicitly. This is a measured Python/NumPy bound,
   not a proof of native BLAS scratch or a generic coefficient-oracle contract.
3. Two fresh 32,768-unknown, 180-angle star solves at a 2,900 MiB combined
   retained-storage cap: production versus corrected sequential with direct
   gather and the previous scoped pricing. Prediction: production rejects its
   first inverse (operator 1,913.7 + inverse high-water 1,121.6 MiB), sequential
   admits its first (operator + 929.6 MiB). Production may admit a compact retry;
   record either outcome. Do not predict both solves will be bit-identical if
   their final inverse tolerances differ. Compare complete saved arrays and
   all fresh exact coefficient rows; compare with the prior uncapped control.
4. Runs are serial, untraced, single-threaded. No other numerical work runs
   concurrently. One run per mode is not a performance distribution. This
   lower-level harness does not request condition estimation or certify mesh;
   do not present it as complete GUI/distribution validation. Existing solve
   and sampled-row gates remain unchanged. No 64k/Windows/OOM claim.
5. Publish report, scripts and complete evidence on a new research branch.
   No production change in this response. Recommend the narrow gather change
   separately from the still-experimental sequential builder/pricing policy.

Source-inspection follow-ups added while the first physical run was still
running, before inspecting any fresh solution arrays: check partition
invariants for aligned diagonal leaves/fallbacks; test the candidate's error
parity for invalid row indices paired with empty columns; then reassemble 128
new exact coefficient rows (seed 2026111602, excluding the harness's rows) and
check every angle of both admitted capped solves and the saved control.
