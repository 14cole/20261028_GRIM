"""Render all measured cases from analysis.json without hand-transcribed numbers."""
from pathlib import Path
import json
root=Path(__file__).resolve().parent
analysis=json.loads((root/'analysis.json').read_text())
lines=['# Complete measurement tables','',
       'All times are seconds. Peak RAM is process high-water RSS in GiB. Compute',
       'is setup + RHS + solve + matched projection, excluding extra audit validation',
       'and array serialization. Measurements are single samples, not confidence intervals.',
       '', '| Case | Unknowns | Angles | Setup | Solve | Compute | Peak GiB | Accurate A RHS-equivalents |',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
for r in analysis['table']:
    lines.append(f"| `{r['label']}` | {r['unknowns']} | {r['count']} | {r['setup']:.3f} | {r['solve']:.3f} | {r['compute']:.3f} | {r['peak']:.4f} | {r['matvecs'] or '—'} |")
lines += ['', 'A counts include true residual checks. For batched/block methods they sum',
          'actual RHS column widths, not just traversal calls; these are not FLOP counts.',
          '', '## Full complex-array comparisons', '',
          '| Candidate | Dense reference | Field / reference peak | Max per-angle density L2 relative | RHS L2 relative | Passed |',
          '|---|---|---:|---:|---:|---|']
for c in analysis['comparisons']:
    lines.append(f"| `{c['label']}` | `{c['reference']}` | {c['field_max_relative']:.3e} | {c['density_relative_l2_max']:.3e} | {c['rhs_relative_l2_max']:.3e} | {c['passed']} |")
lines += ['', '## Incident-load rank scans', '',
          'These are RHS-only QR scans, not solves. They use production row-max scaling',
          'and a 2e-15 relative Frobenius threshold. FMM solve-basis ranks use a different',
          'equilibration and need not match these ranks exactly.', '',
          '| Unknowns | k | Angles | Range | Rank | RHS reconstruction relative |',
          '|---:|---:|---:|---|---:|---:|']
for r in json.loads((root/'rank-scan.json').read_text()):
    lines.append(f"| {r['unknowns']} | {r['k']} | {r['count']} | [{r['start']}, {r['stop']}) | {r['rank']} | {r['relative_rhs_error']:.3e} |")
lines += ['', '## Rejected numerical runs', '', json.dumps(analysis['failures'],indent=2), '']
(root/'RESULT_TABLES.md').write_text('\n'.join(lines))
counts=dict(successful_cases=len(analysis['table']),physical_incident_columns=sum(r['count'] for r in analysis['table']),dense_comparisons=len(analysis['comparisons']),failed_numerical_runs=len(analysis['failures']),failed_comparisons=sum(not c['passed'] for c in analysis['comparisons']),max_field_relative=max(c['field_max_relative'] for c in analysis['comparisons']),max_density_relative=max(c['density_relative_l2_max'] for c in analysis['comparisons']),max_rhs_relative=max(c['rhs_relative_l2_max'] for c in analysis['comparisons']))
(root/'COUNTS.json').write_text(json.dumps(counts,indent=2))
print(json.dumps(counts))
