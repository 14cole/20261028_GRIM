"""Shared spool in BoR; Dense fields with native far blocks unavailable."""
import json, sys, tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1]).resolve()/'tools/GHOST'))
from ghost_backend.execution.options import execution_scope
from ghost_backend.bor.factor import ModalFactor
from ghost_backend.geometry.io import build_geometry_snapshot,parse_geometry
from ghost_backend.twod import solver as S
from ghost_backend.twod.assembly.native import far
out=Path(sys.argv[2]);results=[]
with tempfile.TemporaryDirectory() as temp:
 rng=np.random.default_rng(198);n=521
 a=np.asarray(rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))+n*np.eye(n),complex,order='F')
 b=rng.normal(size=(n,7))+1j*rng.normal(size=(n,7));xs=[]
 with execution_scope(dict(blas_threads=1,assembly_threads=1),limit_blas=True):
  for mode in ('memory','disk'):
   factor=ModalFactor(a.copy(order='F'),0,True,owned=True,residual_storage=(mode,temp))
   x=factor.solve(b);xs.append(x)
   assert np.linalg.norm(a@x-b)/np.linalg.norm(b)<1e-12
   assert factor.event['residual_storage']==mode
   factor.close()
 np.testing.assert_allclose(xs[0],xs[1],rtol=1e-12,atol=1e-12)
 results.append(dict(case='BoR shared spool',max_abs_difference=float(np.max(abs(xs[0]-xs[1])))))
 for degree in (1,2):
  t=-np.linspace(0,2*np.pi,65);p=list(zip(np.cos(t),np.sin(t)));p[-1]=p[0]
  xy='\n'.join('%.15g %.15g %.15g %.15g'%(*p[i],*p[i+1]) for i in range(64))
  g=build_geometry_snapshot(*parse_geometry('Title: fallback\nSegment: b 2\nproperties: 2 1 0 0 0\n'+xy+'\nIBCS_Resistances:\nDielectrics:\n'))
  opts=dict(factorization='dense',dense_residual_storage='disk',basis_order=degree,assembly_threads=1,blas_threads=1,temporary_directory=temp)
  args=dict(geometry_snapshot=g,frequencies_ghz=[.3],elevations_deg=[0,30,90,180],geometry_units='meters',execution_options=opts)
  ref=S.solve_monostatic_rcs_2d_survey(**args)
  with patch.object(far,'far_block',return_value=None) as unavailable:
   run=S.solve_monostatic_rcs_2d_survey(**args)
  assert unavailable.call_count>0
  def fields(r):return np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in r['samples']])
  error=float(np.max(abs(fields(run)-fields(ref)))/np.max(abs(fields(ref))))
  assert error<1e-10,error
  assert run['metadata']['quality_gate']['passed']
  results.append(dict(case=f'P{degree} numpy far fallback',relative_error=error,fallback_blocks=unavailable.call_count))
 assert not list(Path(temp).iterdir())
(out/'alternate-paths.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
