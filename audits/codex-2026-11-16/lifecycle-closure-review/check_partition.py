"""Hold tile policy fixed while changing workers; research wrapper only."""
import os,sys,json,hashlib,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import mesh_for,SimpleNamespace,NativeOracle,CPUState,_STATE,cpu_allocation_scope,execution_scope,exact_rows,op
R=Path(__file__).resolve().parent;D=R/'results';z=np.load(R/'prior/star-control.npz')
if (D/'partition.json').exists():raise RuntimeError('Refusing overwrite')
mesh=mesh_for(4096,'star');k=80.;eps=3-.08j
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
tile0=op._assembly_tile_size;commit0=op.CONCURRENT_FAR_COMMITS;maps={};hashes={};records=[]
sha=lambda a:hashlib.sha256(a.tobytes(order='C')).hexdigest()
try:
 for label,threads,policy,concurrent in [('default1',1,None,True),('default4',4,None,True),('workers4_tiles1',4,'default1',True),('workers1_tiles4',1,'default4',True),('workers4_tiles4_serial_commit',4,'default4',False)]:
    calls={}
    def tile(n,b,planned=True):
        key=str((n,b,planned));value=tile0(n,b,planned) if policy is None else maps[policy][key]
        calls[key]=value;return value
    op._assembly_tile_size=tile;op.CONCURRENT_FAR_COMMITS=concurrent;t=time.perf_counter()
    with threadpool_limits(limits=1,user_api='blas'),_STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(threads),execution_scope({'assembly_threads':threads,'blas_threads':1}):
        oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');e,q=exact_rows(oracle,z['rows'],8192)
        residual=e@z['density']-z['rhs'][z['rows']]
    hashes[label]=sha(e);maps[label]=calls
    rec=dict(label=label,assembly_threads=threads,tile_source=policy,concurrent_commits=concurrent,tile_sizes=calls,exact_sha256=sha(e),residual_sha256=sha(residual),seconds=time.perf_counter()-t)
    records.append(rec);print(json.dumps(rec),flush=True)
finally:op._assembly_tile_size=tile0;op.CONCURRENT_FAR_COMMITS=commit0
assert hashes['workers4_tiles1']==hashes['default1']
assert hashes['workers1_tiles4']==hashes['default4']==hashes['workers4_tiles4_serial_commit']
(D/'partition.json').write_text(json.dumps(records,indent=2))
