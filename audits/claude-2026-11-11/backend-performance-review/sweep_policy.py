"""Spawned frequency workers under Automatic: does the policy (and the 1,024 H-matrix threshold) reach the workers?"""
import json, math, sys, time
from pathlib import Path
import numpy as np
root = Path(sys.argv[1]); sys.path.insert(0, str(root/'tools/GHOST'))
from ghost_backend.execution.fresh_sweep import run_fresh
from ghost_backend.execution.options import automatic_options, execution_scope
from ghost_backend.twod import solver as S
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
def main():
    n = int(sys.argv[2]); ram = float(sys.argv[3]); workers = int(sys.argv[4])
    t = -np.linspace(0, 2*np.pi, n+1); p = [(np.cos(a), np.sin(a)) for a in t]; p[-1] = p[0]
    rows = '\n'.join('%.15g %.15g %.15g %.15g' % (*p[i], *p[i+1]) for i in range(n))
    g = build_geometry_snapshot(*parse_geometry('Title: sweep\nSegment: b 2\nproperties: 2 1 0 0 0\n'+rows+'\nIBCS_Resistances:\nDielectrics:\n'))
    f0 = 0.314/(2*math.pi/n)*299792458/(2*math.pi)/1e9
    args = dict(geometry_snapshot=g, frequencies_ghz=[0.9*f0, 0.95*f0, f0], elevations_deg=[float(x) for x in np.linspace(0, 180, 61)], geometry_units='meters', max_panels=100000)
    opts = dict(automatic_options(ram), mesh_strategy='global')
    out = {}
    for w in (workers,):
        t0 = time.perf_counter()
        with execution_scope(opts, assembly_threads=4, memory_budget_gib=8.):
            r = run_fresh(S.solve_monostatic_rcs_2d_survey, args, opts, 'double', False, frequency_workers=w)
        m = r['metadata']
        ev = m.get('linear_algebra_execution') or []
        per = m.get('per_frequency') or m.get('frequency_metadata') or []
        print('workers', w, 'wall %.1f' % (time.perf_counter()-t0), 'mode', m['frequency_execution'].get('mode'),
              'backend', m.get('linear_backend'), 'keys', [k for k in m if 'backend' in k or 'select' in k or 'frequenc' in k])
        sel=m.get('backend_selection') or {}
        print('   selected', sel.get('selected'), 'reason', sel.get('reason'), 'cands', {k:round(v['peak_gb'],2) for k,v in sel.get('candidates',{}).items()})
        print('   exec', json.dumps(m['frequency_execution'])[:300])
        fm=m.get('frequency_metadata')
        print('   freq meta', json.dumps(fm, default=str)[:900] if not isinstance(fm,(list,dict)) else [ (x.get('linear_backend'), (x.get('backend_selection') or {}).get('selected')) for x in (fm.values() if isinstance(fm,dict) else fm)])
        out[w] = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']])
    if len(out) == 2:
        a, b = out.values(); print('field diff', abs(a-b).max()/abs(a).max())
if __name__ == '__main__': main()
