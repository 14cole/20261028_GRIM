"""Synthetic accounting reproduction; no GiB-sized arrays or real solves."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT/'tests')]
from test_request_memory_budget import simulated, Owned
from ghost_backend.execution import memory_budget as mb


def case(name, private_gib, overhead_gib, unique_gib=.1):
    class Worker:
        def incremental_memory_snapshot(self):
            return dict(complete=True, rss_bytes=mb.GIB,
                        private_bytes=int(private_gib*mb.GIB), unique_resident_bytes=0)
        def memory_snapshot(self):
            return dict(complete=True, rss_bytes=mb.GIB,
                        private_bytes=int(private_gib*mb.GIB), unique_resident_bytes=int(unique_gib*mb.GIB))
    with simulated(available=8, cap=3.5) as (live, ledger):
        worker, payload = Worker(), Owned(.5)
        mb.register(worker, 'workers')
        mb.register(payload)
        ledger.plan = dict(process_geometry_bytes=int(overhead_gib*mb.GIB))
        live.update(rss=3*mb.GIB, private=mb.GIB)
        record = dict(name=name, synthetic=True,
            inputs_gib=dict(available=8, reservation=3.5, numeric=.5, parent_rss_growth=3,
                parent_private_growth=1, worker_rss=1, worker_private=private_gib,
                worker_unique=unique_gib, modeled_overhead=overhead_gib, additional=.2))
        for label, exact in [('normal', False), ('detailed', True)]:
            try:
                ledger.require_reload(int(.2*mb.GIB), exact_workers=exact)
                result = dict(status='accepted')
            except MemoryError as exc:
                result = dict(status='refused', error=str(exc))
            result.update(limit_gib=ledger.last['limit_gib'], refined=ledger.last['worker_charge_refined'])
            record[label] = result
        record['false_refusal'] = record['normal']['status']=='refused' and record['detailed']['status']=='accepted'
        return record


rows = [case('worker_private_suppresses_recheck', 1.5, 0),
        case('modeled_overhead_suppresses_recheck', .2, 1.5),
        case('genuine_capacity_failure_control', 1.5, 0, unique_gib=1)]
manifest = json.loads((ROOT/'Codex_audit/optimization_followup_20261029/source_hashes.json').read_text())
matches = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in manifest.items()}
assert all(matches.values()), 'Source changed since the reviewed follow-up.'
record = dict(source_matches_reviewed_followup=matches, cases=rows,
              scope='Read-only source review and synthetic accounting calls; no production edits, full suite or end-to-end trials.')
(HERE/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
