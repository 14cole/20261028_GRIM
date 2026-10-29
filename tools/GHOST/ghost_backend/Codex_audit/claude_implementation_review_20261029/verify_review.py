"""Allocation-free counterexamples for the review of commit 63429ba.

Real accounting functions, synthetic availability/residency. No giant arrays,
numerical solves, source-policy changes or actual host-pressure experiments.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT.parent))
from ghost_backend.execution import memory_budget as mb
from ghost_backend.execution.options import execution_scope
from ghost_backend.twod import solver
GIB=1024**3


class Owned:
    def __init__(self,gib):self.bytes=int(gib*GIB)


@contextmanager
def environment(available=20.,rss=0.,private=0.):
    state=dict(available=available,rss=rss,private=private)
    with patch.object(solver,'_detect_available_gb',side_effect=lambda:state['available']), \
         patch.object(mb,'process_memory',side_effect=lambda:(int(state['rss']*GIB),int(state['private']*GIB))), \
         patch('ghost_backend.execution.memory.windows_available_commit_bytes',return_value=100*GIB):
        yield state


@contextmanager
def request(cap=None):
    # Independent requests can coexist in different thread contexts. These
    # nested overrides reproduce their accounting without a scheduling race.
    with execution_scope(dict(factorization='compressed',ram_budget_gib=cap)), \
         mb._STATE.override(None),mb.scope() as ledger:
        yield ledger


def refusal(call):
    try:call()
    except MemoryError as exc:return str(exc)
    raise AssertionError('Expected current implementation to refuse')


out={}
with environment(rss=4.,private=4.) as live,request() as ledger:
    stable=ledger.stable()
    owner=Owned(4);ledger.register(owner,'operator')
    live.update(rss=8.,private=8.,available=6.)
    error=refusal(lambda:mb.admit_reload(2*GIB,workspace=0))
    out['reload_untracked_baseline']=dict(stable_gib=stable,owned_payload_gib=4.,
        process_rss_gib=8.,available_gib=6.,initial_reserve_gib=2.,
        additional_reload_gib=2.,true_total_after_reload_gib=10.,
        current_admitted_total_gib=ledger.last['limit_gib'],
        incremental_headroom_gib=4.,error=error)
    assert stable==18. and ledger.last['limit_gib']==8.

with environment(rss=1.,private=10.) as live,request() as ledger:
    ledger.stable();live['available']=8.
    error=refusal(lambda:mb.admit_reload(GIB,workspace=0))
    out['reload_commit_mixed_into_ram']=dict(process_rss_gib=1.,private_commit_gib=10.,
        additional_reload_gib=1.,physical_total_after_reload_gib=2.,
        live_physical_headroom_gib=6.,current_required_total_gib=11.,
        available_commit_gib=100.,error=error)

with environment(rss=.5,private=.5) as live,request() as ledger:
    ledger.stable();owner=Owned(4);ledger.register(owner,'operator')
    live.update(rss=4.5,private=4.5,available=6.)
    mb.record_plan(dict(phase_bytes=dict(solve=int(8.3*GIB))))
    error=refusal(lambda:mb.admit_phase('solve'))
    out['phase_existing_baseline']=dict(predicted_total_gib=8.3,already_owned_payload_gib=4.,
        already_resident_baseline_gib=.5,additional_need_gib=3.8,
        live_additional_headroom_gib=4.,error=error,
        limitation='Hypothetical phase whose baseline is already resident; not all real forecast overhead is resident.')

with environment(available=24.) as live:
    with request(12.) as first:
        a=first.stable()
        with request(12.) as second:
            b=second.stable()
            first_owner,second_owner=Owned(10),Owned(9)
            first.register(first_owner,'operator');second.register(second_owner,'operator')
            # 19 GiB of numeric allocations, 10 GiB of combined physical growth.
            # This can represent paged or not-yet-resident numeric storage.
            live.update(available=14.,rss=10.,private=19.)
            credits=[first.owned()[1],second.owned()[1]]
            with request(24.) as third:
                c=third.stable()
                out['shared_process_credit']=dict(initial_available_gib=24.,
                    initial_ninety_percent_budget_gib=21.6,actual_combined_rss_growth_gib=10.,
                    credited_growth_per_request_gib=credits,sum_credits_gib=sum(credits),
                    stable_reservations_gib=[a,b,c],sum_reservations_gib=a+b+c,
                    remaining_available_gib=14.,
                    limitation='Deterministic overlapping-request accounting counterexample, not an actual OOM or threaded load test.')
                assert credits==[10.,9.] and abs(a+b+c-30.6)<1e-8

summary=json.loads((HERE.parent/'memory_estimation_20261029/live_summary.json').read_text())
p=summary['peak_forecast_components']
workspace=p['process_geometry_bytes']+p['rhs_workspace_bytes']+p['gmres_workspace_bytes']+p['projection_cache_bytes']
out['workspace_and_floor']=dict(saved_inlet_solve_nonstorage_gib=workspace/GIB,
    saved_inlet_factorization_nonstorage_gib=(p['process_geometry_bytes']+
        p['inverse_construction_bytes']-p['inverse_ceiling_bytes'])/GIB,
    floor_counterexample=dict(total_budget_gib=10.,workspace_gib=6.,safe_payload_gib=4.,
        sixty_percent_floor_gib=6.,resulting_total_gib=12.),
    limitation='The saved inlet workspace must not be reused as a constant for larger geometries.')
for name,expected in json.loads((HERE.parent/'memory_implementation_20261029/source_hashes.json').read_text()).items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
paths=['execution/memory_budget.py','compressed/memory.py','compressed/runtime.py',
       'Claude_audit/review_of_codex_memory_implementation.md']
out['verification']=dict(status='passed',reviewed_commit='63429ba0cf5d20f49324675e0cdc4b61588f9cfc',
    implementation_source_hashes_unchanged=True,
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths})
(HERE/'verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
