"""Reviewer diagnostic 2: instrument the retained HODLR inverse tree.
For each tree depth: 1-norm condition numbers of the leaf LUs and Woodbury
small systems, and the size of the intermediate (pre-correction) vectors
relative to the final output of the whole apply."""
import numpy as np,scipy.linalg as la
import precond_diag as pd
def lu_cond(lu):
    f,piv=lu;n=len(f);L=np.tril(f,-1)+np.eye(n);U=np.triu(f);a=L@U
    for i in range(n-1,-1,-1):a[[i,piv[i]]]=a[[piv[i],i]]
    inv=la.lu_solve(lu,np.eye(n,dtype=complex),check_finite=False)
    return float(np.linalg.norm(a,1)*np.linalg.norm(inv,1)),float(np.linalg.norm(inv,2)),float(np.linalg.norm(a,2))
def walk(node,b,depth,rec):
    e=rec.setdefault(depth,dict(pre_sq=0.,post_sq=0.,in_sq=0.,corr_sq=0.,small_sq=0.,nodes=0,leaves=0))
    e['in_sq']+=la.norm(b)**2
    if node.leaf:
        r=la.lu_solve(node.lu,b,check_finite=False);e['leaves']+=1;e['pre_sq']+=la.norm(r)**2;e['post_sq']+=la.norm(r)**2;return r
    n=node.left.n;z1=walk(node.left,b[:n],depth+1,rec);z2=walk(node.right,b[n:],depth+1,rec);e['nodes']+=1
    e['pre_sq']+=la.norm(z1)**2+la.norm(z2)**2
    if node.lu is None:
        e['post_sq']+=la.norm(z1)**2+la.norm(z2)**2;return np.vstack((z1,z2))
    small=np.vstack((node.v12@z2,node.v21@z1));c=la.lu_solve(node.lu,small,check_finite=False);r=node.e1.shape[1]
    d1=node.e1@c[:r];d2=node.e2@c[r:];e['corr_sq']+=la.norm(d1)**2+la.norm(d2)**2;e['small_sq']+=la.norm(c)**2
    out=np.vstack((z1-d1,z2-d2));e['post_sq']+=la.norm(out)**2;return out
def conds(node,depth,rec):
    e=rec.setdefault(depth,dict(leaf_cond1=[],leaf_inv2=[],leaf_norm2=[],small_cond1=[],small_inv2=[],e_norm=[],v_norm=[],rank=[]))
    if node.leaf:
        c,i,a=lu_cond(node.lu);e['leaf_cond1'].append(c);e['leaf_inv2'].append(i);e['leaf_norm2'].append(a);return
    if node.lu is not None:
        c,i,a=lu_cond(node.lu);e['small_cond1'].append(c);e['small_inv2'].append(i);e['rank'].append(len(node.lu[0]))
        e['e_norm'].append(max(np.linalg.norm(node.e1,2),np.linalg.norm(node.e2,2)));e['v_norm'].append(max(np.linalg.norm(node.v12,2),np.linalg.norm(node.v21,2)))
    conds(node.left,depth+1,rec);conds(node.right,depth+1,rec)
base=pd.diag
def diag(L):
    if pd.OUT:return
    base(L)
    pre,V,Z,hi,y=L['precondition'],L['V'],L['Z'],L['hi'],L['coefficients']
    cells=[c.cell_contents for c in pre.__closure__];inv=[c for c in cells if hasattr(c,'apply')][0]
    vecs=[c for c in cells if isinstance(c,np.ndarray) and c.ndim==1]
    r=np.random.default_rng(5);n=V.shape[0];u=r.standard_normal((n,8))+1j*r.standard_normal((n,8));w=V[:,:hi]@y
    # identify rows scaling: pre(v)=cols*inv.apply(rows*v); find by test
    ref=pre(u);rows=cols=None
    for a in vecs:
        for c in vecs:
            if np.array_equal(c[:,None]*inv.apply(a[:,None]*u,solve=True),ref):rows,cols=a,c
    assert rows is not None
    out={}
    for name,x in (('random',u),('VY',w)):
        rec={};res=walk(inv.root,(rows[:,None]*x)[inv.permutation],0,rec);full=np.empty_like(res);full[inv.permutation]=res
        assert np.allclose(cols[:,None]*full,pre(x),rtol=1e-9,atol=0)
        tot=la.norm(res)
        out[name]={str(d):dict(nodes=e['nodes'],leaves=e['leaves'],input=float(e['in_sq']**.5/tot),pre_correction=float(e['pre_sq']**.5/tot),correction=float(e['corr_sq']**.5/tot),small_solution=float(e['small_sq']**.5/tot),post=float(e['post_sq']**.5/tot)) for d,e in sorted(rec.items())}
        out[name+'_scaled_input_norm_over_output']=float(la.norm(rows[:,None]*x)/tot)
    rec={};conds(inv.root,0,rec)
    def s(v):return [float(np.min(v)),float(np.median(v)),float(np.max(v))] if len(v) else None
    out['conditioning_min_median_max']={str(d):{k:s(v) for k,v in e.items()} for d,e in sorted(rec.items())}
    out['row_scale_range']=[float(rows.min()),float(rows.max())];out['col_scale_range']=[float(cols.min()),float(cols.max())]
    pd.OUT['tree']=out
pd.ns['diag']=diag
solve=pd.solve
