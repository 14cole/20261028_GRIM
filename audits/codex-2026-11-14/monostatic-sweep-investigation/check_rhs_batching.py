"""Reproduce batch-boundary roundoff independently of every linear solve."""
import json,os,numpy as np
from pathlib import Path
from monostatic import mesh_for,dielectric,CPUState,_STATE,cpu_allocation_scope,execution_scope
from evidence_paths import batches
root=Path(__file__).resolve().parent
results=Path(os.environ.get('MONOSTATIC_RESULTS',str(root/'results')))
checks=[]
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    for n,k in ((1024,20),(4096,80)):
        mesh=mesh_for(n,'star')
        for count,start,stop in ((180,-90,90),(360,0,360)):
            angles=np.linspace(start,stop,count,endpoint=False)
            generated={width:np.concatenate([dielectric.rhs_many(mesh,k,angles[first:first+width]) for first in range(0,count,width)],axis=1) for width in (16,64,256)}
            reference=generated[64]
            for width,rhs in generated.items():
                difference=rhs-reference
                rel=float(np.max(np.linalg.norm(difference,axis=0)/np.linalg.norm(reference,axis=0)))
                peak=float(np.max(abs(difference))/np.max(abs(reference)))
                assert rel<5e-15 and peak<5e-15
                checks.append(dict(unknowns=2*n,count=count,batch=width,rhs_relative_l2_max=rel,rhs_peak_relative=peak,bitwise_equal=np.array_equal(rhs,reference)))
            if n==1024 and count==180:
                for label,width in [('star-2048-180-dense-cold',64),('star-2048-180-fmm-rhs_qr',256)]:
                    paths=batches(results,label)
                    consolidated=results/(label+'.npz')
                    if paths or consolidated.exists():
                        saved=np.concatenate([np.load(p,allow_pickle=False)['rhs'] for p in paths],axis=1) if paths else np.load(consolidated,allow_pickle=False)['rhs']
                        relative=float(np.linalg.norm(saved-generated[width])/np.linalg.norm(saved))
                        assert relative<5e-15,(label,relative)
                        checks.append(dict(saved_case=label,batch=width,fresh_rhs_bitwise_equal=np.array_equal(saved,generated[width]),fresh_rhs_relative_l2=relative))
print(json.dumps(checks,indent=2))
