"""Read recorded trials; compare matching successful dense/compressed runs."""
import collections
import csv
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'trials/airfoil_matrix_20261027_full/summary.csv'
FIELDS = ('frequency_ghz', 'mesh_strategy', 'basis_order', 'mesh_grading')
METRICS = ('solve_wall_seconds', 'worker_wall_seconds', 'process_wall_seconds')


def main():
    with SOURCE.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    groups = collections.defaultdict(dict)
    for row in rows:
        if row['role'] == 'trial' and row['status'] == 'ok':
            key = tuple(row[field] for field in FIELDS)
            assert row['factorization'] not in groups[key], 'Ambiguous duplicate trial'
            groups[key][row['factorization']] = row
    pairs = []
    for key, group in groups.items():
        if not {'dense', 'compressed'} <= group.keys():
            continue
        dense, compressed = group['dense'], group['compressed']
        assert dense['panel_count'] == compressed['panel_count']
        pairs.append(dict(case=dict(zip(FIELDS, key)), dense_id=dense['id'],
            compressed_id=compressed['id'], panel_count=int(dense['panel_count']),
            accuracy_status={m: group[m]['accuracy_status'] for m in ('dense', 'compressed')},
            defects={m: group[m]['defects'] for m in ('dense', 'compressed')},
            actual_factorization={m: group[m]['actual_factorization'] for m in ('dense', 'compressed')},
            times={metric: dict(dense=float(dense[metric]), compressed=float(compressed[metric]),
                dense_saving_seconds=float(compressed[metric])-float(dense[metric])) for metric in METRICS}))
    summary = {}
    for metric in METRICS:
        savings = [pair['times'][metric]['dense_saving_seconds'] for pair in pairs]
        summary[metric] = dict(matched_pairs=len(pairs), dense_faster=sum(s > 0 for s in savings),
            max_dense_saving_seconds=max(savings), median_dense_saving_seconds=statistics.median(savings),
            five_minute_savings=sum(s >= 300 for s in savings), aggregate_dense_saving_seconds=sum(savings))
    pairs.sort(key=lambda pair: pair['times']['solve_wall_seconds']['dense_saving_seconds'], reverse=True)
    result = dict(source=str(SOURCE.relative_to(ROOT)), matching_fields=FIELDS,
        filter='Trial rows, status ok in both modes, same panel count. References and failed runs excluded.',
        limitation='Operational success is not independent accuracy certification; retain original accuracy flags.',
        summary=summary, pairs=pairs)
    (HERE / 'airfoil_comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
