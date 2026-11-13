import os,sys,json,runpy,cProfile,pstats,io,contextlib
from pathlib import Path
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,str(Path(__file__).parent/'fmm'))
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
spec=json.loads(sys.argv[1]);native=spec.pop('native_pairs',False)
if native:
 import native_pairs as pairs
 from hybrid_galerkin import NearOracle
 reference_pairs=NearOracle.pairs_values
 def native_near(self,i,j):
  # The research operator alone gets the native routine. The preconditioner,
  # independent exact rows and optional Dense reference remain unmodified.
  saved=pairs.op._integrate_linear_pairs_box_sk_batched
  pairs.install()
  try:return reference_pairs(self,i,j)
  finally:pairs.op._integrate_linear_pairs_box_sk_batched=saved
 NearOracle.pairs_values=native_near
from preconditioned_solve import main
p=cProfile.Profile();state=CPUState(kernel_only=True);state.reuse_operators=False
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 if spec.get('profile'):p.enable()
 capture=io.StringIO()
 with contextlib.redirect_stdout(capture):main(spec)
 result=json.loads(capture.getvalue().splitlines()[-1])
 if spec.get('profile'):
  p.disable();p.dump_stats(spec['out']+'.prof')
  with open(spec['out']+'.profile.txt','w') as f:pstats.Stats(p,stream=f).strip_dirs().sort_stats('cumulative').print_stats(65)
if native:assert pairs.op._integrate_linear_pairs_box_sk_batched is pairs.original
result.update(native_pairs=native,native_scope='FMM NearOracle only',pair_stats=pairs.stats if native else None,kernel_tables=state.table_events)
Path(spec['out']+'.json').write_text(json.dumps(result,indent=2))
