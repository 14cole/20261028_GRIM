"""Render the handoff directly from verified results."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
a=json.loads((HERE/'analysis.json').read_text())
rows={r['label']:r for r in a['fresh_cases']}
v=rows['star-8192-180-v3'];z=rows['star-8192-180-z'];c=rows['star-8192-180-compressed']
validation=json.loads((HERE/'archive-verification.json').read_text())
fresh=json.loads((HERE/'fresh-row-check.json').read_text())
head=f'''# Stored-basis FMM review and independent reproduction

Reviewed Claude commit `0328f1fde93a63062ea9938cfff154a8893b2730`.
Parent Codex commit `9ce0f99e362c99313e27b0637fbca196d853a09a`.
Branch: `codex/fmm-stored-basis-review-2026-11-15`.

**The final-preconditioner recombination diagnosis reproduces.** In the fresh
8k/180-angle comparison, stored Z reduced compute by
{100*(1-z['compute_seconds']/v['compute_seconds']):.1f}% and accurate operator
applications by {100*(1-z['applications']/v['applications']):.1f}%, with peak
process memory changing from {v['peak_gib']:.3f} to {z['peak_gib']:.3f} GiB.
It still took {z['compute_seconds']/c['compute_seconds']:.1f} times the fresh
Compressed control's compute time. This is one paired comparison, not a
statistical speedup guarantee. Production remains unchanged.

## Fresh measurements

| Case | Compute seconds | Solve seconds | Peak GiB | Accurate RHS-equivalent applications | Cycles | Nonconverged true checks |
|---|---:|---:|---:|---:|---:|---:|
'''
for label in ('star-8192-180-compressed','star-8192-180-v3','star-8192-180-z','square-1024-180-TE-z','slot-1024-180-TE-z','slot-1024-180-TM-z'):
    r=rows[label];fmm=r['method']=='fmm'
    head+=f"| {label} | {r['compute_seconds']:.2f} | {r['solve_seconds']:.2f} | {r['peak_gib']:.3f} | {r['applications'] if fmm else '—'} | {r['cycles'] if fmm else '—'} | {r['failed_checks'] if fmm else '—'} |\n"
head+=f'''
Seven fresh physical cases completed, including the separate instrumented
eight-angle diagnostic: **1,088 incident columns**. Every case passed comparison
with the archived Dense reference. Maximum peak-normalized field difference:
{max(x['peak_normalized_field_error'] for x in rows.values()):.3e}; maximum
per-angle density relative L2 difference:
{max(x['max_density_relative_l2'] for x in rows.values()):.3e}. Maximum saved
exact-row backward error: {max(x['exact_row_backward_error'] for x in rows.values()):.3e}.

The fresh 16-row check of Claude's supplied 32k/24 density passed with maximum
backward error {fresh['max_exact_row_backward_error']:.3e}. This is an independent
equation check, not a newly timed 32k solve. The new 8k v3 solution agrees with
Claude's supplied v3 density to
{a['claude_published_array_checks'][0]['fresh_v3_comparison']['max_density_relative_l2']:.3e}
maximum per-angle relative L2 difference.

The local evidence archive restored {validation['arrays_bitwise_verified']}
numerical arrays bit for bit, and the restored analysis matched exactly.
All {validation['production_files_unchanged']} production file hashes remained
unchanged. See `analysis.json`, `independent-checks.json`, `fresh-row-check.json`,
`source-provenance.json`, `archive-verification.json`, and `README_REPRO.md`.

'''
(HERE/'HANDOFF_STORED_BASIS_REVIEW.md').write_text(head+(HERE/'REPORT_BODY.md').read_text())
print(head)
