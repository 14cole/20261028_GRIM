from lib import *
from ghost_backend.twod import solver as S
def rect(x0,y0,x1,y1):  # clockwise
    p=[(x0,y0),(x0,y1),(x1,y1),(x1,y0),(x0,y0)]
    return '\n'.join(f'{p[i][0]} {p[i][1]} {p[i+1][0]} {p[i+1][1]}' for i in range(4))
diel = f"Segment: d 3\nproperties: 3 {{n}} 0 1 0\n{rect(-0.05,-0.03,0.05,0.03)}\n"
def scene(strip, n):
    return snap("Title: t\n"+diel.format(n=n)+strip.format(n=n)+"IBCS_Resistances:\n\nDielectrics:\n1 3.0 -0.1 1.0 0.0\n")
openstrip = "Segment: s 2\nproperties: 2 {n} 0 0 0\n-0.05 0.08 0.05 0.08\n"
t=0.0002
plate = "Segment: s 2\nproperties: 2 {n} 0 0 0\n"+rect(-0.05,0.08-t/2,0.05,0.08+t/2)+"\n"
ang=[0.,45.,90.,135.,270.]
for name,strip in (('open',openstrip),('plate',plate)):
    for n in (-20,-60):
        try:
            r=S.solve_monostatic_rcs_2d(scene(strip,n),[1.5],ang,geometry_units='meters',solver_method='direct')
            for pol in ('VV','HH'):
                print(name,n,pol,[round(s['rcs_db'],3) for s in r['samples'] if s['polarization']==pol], r['metadata'].get('quality_gate',{}).get('passed') if isinstance(r['metadata'].get('quality_gate'),dict) else '')
        except Exception as e: print(name,n,'ERR',str(e)[:300])
# strip alone -> should be refused
try:
    S.solve_monostatic_rcs_2d(snap("Title: t\n"+openstrip.format(n=-20)+"IBCS_Resistances:\n\nDielectrics:\n"),[1.5],ang,geometry_units='meters',solver_method='direct'); print('alone accepted')
except Exception as e: print('alone refused:',str(e)[:120])
