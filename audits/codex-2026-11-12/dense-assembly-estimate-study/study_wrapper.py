"""Research-only instrumentation/prototype; never imported by GHOST production.

Run: python study_wrapper.py RUNTIME_ROOT JSON_SPEC
The candidate workspace coefficients are conservative hypotheses, NOT proven
allocation bounds. Normal planning, factor admission and numerical gates remain.
"""
import contextvars, json, runpy, sys, time
from pathlib import Path
root, raw = sys.argv[1:3]
spec = json.loads(raw)
sys.path.insert(0, str(Path(root)/'tools/GHOST'))
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.execution import dense_memory as dm
from ghost_backend.twod import solver as s, operators as ops
from ghost_backend.twod.formulations import dielectric, regions
from ghost_backend.twod.assembly.native import far
import psutil

records = dict(resources=[], forecasts=[], assemblies=[], tiles=[], near=[], fallback_calls=0,
               large_zeros=[], no_table_calls=0)
process = psutil.Process()
active = contextvars.ContextVar('estimate_resources', default=None)
resources0 = s._dense_formulation_resources
def resources(*args, **kwargs):
    answer = resources0(*args, **kwargs)
    if answer['formulation'] == 'single_dielectric':
        answer['study_near_pairs'] = regions.mesh_near_pair_count(args[0])
        records['resources'].append({k: answer[k] for k in
            ('nodes', 'panels', 'basis_width', 'system_dofs', 'study_near_pairs')})
    return answer
s._dense_formulation_resources = resources
estimate0 = s._estimate_memory_gb
def estimate(*args, **kwargs):
    token = active.set(kwargs.get('dense_resources'))
    try: return estimate0(*args, **kwargs)
    finally: active.reset(token)
s._estimate_memory_gb = estimate
forecast0 = dm.forecast
def forecast(d, count, batch, assembly, solve, extra, eligible, submission=False):
    r = active.get()
    old = assembly
    breakdown = None
    if spec.get('prototype') and r and r['formulation'] == 'single_dielectric' and r['basis_width'] == 2:
        # Restrict the experiment to an explicit 128 tile: there is no circular
        # assumption that admission will later select a smaller implicit tile.
        assert spec['options']['assembly_tile'] == 128
        n, e, q, w = r['nodes'], r['panels'], r['study_near_pairs'], r['basis_width']
        tile = min(e, 128)
        workers = ops.get_assembly_threads()
        retained = 64*w*w+64  # four operator arrays and scale/mask buffers
        active_scratch = 1024+64*w*w  # deliberately generous provisional allowance
        far_bytes = workers*tile*tile*(3*retained+active_scratch)
        near_bytes = 256*min(ops._NEAR_BATCH_MAX_SAMPLES, q*256)
        breakdown = dict(matrix=16*d*d, fixed=64*1024**2, linear=8192*n,
            near_metadata=128*q, near_store=min(16*1024**2, 3*16*w*w*q),
            far_workspace=far_bytes, near_workspace=near_bytes, tile=tile, workers=workers)
        assembly = sum(breakdown[k] for k in ('matrix','fixed','linear','near_metadata','near_store')) + max(far_bytes,near_bytes)
    answer = forecast0(d,count,batch,assembly,solve,extra,eligible,submission=submission)
    records['forecasts'].append(dict(old_assembly=old, candidate_assembly=assembly,
        breakdown=breakdown, plan=answer.copy()))
    return answer
dm.forecast = forecast
assemble0 = dielectric.assemble_system
def assemble(*args, **kwargs):
    t = time.perf_counter()
    row = dict(pol=args[2], n=len(args[0].nodes), start_rss=process.memory_info().rss)
    records['assemblies'].append(row)
    if spec.get('unequal_orders'):
        args=list(args)
        for position,key,value in ((4,'obs_order',8),(5,'src_order',7)):
            if len(args)>position:args[position]=value
            else:kwargs[key]=value
    try: return assemble0(*args, **kwargs)
    finally: row.update(end_rss=process.memory_info().rss, seconds=time.perf_counter()-t)
dielectric.assemble_system = assemble
tile0 = ops._assembly_tile_size
def tile(*args, **kwargs):
    result = tile0(*args, **kwargs)
    row = dict(elements=args[0], bytes_per_entry=args[1], tile=result, planned=kwargs.get('planned',True))
    if row not in records['tiles']: records['tiles'].append(row)
    return result
ops._assembly_tile_size = tile
expand0 = ops._expand_near_chunks
def expand(*args, **kwargs):
    result = expand0(*args, **kwargs)
    records['near'].append(dict(pairs=len(result[0]), rss=process.memory_info().rss))
    return result
ops._expand_near_chunks = expand
if spec.get('fallback'):
    def unavailable(*args, **kwargs):
        records['fallback_calls'] += 1
        return None
    far.far_block = unavailable
    # Exercise scatter fallback too, independently of far quadrature.
    far.tile_library = lambda: None
    far.scatter_library = lambda: None

if spec.get('no_tables'):
    from ghost_backend.twod.assembly import kernels
    from ghost_backend.twod import polynomial_quadrature as pq
    def no_far_table(mesh,k,green,hankel,domain_upper=None):
        records['no_table_calls']+=1
        return green,hankel
    kernels.select_far_kernels=no_far_table
    pq._table_for_ends=lambda *args,**kwargs: None

if spec.get('allocation_probe'):
    import numpy as np, traceback
    zeros0 = np.zeros
    def zeros(shape,*args,**kwargs):
        value = zeros0(shape,*args,**kwargs)
        if value.ndim==2 and min(value.shape)>=spec['n']:
            records['large_zeros'].append(dict(shape=value.shape,bytes=value.nbytes,
                stack=[f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}'
                       for frame in traceback.extract_stack(limit=8)[:-1]]))
        return value
    np.zeros=zeros

script = str(Path(__file__).with_name('profile_solve.py'))
sys.argv = [script, root, raw]
try:
    with cpu_allocation_scope(spec.get('allocation_cpus',4)):
        runpy.run_path(script, run_name='__main__')
finally:
    Path(spec['out']+'.study.json').write_text(json.dumps(records,indent=2)+'\n')
