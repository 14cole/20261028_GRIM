"""Exercise table fallback explicitly, including a valid narrower table domain."""
import os,sys,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,str(Path(__file__).parent/'fmm'))
from fmm_galerkin import circle_mesh
from hybrid_galerkin import NearOracle
import native_pairs as native
mesh=circle_mesh(32);g=NearOracle(mesh,2.).g
args=(mesh.elements,np.array([0,1]),np.array([12,13]),2.,False,8)
kw=dict(prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals))
ref=native.original(*args,**kw);factory=native._kernel_table;fun=native.fun;table=factory(2.,0.,8.)
assert table is not None and table.native_checked
# Retain a contiguous subset of independently qualified intervals. The input
# distances are below this valid subdomain; the actual C kernel must return 2.
first=int(np.flatnonzero(table.bounds>3.)[0]);assert first<len(table.bounds)-1
narrow=SimpleNamespace(bounds=np.ascontiguousarray(table.bounds[first:]),normalized_power=np.ascontiguousarray(table.normalized_power[first:]),native_checked=True)
records=[]
try:
 for name,value in [('missing',None),('unqualified',SimpleNamespace(native_checked=False)),('below_domain',narrow)]:
  statuses=[]
  def recording(*args):
   status=fun(*args);statuses.append(status);return status
  native.fun=recording;native._kernel_table=lambda *args:value
  before=native.stats['fallback_calls'];got=native.fixed(*args,**kw)
  assert all(np.array_equal(a,b) for a,b in zip(ref,got))
  assert native.stats['fallback_calls']==before+1
  assert statuses==([2] if name=='below_domain' else [])
  records.append(dict(case=name,native_statuses=statuses,bitwise_reference=True,fallback_count_increment=1))
finally:native._kernel_table=factory;native.fun=fun
Path('native-fallbacks.json').write_text(json.dumps(records,indent=2));print(json.dumps(records))
