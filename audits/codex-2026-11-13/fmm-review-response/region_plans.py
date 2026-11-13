import pathlib,sys,json,os,numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from fmm_galerkin import circle_mesh
from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
from cached_fmm import HelmholtzFMM
D=pathlib.Path(__file__).parent;rows=[]
for n,k0,star in [(128,3,False),(128,12,True),(512,40,True)]:
 mesh=circle_mesh(n,star=star,inward=True);g=AssemblyGeometry(mesh);q=(np.polynomial.legendre.leggauss(8)[0]+1)/2;x=(g.p0[:,None]+q[None,:,None]*g.segments[:,None]).reshape(-1,2)
 for region,k in [('exterior',complex(k0)),('interior',k0*np.sqrt(3-.08j))]:
  f=HelmholtzFMM(x,np.repeat(g.normals,8,axis=0),k.conjugate(),digits=10,leaf_wavelengths=1.5,separation=2,tile_points=256,gradients=True,near_storage=False,partition_points=np.repeat(g.centers,8,axis=0),support_radius=max(g.lengths)/2)
  leaf=np.empty(len(x),int);leaf[f.order]=f.leaf_of_point;leaf=leaf.reshape(-1,8)[:,0];counts=np.bincount(leaf,minlength=len(f.leaf_start));pairs=sum(counts[i]*sum(counts[j] for j in neighbors) for i,neighbors in enumerate(f.leaf_neighbors));rows.append(dict(n=n,k0=k0,region=region,k=[k.real,k.imag],levels=f.levels,all_near=f.low_frequency_direct,near_panel_pairs=int(pairs),fraction=float(pairs/n**2),translation_groups=sum(len(z) for z in f.m2l[2:])))
(D/'REGION_PLANS.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
