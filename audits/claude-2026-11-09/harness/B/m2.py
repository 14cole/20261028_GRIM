from ref import *
from ghost_backend.twod import solver as S
import json
a=0.1
g = geo([(2, '2 1 0 0 0', rows(a, 60))])
r = S.solve_monostatic_rcs_2d(g, [1.0], [0.0], geometry_units='meters')
m = r['metadata']
def show(d, ind=0):
    for k, v in d.items():
        if isinstance(v, dict) and k not in ('preflight',):
            print(' '*ind + k + ':'); show(v, ind+2)
        else:
            s = repr(v); print(' '*ind + f'{k}: {s[:300]}')
show({k: v for k, v in m.items() if k != 'channel_metadata'})
print('---- TE channel'); show(m['channel_metadata']['VV'])
for pol in ('TE','TM'):
    b = get(r, pol)[0]; br = amp(1e9, pol, [a], [], ('pec',))[0]
    print(pol, abs(b-br)/abs(br))
