"""Behavior and preservation checks for the backend cleanup.

Run with the cleaned tools/GHOST on PYTHONPATH. Optionally supply
--baseline-root /path/to/original/repository for exact AST/evidence comparison.
"""
import argparse
import ast
import asyncio
import copy
import importlib
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--baseline-root')
parser.add_argument('--probe-certification',action='store_true')
parser.add_argument('--standalone',action='store_true')
args=parser.parse_args()

def certification_cases():
    quality={'passed':True}
    mesh=dict(passed=True,published_mesh='fine',base_quality_gate=quality,fine_quality_gate=quality)
    legacy=dict(contract='legacy-workflow-unit.v1',mesh_convergence=mesh)
    record=dict(schema='ghost.workflow.mesh-certified-sources.v1',passed=True,published_mesh='fine',sources=[legacy],source_count=1)
    hashes={key:'a'*64 for key in ('solver_source_sha256','runtime_environment_sha256','geometry_input_sha256',
        'run_solve_spec_sha256','unit_solve_spec_sha256','solver_config_sha256','angular_grid_sha256')}
    attestation=dict(schema='ghost.workflow.embedded-attestation.v1',run_id='test',frequency_ghz=1.,
                     angular_grid_kind='azimuths_deg',polarization='HH',**hashes)
    metadata=dict(mesh_convergence=mesh,quality_gate=quality,output_attestation=attestation)
    single=dict(polarizations=['HH'],frequencies=[1.],solver_metadata_json=json.dumps(dict(metadata=metadata)))
    dual_attestation=dict(attestation);dual_attestation.pop('polarization');dual_attestation['polarizations']=['VV','HH']
    channels={p:dict(mesh_convergence=mesh,quality_gate=quality,mesh_convergence_certified=True,
                    certified_entry_point=True,published_mesh='fine') for p in ('VV','HH')}
    aggregate_quality=dict(passed=True,channels={p:quality for p in channels})
    aggregate_mesh=dict(passed=True,published_mesh='fine',base_quality_gate=aggregate_quality,
                        fine_quality_gate=aggregate_quality,channels={p:mesh for p in channels})
    dual_metadata=dict(mesh_convergence=aggregate_mesh,quality_gate=aggregate_quality,
                       output_attestation=dual_attestation,polarizations=['VV','HH'],
                       polarization_mapping={'VV':'TE','HH':'TM'},channel_metadata=channels,
                       mesh_convergence_certified=True,certified_entry_point=True,published_mesh='fine')
    dual=dict(polarizations=['VV','HH'],frequencies=[1.],solver_metadata_json=json.dumps(dict(metadata=dual_metadata,polarizations=['VV','HH'])))
    bad_count=copy.deepcopy(record);bad_count['source_count']=2
    bad_claim=copy.deepcopy(record);bad_claim['certifies_coherent_delta_convergence']=True
    bad_gate=copy.deepcopy(record);bad_gate['sources'][0]['mesh_convergence']['fine_quality_gate']={'passed':False}
    missing_channel=copy.deepcopy(dual_metadata);missing_channel['channel_metadata'].pop('HH')
    bad_frequency=copy.deepcopy(single);bad_frequency['frequencies']=[2.]
    bad_hash=copy.deepcopy(metadata);bad_hash['output_attestation']['solver_source_sha256']='bad'
    return [
        ('absent',{},False),
        ('no mesh',{'solver_metadata_json':json.dumps({'metadata':{}})},False),
        ('legacy source chain',{'production_mesh_certification_json':json.dumps(record)},False),
        ('malformed JSON',{'production_mesh_certification_json':'{'},True),
        ('source count mismatch',{'production_mesh_certification_json':json.dumps(bad_count)},True),
        ('false convergence claim',{'production_mesh_certification_json':json.dumps(bad_claim)},True),
        ('failed fine quality gate',{'production_mesh_certification_json':json.dumps(bad_gate)},True),
        ('single-channel attestation',single,False),
        ('dual-channel attestation',dual,False),
        ('missing channel',dict(dual,solver_metadata_json=json.dumps(dict(metadata=missing_channel,polarizations=['VV','HH']))),True),
        ('frequency mismatch',bad_frequency,True),
        ('invalid hash',dict(single,solver_metadata_json=json.dumps(dict(metadata=bad_hash))),True),
    ]

if args.probe_certification:
    name='cem_tools.grim_native' if args.standalone else 'ghost_backend.data_tools.cem_tools.grim_native'
    module=importlib.import_module(name);observed=[]
    for label,payload,want_error in certification_cases():
        try:
            result=module._mesh_certification_sources(payload,'fixture')
            observed.append(dict(case=label,result=result,error=None))
        except Exception as exc:
            observed.append(dict(case=label,result=None,error=[type(exc).__name__,str(exc)]))
        assert bool(observed[-1]['error'])==want_error,observed[-1]
    print(json.dumps(observed,sort_keys=True));raise SystemExit(0)

checks=[]
def check(name,value):
    assert value,name
    checks.append(name);print('PASS',name,flush=True)

import ghost_backend.execution.runtime as runtime
from ghost_backend.execution import thread_control
import ghost_backend.data_tools.cem_tools.grim_native as gn
root=Path(runtime.__file__).resolve().parents[2]
check('GHOST uses stdlib dataclasses and retained BLAS implementation',
      runtime.dataclass.__module__=='dataclasses' and thread_control.implementation.__file__.endswith('/_threadpoolctl.py'))
check('ordinary CEM import does not load certification implementation',
      'ghost_backend.data_tools.cem_tools.certification_evidence' not in sys.modules)
check('legacy inspection entry still returns absent evidence',gn._mesh_certification_sources({},'fixture') is None)
check('explicit inspection loads optional implementation',
      'ghost_backend.data_tools.cem_tools.certification_evidence' in sys.modules)

value=runtime.ScopedValue('cleanup-check',default='default')
try:
    with value.override('outer'):
        check('outer scoped setting visible',value.get()=='outer')
        with value.override('inner'):
            check('nested scoped setting visible',value.get()=='inner')
        check('nested scope restores outer',value.get()=='outer')
        raise RuntimeError('test')
except RuntimeError:
    pass
check('exception restores scoped default',value.get()=='default')
barrier=threading.Barrier(2)
def thread_case(name):
    with value.override(name):
        barrier.wait();return value.get()
with ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(thread_case,name) for name in ('a','b')]
    check('thread scopes remain isolated',[f.result() for f in futures]==['a','b'])
async def async_cases():
    async def one(name):
        with value.override(name):
            await asyncio.sleep(0);return value.get()
    return await asyncio.gather(one('a'),one('b'))
check('async scopes remain isolated',asyncio.run(async_cases())==['a','b'])

def probe(pythonpath,standalone=False):
    env=dict(os.environ,PYTHONPATH=str(pythonpath))
    cmd=[sys.executable,str(Path(__file__).resolve()),'--probe-certification']
    if standalone:cmd.append('--standalone')
    return json.loads(subprocess.check_output(cmd,env=env,text=True))
new=probe(root)
check('12 evidence cases accept valid inputs and reject malformed inputs',len(new)==12)
standalone=probe(root/'ghost_backend/data_tools',True)
check('standalone CEM and embedded CEM inspection agree',standalone==new)
check('new optional module retains Python 3.6 syntax compatibility',
      ast.parse((root/'ghost_backend/data_tools/cem_tools/certification_evidence.py').read_text(),feature_version=(3,6)) is not None)

if args.baseline_root:
    baseline=Path(args.baseline_root)/'tools/GHOST'
    old=probe(baseline)
    check('inspection results and exact errors match baseline on all 12 cases',old==new)
    removals={
        'bor/kernels.py':{'_checked_near_kernels','_cosine_moments','_project_parity_brackets'},
        'bor/solver.py':{'_cell_points','_graded_cells'},
        'twod/formulations/regions.py':{'_assemble_system_fresh'},
    }
    for path,names in removals.items():
        before=ast.parse((baseline/'ghost_backend'/path).read_text())
        after=ast.parse((root/'ghost_backend'/path).read_text())
        before.body=[n for n in before.body if not (isinstance(n,ast.FunctionDef) and n.name in names)]
        check('all retained numerical AST unchanged: '+path,ast.dump(before)==ast.dump(after))
    before=ast.parse((baseline/'ghost_backend/data_tools/cem_tools/grim_native.py').read_text())
    after=ast.parse((root/'ghost_backend/data_tools/cem_tools/grim_native.py').read_text())
    moved=ast.parse((root/'ghost_backend/data_tools/cem_tools/certification_evidence.py').read_text())
    old_functions={n.name:n for n in before.body if isinstance(n,ast.FunctionDef)}
    moved_names=set()
    for node in moved.body:
        if isinstance(node,ast.FunctionDef):
            name='_mesh_certification_sources' if node.name=='mesh_certification_sources' else node.name
            node.name=name;moved_names.add(name)
            check('moved inspection AST unchanged: '+name,ast.dump(node)==ast.dump(old_functions[name]))
    before.body=[n for n in before.body if not (isinstance(n,ast.FunctionDef) and n.name in moved_names)]
    after.body=[n for n in after.body if not (isinstance(n,ast.FunctionDef) and n.name=='_mesh_certification_sources')]
    check('ordinary dataset operation AST unchanged',ast.dump(before)==ast.dump(after))

Path(__file__).with_name('cleanup-check-results.json').write_text(json.dumps(dict(passed=len(checks),checks=checks,certification_cases=new),indent=2))
print('Passed:',len(checks))
