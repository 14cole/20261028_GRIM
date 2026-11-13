"""Exact near-pair counts for specified uniform-tree geometries; no solves/timings."""
import pathlib,json,math,numpy as np
D=pathlib.Path(__file__).parent;results=[];q=(np.polynomial.legendre.leggauss(8)[0]+1)/2
for kind in ['circle','star','two_close_stars']:
 for n in [1000,2000,4000,8000,16000]:
  t=np.linspace(0,2*np.pi,n,endpoint=False);r=2.54*(1+.2*np.cos(5*t)) if kind!='circle' else np.full(n,2.54);v=np.column_stack((r*np.cos(t),r*np.sin(t)));p0=v;p1=np.roll(v,-1,axis=0)
  if kind=='two_close_stars':p0=np.concatenate([p0,p0*.99]);p1=np.concatenate([p1,p1*.99])
  x=(p0[:,None]+q[None,:,None]*(p1-p0)[:,None]).reshape(-1,2);centers=(p0+p1)/2;lo=x.min(axis=0);span=float((x.max(axis=0)-lo).max())*(1+1e-9)+1e-300;k=2*np.pi*2e9/299792458.;levels=max(2,int(math.floor(math.log2(span/(1.5*2*np.pi/k)))));side=span/2**levels;ij=np.clip(np.floor((centers-lo)/side).astype(int),0,2**levels-1);unique,counts=np.unique(ij,axis=0,return_counts=True);table={tuple(v):int(c) for v,c in zip(unique,counts)};pairs=0
  for (i,j),count in table.items():pairs+=count*sum(table.get((i+di,j+dj),0) for di in range(-2,3) for dj in range(-2,3))
  results.append(dict(kind=kind,panels_per_interface=n,panels=len(p0),frequency_ghz=2.,levels=levels,leaf_side_m=side,near_panel_pairs=pairs,pair_fraction=pairs/len(p0)**2,coefficient_buffer_guard_bytes=pairs*4*(8*2+16*3),research_2gib_buffer_guard_passes=pairs*4*(8*2+16*3)<=2*2**30,full_solve=False))
(D/'GEOMETRY_NEAR_SCALING.json').write_text(json.dumps(results,indent=2));print([(r['kind'],r['panels'],r['near_panel_pairs'],round(r['coefficient_buffer_guard_bytes']/2**30,2)) for r in results])
