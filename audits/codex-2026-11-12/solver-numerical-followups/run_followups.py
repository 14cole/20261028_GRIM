import json,os,pathlib,subprocess,time
SCRIPTS=pathlib.Path(__file__).parent
D=pathlib.Path(os.environ.get('GRIM_EVIDENCE_DIR',SCRIPTS)); D.mkdir(parents=True,exist_ok=True)
NEW=os.environ.get('GRIM_ROOT','/workspace/grim-solver-followups'); OLD=os.environ.get('GRIM_BASELINE_ROOT','/workspace/grim-workflow-improvements')
def run(name,spec,root=NEW):
    p=D/(name+'.json')
    if p.exists() and p.stat().st_size:return
    spec=dict(spec,sample=spec.get('sample',False),out=str(D/(name+'.npy')))
    start=time.time()
    with p.open('w') as f:
        try:r=subprocess.run(['python',str(SCRIPTS/'sample_solve.py'),root,json.dumps(spec)],stdout=f,stderr=subprocess.PIPE,text=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),timeout=360)
        except subprocess.TimeoutExpired:
            print(name,'TIMEOUT',flush=True);return
    if r.stderr:(D/(name+'.stderr')).write_text(r.stderr)
    try:data=json.load(p.open());error=data['error']
    except Exception:error='invalid output'
    print(name,round(time.time()-start,1),error,flush=True)

if __name__=='__main__':
    for body in ['diel','coated']:
        for degree in [2,3]:
            for mode in ['dense','compressed']:
                run(f'p{degree}-{body}-{mode}',dict(body=body,n=600,radius=.02,mode=mode,angles=7,options={'basis_order':degree}))
    for mode in ['dense','compressed']:
        run('fallback-'+mode,dict(body='diel',n=600,radius=.01,mode=mode,angles=7,fallback=True))
    run('random-rhs',dict(body='diel',n=600,radius=.01,mode='compressed',angles=3,random_rhs_checks=True))
    for mode in ['dense','compressed']:
        run('certified-'+mode,dict(body='diel',n=600,radius=.1,mode=mode,angles=3,certified=True))
    for cap in [.85,1.]:
        run(f'auto-cap-{cap}',dict(body='diel',n=2000,radius=.01,mode='automatic',angles=19,threads=1,options={'ram_budget_gib':cap,'compressed_storage_mib':0}))
    run('sweep-profile',dict(body='coated',n=2000,radius=.2,mode='compressed',angles=19,frequency_factors=[.98,1.,1.02],fixed_mesh=True,profile_geometry=True,sample=True))
    for factor in [.98,1.,1.02]:
        run(f'sweep-dense-{factor}',dict(body='coated',n=2000,radius=.2,mode='dense',angles=19,frequency_factors=[factor],fixed_mesh=True))
    # Interleaved fresh processes; no concurrent solver workloads.
    for repeat in range(2):
        for root,label in [(OLD,'before'),(NEW,'after')]:
            for case,spec in [('pec',dict(body='pec',n=8000,angles=181,threads=4)),('airfoil',dict(body='airfoil',f=6,angles=19)),('diel',dict(body='diel',n=4000,radius=.05,angles=181))]:
                run(f'bench-{case}-{label}-{repeat}',dict(spec,mode='compressed'),root)
    for variant in ['control','coarse_blas','parallel_solve']:
        for repeat in range(2):
            run(f'experiment-{variant}-{repeat}',dict(body='pec',n=8000,mode='compressed',angles=181,**({variant:True} if variant!='control' else {})))
    run('airfoil-profile',dict(body='airfoil',f=6,mode='compressed',angles=19,sample=True,profile_geometry=True))
