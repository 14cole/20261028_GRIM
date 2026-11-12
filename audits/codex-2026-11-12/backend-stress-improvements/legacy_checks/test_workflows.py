"""Compare disk and memory residuals through certified/adaptive/frequency paths."""
import sys,json,tempfile,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.twod import solver as S
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.execution.options import execution_scope
from ghost_backend.execution.fresh_sweep import run_fresh

def geometry(n=600):
 t=-np.linspace(0,2*np.pi,n+1);p=[(np.cos(a),np.sin(a)) for a in t];p[-1]=p[0]
 xy='\n'.join('%.15g %.15g %.15g %.15g'%(*p[i],*p[i+1]) for i in range(n))
 return build_geometry_snapshot(*parse_geometry('Title: synthetic unit PEC circle\nSegment: b 2\nproperties: 2 1 0 0 0\n'+xy+'\nIBCS_Resistances:\nDielectrics:\n'))
def find(x,k):
 if isinstance(x,dict):
  if k in x:yield x[k]
  for v in x.values():yield from find(v,k)
 elif isinstance(x,list):
  for v in x:yield from find(v,k)
def main():
 output=(Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).parent)/'workflow-results.json'
 results=json.loads(output.read_text()) if len(sys.argv)>3 and output.exists() else []
 with tempfile.TemporaryDirectory() as temp:
  for kind in (sys.argv[3:] or ('survey','certified','adaptive','polynomial2','frequency_workers')):
   fields=[];details=[]
   for storage in ('memory','disk'):
    opts=dict(factorization='dense',dense_residual_storage=storage,mesh_strategy='adaptive' if kind=='adaptive' else 'global',assembly_threads='auto',blas_threads='auto',ram_budget_gib=8.,temporary_directory=temp)
    args=dict(geometry_snapshot=geometry(),frequencies_ghz=[.27,.3] if kind=='frequency_workers' else [.3],elevations_deg=list(np.linspace(0,180,19)),geometry_units='meters',max_panels=20000)
    if kind=='polynomial2':opts['basis_order']=2
    if kind=='frequency_workers':
     with execution_scope(opts,assembly_threads=4,memory_budget_gib=8.):
      r=run_fresh(S.solve_monostatic_rcs_2d_survey,args,opts,'double',False,frequency_workers=2)
     assert r['metadata']['frequency_execution']['maximum_active_workers']==2
    else:
     fn=S.solve_monostatic_rcs_2d_certified if kind in ('certified','adaptive') else S.solve_monostatic_rcs_2d_survey
     r=fn(**args,execution_options=opts)
    m=r['metadata'];gates=list(find(m,'quality_gate'));assert gates and all(g['passed'] for g in gates)
    spool=list(find(m,'residual_storage'))
    if storage=='disk':assert spool and all(v=='disk' for v in spool),(kind,spool)
    certified=list(find(m,'mesh_convergence_certified'))
    if kind in ('certified','adaptive'):assert any(certified),(kind,certified)
    fields.append(np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in r['samples']]))
    details.append(dict(storage=storage,backend=m.get('linear_backend'),storage_records=len(spool),certified=certified,quality_gates=len(gates),execution=m.get('frequency_execution')))
    assert not list(Path(temp).iterdir()),list(Path(temp).iterdir())
   err=float(np.max(abs(fields[0]-fields[1]))/max(np.max(abs(fields[0])),1e-300));assert err<1e-11,(kind,err)
   row=dict(case=kind,relative_error=err,samples=len(fields[0]),details=details);results.append(row);print('PASS',json.dumps(row),flush=True)
 ((Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).parent)/'workflow-results.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
