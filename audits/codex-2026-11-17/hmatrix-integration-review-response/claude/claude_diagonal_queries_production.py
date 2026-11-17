"""Reviewer check: actual allocation of aligned diagonal queries on real operators (v2 gather)."""
import os,sys,json,tracemalloc,time
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope)
from ghost_backend.compressed.hmatrix import BlockRow
v2=BlockRow.values  # actual production method of the tree under test
counter=dict(lowrank=0,dense=0,maxrank=0,lowrank_chunk=0,dense_chunk=0)
def counted(self,rows=None,columns=None):
    if isinstance(rows,np.ndarray) and isinstance(columns,np.ndarray):
        size=rows.size*columns.size*16
        if self.v is None:counter['dense']+=1;counter['dense_chunk']=max(counter['dense_chunk'],size)
        else:counter['lowrank']+=1;counter['maxrank']=max(counter['maxrank'],self.u.shape[1]);counter['lowrank_chunk']=max(counter['lowrank_chunk'],size)
    return v2(self,rows,columns)
BlockRow.values=counted
out={}
state=CPUState(kernel_only=True)
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    for name,n,kind,k,eps in (('star-8192',4096,'star',80.,3-.08j),('slot-1024',512,'slot',10.,3-.08j),('square-1024',512,'square',10.,3-.08j)):
        mesh=mesh_for(n,kind);info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
        coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
        h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30)
        rows=[];stack=[np.asarray(h.order)]
        while stack:
            ids=stack.pop();m=len(ids)
            if m<=1024:
                for key in counter:counter[key]=0
                q=m*m*16;tracemalloc.start();b0=tracemalloc.get_traced_memory()[0];tracemalloc.reset_peak()
                res=h._get(ids,ids);peak=tracemalloc.get_traced_memory()[1]-b0;tracemalloc.stop()
                rows.append(dict(side=m,leaf=bool(m<=h.leaf),peak_over_q=peak/q,peak_MiB=peak/2**20,four_q_plus_1_MiB=(4*q+2**20)/2**20,exceeds=bool(peak>4*q+2**20),exceeds_2q=bool(peak>2*q),**counter));del res
            if m>h.leaf:stack.extend((ids[:m//2],ids[m//2:]))
        leaves=[r for r in rows if r['leaf']];big=[r for r in rows if not r['leaf']]
        out[name]=dict(unknowns=2*n,operator_leaf=int(h.leaf),queries=len(rows),leaf_queries=len(leaves),leaf_lowrank_contributions=sum(r['lowrank'] for r in leaves),
            leaf_max_peak_over_q=max(r['peak_over_q'] for r in leaves),fallback_queries=len(big),fallback_max_peak_over_q=max((r['peak_over_q'] for r in big),default=None),
            fallback_lowrank_contributions=sum(r['lowrank'] for r in big),fallback_max_rank_over_side=max((r['maxrank']/r['side'] for r in big),default=None),
            fallback_max_lowrank_chunk_over_q=max((r['lowrank_chunk']/(r['side']**2*16) for r in big),default=None),
            any_exceeds_4q_plus_1=any(r['exceeds'] for r in rows),count_exceeding_2q=sum(r['exceeds_2q'] for r in rows),
            by_side={str(s):dict(count=sum(1 for r in rows if r['side']==s),max_peak_over_q=max(r['peak_over_q'] for r in rows if r['side']==s)) for s in sorted({r['side'] for r in rows})},rows=rows)
        print(name,json.dumps({k:v for k,v in out[name].items() if k!='rows'}),flush=True)
json.dump(out,open(sys.argv[1],'w'),indent=1)
