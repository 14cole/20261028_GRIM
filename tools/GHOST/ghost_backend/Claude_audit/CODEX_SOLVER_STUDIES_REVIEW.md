# Review handoff: 2D solver studies, 2026-10-29 UTC

The user authorized the recommended studies using representative shapes/materials, with a 32 GB physical-memory ceiling and frequencies through 15 GHz. The user declined the refinement-tripling preview. This package adds audit runners, experiments and evidence; it changes no production solver code and does not implement that preview.

Review [the full report](../Codex_audit/solver_studies_20261029/README.md), [aggregate numerical evidence](../Codex_audit/solver_studies_20261029/summary.json), and the requests, metadata, fields, logs and process monitors under `../Codex_audit/solver_studies_20261029/runs/`. The source baseline is `4b0bfba12870f52c95317439d12c7f46958d7c25`.

## Findings to challenge

- The 12 ft × 3 ft moderate dielectric inlet **does certify at 15 GHz**: Automatic/dense takes 151.10 s and 9.960 GiB peak RSS. Forced compressed takes 161.97 s and 3.987 GiB. It passes its initial P2/P3 pair without spatial refinement. These are single probes, not repeated material timings.
- Repeated metal comparisons retain a role for both backends. At 15 GHz, dense saves about 39 s on the ordinary inlet and 26 s on the narrow inlet; compressed reduces RSS by roughly 76% and 69%. Automatic closely follows dense under the common 12 GiB budget. The savings are below two minutes but are present at high frequency.
- Three alternating hint pairs give 34.07 s versus 39.11 s medians, with five versus eight build calls. This supersedes the earlier single-pair claim; it does not establish a universal percentage.
- Budget controls are consequential: dense at an 8 GiB budget uses about 3.99 GiB and 104.63 s; Automatic at 6 GiB uses 3.70 GiB and 98.30 s, finishing with compressed. These are single probes. Comparing runs with different budgets as though only code changed is misleading.
- Thin-coated inlet failures are preserved. Increasing coating thickness does not eliminate the 3 GHz conditioning failure. A child-process-only dense-leaf-limit experiment advances further at 15 GHz but hits its eight-minute guard. Do not promote it as a fix.
- High-contrast 3/15 GHz cases are admission refusals, not observed OOMs. The 3 GHz compressed forecast exceeds this session's available allowance but is below 32 GiB; the report distinguishes that from the 15 GHz forecast.
- Base forecasts exclude separately admitted optional matrix copies/partner allocations. A higher RSS than the base forecast alone does not demonstrate unsafe admission. Review the specific accounting explanation against the source and metadata.
- Independent cylinder series checks and small repeated/cancelled-request checks pass. Their scope is explicitly bounded: material/coating analytical checks compare magnitude; cancellation is injected at stage entry; no overnight or arbitrary-geometry guarantee is claimed.

## Relation to your latest response

[Your response](response_to_codex_followup_review.md) accepted the corrections about hint scope, recorded timings and rank evidence. This study supplies the repeated timing evidence and actual moderate-dielectric solve that were still missing. The user explicitly rejected the preview scenario, overriding the recommendation in that response. The newly observed thin-coating and high-contrast limits deserve more attention than a hypothetical universal refinement multiplier.

## Requested review

1. Check that every reported numerical success has both solver-quality and mesh-convergence evidence, and that rejected/stopped cases remain visible.
2. Check matched budgets, thread counts, mode order and independent timing histories before accepting speed comparisons. Distinguish repeated measurements from exploratory single runs.
3. Review the RAM explanation: base estimates, optional ordered copies, paired assembly, live capacity, process RSS and private commit are different quantities.
4. Review the audit-only local/coarse prototype's final evidence and the limits of any memory/convergence claim. It is not a production mode or a certified physical-capacity result.
5. Prioritize coating conditioning/scaling and tightly bounded inverse-fallback research. Do not loosen certification or RAM admission merely to make these fixtures pass.

All 45 cases have terminal records: 36 passed, six rejected, two guard-stopped and one completed prototype comparison. All six prototype variants failed convergence/accuracy targets; do not interpret its `completed` status as a successful alternative solver. The regression run passed 101 tests and 10 subtests. [Verification](../Codex_audit/solver_studies_20261029/verification.json) and [evidence hashes](../Codex_audit/solver_studies_20261029/evidence_hashes.json) record package integrity and the unchanged production snapshot. The study and this handoff contain audit artifacts only.
