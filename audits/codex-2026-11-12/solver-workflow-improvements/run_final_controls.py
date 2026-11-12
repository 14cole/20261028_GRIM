from run_followups import run, D, NEW, OLD, SCRIPTS
import numpy as np
from pathlib import Path

def geometry(name,kind,points,law,material=''):
    text=f'Title: {name}\nSegment: b {kind}\nproperties: {kind} 1 10 0 0\n'
    text+='\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(points[:-1],points[1:]))
    text+='\nIBCS_Resistances:\n10 '+law+'\nDielectrics:\n'+material
    p=D/(name+'.geo');p.write_text(text);return str(p)

if __name__=='__main__':
    run('coated-dense-refined',dict(body='coated',n=2000,radius=.01,mode='dense',angles=19,dense_extra_refinement=True))
    for cap in [.85,1.]:
        run(f'auto-final-{cap}',dict(body='diel',n=2000,radius=.01,mode='automatic',angles=19,threads=1,options={'ram_budget_gib':cap,'compressed_storage_mib':0}))
    run('auto-before-0.85',dict(body='diel',n=2000,radius=.01,mode='automatic',angles=19,threads=1,options={'ram_budget_gib':.85,'compressed_storage_mib':0}),OLD)
    for mode in ['dense','compressed']:
        run('native-'+mode,dict(body='diel',n=600,radius=.01,mode=mode,angles=7))
    for radius in [.01,100.]:
        run(f'tile-{radius}',dict(body='diel',n=600,radius=radius,mode='compressed',angles=7,threads=1,force_tile=True))
    n=1200;t=-np.linspace(0,2*np.pi,n+1);circle=.05*np.column_stack((np.cos(t),np.sin(t)));circle[-1]=circle[0]
    line=np.column_stack((np.linspace(-.3,.3,n+1),np.zeros(n+1)))
    cases=[('ibc',geometry('ibc',2,circle,'constant 75 -20 0 0'),8.),
           ('sheet',geometry('sheet',1,line,'constant 75 -20 0 0'),2.),
           ('thin',geometry('thin',1,line,'thin_dielectric 0.0001 1','1 2.0 -0.02 1.0 0.0\n'),2.)]
    for name,geo,f in cases:
        for mode in ['dense','compressed']:
            run(f'{name}-{mode}',dict(body='custom',geo=geo,f=f,mode=mode,angles=7,threads=1))
    run('sweep-final',dict(body='coated',n=2000,radius=.2,mode='compressed',angles=19,frequency_factors=[.98,1.,1.02],fixed_mesh=True,profile_geometry=True,sample=True))
    for root,label in [(OLD,'before'),(NEW,'after')]:
        run(f'bench-airfoil-{label}-replacement',dict(body='airfoil',f=6,angles=19,mode='compressed'),root)

    run('pec8k-dense',dict(body='pec',n=8000,mode='dense',angles=181,threads=4))
    for mode in ['dense','compressed']:
        run('airfoil3-'+mode,dict(body='airfoil',f=3,mode=mode,angles=19))

    run('coated-refine-p2',dict(body='coated',n=2000,radius=1.,mode='dense',angles=19,options={'basis_order':2}))

    import subprocess,os
    subprocess.run(['python',str(SCRIPTS/'test_parallel_requests.py'),NEW,str(D/'parallel-requests.json')],check=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
