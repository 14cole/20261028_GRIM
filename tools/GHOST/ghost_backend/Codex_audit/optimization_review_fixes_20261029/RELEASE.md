# Release closeout - 2026-10-30

This release packages the validated follow-up to `6c73ccd`: cheaper live worker-memory charges, a detailed retry before reservation refusal (including the corrected parent-RSS cases), an optional polynomial-reuse fallback at material junctions, clearer memory telemetry, and behavior-preserving ASCII source spelling. The matching FREDDY material parser is included.

The full suite passed 2,787 tests and 1,065 subtests with one expected Windows skip. Four certified 15 GHz inlet solves produced identical VV/HH fields, with effectively tied total runtime against the pre-construction-check baseline. No production changes followed validation. The final Claude review found no release blocker; Codex's response qualifies the claimed timing upper bound.

Earlier reports' statements that work is local or unpushed describe their state at the time they were written. This closeout accompanies the subsequent user-authorized commit and push. Historical JSON evidence remains unchanged.

The commit includes implementation, regression tests, handoffs, review conclusions, and compact validation/timing summaries. Detailed local trial outputs, original-source snapshots and full structured test archives remain available in this checkout. Audit verification scripts that consume those archives require those local artifacts. An unrelated earlier modified review-result file is excluded.

Compressed remains the default, with dense and impedance as explicit overrides. No new RAM policy or saved solve-history learning is introduced. Coated-inlet conditioning/rank, magnetic-material scaling and near-capacity qualification remain future studies.
