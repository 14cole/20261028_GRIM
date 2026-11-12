"""A fixed mesh with electrically long panels: survey still runs with the warning, certification is refused."""
import sys, os
root = sys.argv[1]; sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.twod import solver as S
sq = [(0,0),(0,1),(1,1),(1,0),(0,0)]
rows = '\n'.join('%g %g %g %g' % (*sq[i], *sq[i+1]) for i in range(4))
g = build_geometry_snapshot(*parse_geometry('Title: sq\nSegment: b 2\nproperties: 2 -1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % rows))
opts = dict(factorization='dense', mesh_strategy='global', enforce_mesh_density=False)
for name in ('solve_monostatic_rcs_2d_survey', 'solve_monostatic_rcs_2d_certified'):
    try:
        r = getattr(S, name)(g, [1.5], [0., 30., 45.], geometry_units='meters', execution_options=opts)
        m = r['metadata']; q = m.get('quadrature_qualification') or []
        print(name, 'completed; certified =', m.get('mesh_convergence_certified'), '; qualified =', [x['qualified'] for x in q], '; max kL =', [round(x['maximum_panel_kl'], 2) for x in q],
              '; long-panel warning =', any('Electrically long' in w for w in (m.get('warnings') or [])))
    except Exception as exc:
        print(name, 'raised', type(exc).__name__ + ':', str(exc)[:260])
