from dlib import *
P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
def body(pts, N=0, split=False, props=None):
    props = props or f'2 {N} 0 0 0'
    if split:
        segs=[(f's{i}',2,props,rows(pts[i:i+2])) for i in range(len(pts)-1)]
    else:
        segs=[('b',2,props,rows(pts))]
    return geo(segs)
asp=[0,10,30,60,90,120,150,170,180]
f=3.0
def get(r):
    return np.concatenate([chan(r,'VV')[0],chan(r,'HH')[0]]), np.concatenate([chan(r,'VV')[1],chan(r,'HH')[1]])
def cmp(tag, s1,a1,s2,a2, phase=None):
    d=np.max(np.abs(db(s1)-db(s2)))
    if phase is not None: a2=a2*phase
    ca=np.max(np.abs(a1-a2))/np.max(np.abs(a1))
    print(f'{tag:40s} max|ddB|={d:.2e}  rel complex amp diff={ca:.2e}',flush=True)
t=time.time(); r0=run(body(P),f,asp); print('base t',time.time()-t, r0['metadata']['per_frequency'][0]['n_unknowns'], r0['metadata']['per_frequency'][0]['modes_used'])
s0,a0=get(r0)
print('VV dB',np.round(db(chan(r0,'VV')[0]),3)); print('HH dB',np.round(db(chan(r0,'HH')[0]),3))
print('VV==HH at 0,180:', abs(db(chan(r0,'VV')[0][0])-db(chan(r0,'HH')[0][0])), abs(db(chan(r0,'VV')[0][-1])-db(chan(r0,'HH')[0][-1])), 'amp', chan(r0,'VV')[1][0], chan(r0,'HH')[1][0])
# flip z
Pf=[(p[0],-p[1]) for p in P][::-1]
r=run(body(Pf),f,[180-x for x in asp]); s,a=get(r); cmp('flip z & 180-theta',s0,a0,s,a)
# translate
d=0.137; Pt=[(p[0],p[1]+d) for p in P]
r=run(body(Pt),f,asp); s,a=get(r)
k=2*np.pi*f*1e9/C0; th=np.radians(asp*2)
for sgn in (+1,-1):
    cmp(f'translate dz phase exp({sgn:+d}2jkd cos)',s0,a0,s,a, np.exp(-sgn*2j*k*d*np.cos(th)))
# split
r=run(body(P,split=True),f,asp); s,a=get(r); cmp('split segments',s0,a0,s,a)
# inches
Pi=[(p[0]/0.0254,p[1]/0.0254) for p in P]
r=run(body(Pi),f,asp,geometry_units='inches'); s,a=get(r); cmp('inches',s0,a0,s,a)
# multi-frequency
r=run(body(P),[4.0,3.0,2.0],asp)
vv=r['co_solved_samples']['VV']; print('multi-f sample order freq:', [x['frequency_ghz'] for x in vv][::len(asp)])
sel=lambda pol:[x for x in r['co_solved_samples'][pol] if x['frequency_ghz']==3.0]
s=np.array([x['rcs_linear'] for x in sel('VV')+sel('HH')]); a=np.array([x['rcs_amp_real']+1j*x['rcs_amp_imag'] for x in sel('VV')+sel('HH')])
cmp('multi-freq [4,3,2] vs single 3',s0,a0,s,a)
# aspect order / subset
r=run(body(P),f,asp[::-1]); s,a=get(r); n=len(asp); s=np.concatenate([s[:n][::-1],s[n:][::-1]]); a=np.concatenate([a[:n][::-1],a[n:][::-1]]); cmp('aspect order reversed',s0,a0,s,a)
r=run(body(P),f,[60]); s,a=get(r); print('single aspect 60: ddB', db(s)-db(s0[[3,3+n]]), 'modes', r['metadata']['per_frequency'][0]['modes_used'])
r=run(body(P),f,[0]); s,a=get(r); print('single aspect 0: ddB', db(s)-db(s0[[0,n]]), 'modes', r['metadata']['per_frequency'][0]['modes_used'])
r=run(body(P),f,[0,180]); s,a=get(r); print('aspects 0,180: ddB', db(s)-db(s0[[0,n-1,n,2*n-1]]), 'modes', r['metadata']['per_frequency'][0]['modes_used'])
r=run(body(P),f,[0.001,179.999]); s,a=get(r); print('aspects .001,179.999: ddB', db(s)-db(s0[[0,n-1,n,2*n-1]]), 'modes', r['metadata']['per_frequency'][0]['modes_used'])
# n_modes explicit
for nm in (30, 20, 12, 8, 5):
    try:
        r=run(body(P),f,asp,n_modes=nm); s,a=get(r); cmp(f'n_modes={nm} used {r["metadata"]["per_frequency"][0]["modes_used"]}',s0,a0,s,a)
    except Exception as e: print('n_modes',nm,type(e).__name__,str(e)[:150])
for tol in (1e-3,1e-9,1e-12):
    try:
        r=run(body(P),f,asp,mode_tol=tol); s,a=get(r); cmp(f'mode_tol={tol} used {r["metadata"]["per_frequency"][0]["modes_used"]}',s0,a0,s,a)
    except Exception as e: print('mode_tol',tol,type(e).__name__,str(e)[:150])
# expand
r=run(body(P),f,asp,expand_to_360=True)
ss=r['co_solved_samples']['VV']; print('expand: n',len(ss),[ (x['theta_inc_deg'],round(x['rcs_db'],3)) for x in ss])
print('samples len', len(r['samples']), r['metadata']['output_aspect_count'])
# workers
r=run(body(P),f,asp,workers=1); s,a=get(r); cmp('workers=1 vs 2',s0,a0,s,a)
# cfie alpha
for al in (0.2,0.8):
    r=run(body(P),f,asp,cfie_alpha=al); s,a=get(r); cmp(f'cfie_alpha={al}',s0,a0,s,a)
# refinement
for N in (-40,-80):
    r=run(body(P,N=N),f,asp); s,a=get(r); cmp(f'N={N} n={r["metadata"]["per_frequency"][0]["n_unknowns"]}',s0,a0,s,a)
