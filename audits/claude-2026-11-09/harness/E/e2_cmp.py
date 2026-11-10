import json,glob,sys,os
import numpy as np
N=sys.argv[1] if len(sys.argv)>1 else '1200'; F=sys.argv[2] if len(sys.argv)>2 else '10.0'
for c in ['pec','ibc','diel','diel_res','coat','coat_thin','two_pec','two_ibc']:
    R={}
    for b in ['lu','hodlr','tile','hmat']:
        f=f'res/{c}_{b}_{N}_{F}.json'
        if os.path.exists(f) and os.path.getsize(f)>0: R[b]=json.load(open(f))
        elif os.path.exists(f): R[b]=dict(error='NO OUTPUT (timeout/crash)')
    if not R: continue
    print('==',c)
    ref=R.get('lu')
    for b,d in R.items():
        if 'error' in d: print('  %-6s ERROR %s'%(b,d['error'][:250])); continue
        s='  %-6s t=%6.1fs rss=%5.0fMB'%(b,d['t'],d['maxrss_mb'])
        for p in ('VV','HH'):
            a=np.array([complex(*z) for z in d['amp'][p]])
            if ref and 'amp' in ref:
                r=np.array([complex(*z) for z in ref['amp'][p]])
                s+=' | %s dofs=%s maxreldiff=%.1e (rel to max|amp| %.1e) cond=%.3g res=%.1e used=%s'%(p,d[p]['dofs'],np.max(np.abs(a-r)/np.abs(r)),np.max(np.abs(a-r))/np.max(np.abs(r)),d[p]['cond'] or float('nan'),d[p]['res'],d[p]['backend'])
            if d[p]['fallback']: s+=' FALLBACK %s'%str(d[p]['fallback'])[:200]
        print(s)
