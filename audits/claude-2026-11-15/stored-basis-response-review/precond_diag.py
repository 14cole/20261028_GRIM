"""Reviewer diagnostic: where does M(VY) differ from ZY, and is it more than
ordinary double-precision conditioning? Runs the stored-Z solver and, at the
first true check of the first block, measures the quantities below."""
import time,json,os,numpy as np
from scipy.linalg import norm
import block_gmres_right_z as z
OUT={}
def census(root):
    seen=set();arrays={};stack=[root]
    while stack:
        o=stack.pop()
        if id(o) in seen:continue
        seen.add(id(o))
        if isinstance(o,np.ndarray):
            e=arrays.setdefault(str(o.dtype),[0,0]);e[0]+=1;e[1]+=o.nbytes;continue
        if isinstance(o,(list,tuple,set)):stack.extend(o)
        elif isinstance(o,dict):stack.extend(o.values())
        elif hasattr(o,'__dict__'):stack.extend(vars(o).values())
        elif hasattr(o,'__slots__'):stack.extend(getattr(o,s) for s in o.__slots__ if hasattr(o,s))
    return arrays
def fro(x):return float(norm(x))
def diag(L):
    if OUT:return
    a,pre,V,Z,hi,y,b,x=L['apply'],L['precondition'],L['V'],L['Z'],L['hi'],L['coefficients'],L['b'],L['x']
    eps=np.finfo(float).eps;r=np.random.default_rng(77);n,m=b.shape;bn=fro(b)
    inv=[c.cell_contents for c in pre.__closure__ if hasattr(c.cell_contents,'apply')][0]
    OUT['inverse_array_census']=census(inv)
    w=V[:,:hi]@y;zy=Z[:,:hi]@y;mw=pre(w);d=mw-zy
    OUT['repeat_call_bitwise_identical']=bool(np.array_equal(pre(w),mw))
    OUT['replay_blocks_bitwise_identical_to_Z']=bool(all(np.array_equal(pre(V[:,j:j+m]),Z[:,j:j+m]) for j in (0,m,hi-m)))
    OUT['norm_b']=bn;OUT['norm_w_VY']=fro(w);OUT['norm_ZY']=fro(zy);OUT['norm_Y']=fro(y);OUT['basis_columns']=int(hi)
    OUT['largest_term_over_sum']=float(max(norm(Z[:,j])*norm(y[j]) for j in range(hi))/fro(zy))
    OUT['defect_rel_ZY']=fro(d)/fro(zy);OUT['equation_effect_rel_b']=fro(a(d))/bn
    OUT['true_rel_MVY']=fro(b-a(x+mw))/bn;OUT['true_rel_ZY']=fro(b-a(x+zy))/bn
    # 2-norm of M by power iteration on M^H M using difference quotients is not
    # available without the adjoint; use the largest gain seen over probes plus
    # an explicit power iteration on M via Gram of small subspace (lower bound).
    q=np.linalg.qr(r.standard_normal((n,m))+1j*r.standard_normal((n,m)))[0];gain=[]
    for it in range(12):
        mq=pre(q);s=np.linalg.svd(mq,compute_uv=False);gain.append(float(s[0]));q=np.linalg.qr(mq)[0]
    OUT['M_gain_power_iteration_lower_bound']=gain[-1];OUT['M_gain_history']=gain
    u=r.standard_normal((n,m))+1j*r.standard_normal((n,m));v=r.standard_normal((n,m))+1j*r.standard_normal((n,m))
    mu,mv,muv=pre(u),pre(v),pre(u+v)
    OUT['random_additivity_defect_rel_result']=fro(muv-mu-mv)/fro(muv)
    OUT['random_additivity_defect_over_eps_normM_normInput']=fro(muv-mu-mv)/(eps*gain[-1]*fro(u+v))
    OUT['random_M_gain_rms']=fro(muv)/fro(u+v)
    OUT['defect_over_eps_normM_normVY']=fro(d)/(eps*gain[-1]*fro(w))
    # input rounding sensitivity: perturb w by relative eps noise per entry
    for scale in (1,4):
        pert=w*(1+scale*eps*(r.random(w.shape)-.5)*2)
        dp=pre(pert)-mw
        OUT[f'input_roundoff_x{scale}_defect_rel_ZY']=fro(dp)/fro(zy);OUT[f'input_roundoff_x{scale}_equation_effect_rel_b']=fro(a(dp))/bn
    # the same for a random vector of the same norm as w
    rw=u*(fro(w)/fro(u));mrw=pre(rw);dp=pre(rw*(1+eps*(r.random(w.shape)-.5)*2))-mrw
    OUT['random_input_roundoff_defect_rel_result']=fro(dp)/fro(mrw);OUT['random_input_gain']=fro(mrw)/fro(rw);OUT['VY_gain']=fro(mw)/fro(w)
    OUT['A_gain_on_defect']=fro(a(d))/fro(d);OUT['A_gain_on_random']=fro(a(u))/fro(u);OUT['A_gain_on_ZY']=fro(a(zy))/fro(zy)
    t=time.perf_counter();pre(u);tp=time.perf_counter()-t;t=time.perf_counter();a(u);ta=time.perf_counter()-t
    OUT['seconds_pre_8cols']=tp;OUT['seconds_A_8cols']=ta
src=open(z.__file__).read().replace("candidate=x+Z[:,:hi]@coefficients;","diag(locals());candidate=x+Z[:,:hi]@coefficients;")
assert 'diag(locals())' in src
ns={'diag':diag,'__name__':'zdiag'};exec(compile(src,'zdiag','exec'),ns)
def solve(apply,precondition,b,**kw):
    x,d=ns['solve'](apply,precondition,b,**kw)
    if OUT and not OUT.get('written'):
        OUT['written']=True;d=dict(d,precond_diag=OUT)
    return x,d
