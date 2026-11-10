import sys, time, os, copy, json, threading, glob, tempfile
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
which = sys.argv[1].split(',')
def amps(r, pol): return get(r, pol)
def rel(a, b): return float(np.max(np.abs(a-b))/np.max(np.abs(b)))
def tmpfiles():
    return set(glob.glob(os.path.join(tempfile.gettempdir(), '*ghost*')) + glob.glob(os.path.join(tempfile.gettempdir(), '*GHOST*')) + glob.glob(os.path.join(tempfile.gettempdir(), 'tmp*')))

if 'dup' in which:
    g = make('pec')
    for ang in ([10.0, 10.0], [0.0, 360.0], [-180.0, 180.0]):
        for method in ('direct', 'auto'):
            t = time.time()
            try:
                r = S.solve_monostatic_rcs_2d(g, [1.5], ang, geometry_units='meters', solver_method=method)
                print('dup', ang, method, 'OK n=', len(r['samples']), [round(s['rcs_db'], 6) for s in r['samples']])
            except Exception as e:
                print('dup', ang, method, 'ERR after %.2fs' % (time.time()-t), type(e).__name__, str(e)[:160])
    try:
        r = S.solve_bistatic_rcs_2d(g, [1.5], [0.0, 0.0], [10.0, 20.0], geometry_units='meters'); print('bi dup inc OK')
    except Exception as e: print('bi dup inc ERR', type(e).__name__, str(e)[:160])
    try:
        r = S.solve_monostatic_rcs_2d(g, [1.5, 1.5], [0.0], geometry_units='meters'); print('dup freq OK')
    except Exception as e: print('dup freq ERR', type(e).__name__, str(e)[:160])

if 'mut' in which:
    for name in ('coatibc', 'sheetpec', 'thin'):
        g = make(name); g0 = copy.deepcopy(g)
        fl = [1.5]; al = [0.0, 20.0]
        S.solve_monostatic_rcs_2d(g, fl, al, geometry_units='meters')
        S.solve_bistatic_rcs_2d(g, fl, al, al, geometry_units='meters')
        try:
            S.solve_monostatic_rcs_2d_certified(g, fl, al, geometry_units='meters')
        except Exception as e: print('cert err', name, str(e)[:200])
        print('mut', name, 'snapshot unchanged:', json.dumps(g, sort_keys=True, default=str) == json.dumps(g0, sort_keys=True, default=str), 'lists', fl, al)

if 'ref' in which:
    g = make('coatibc')
    for method in ('direct', 'auto'):
        r = S.solve_monostatic_rcs_2d(g, [0.8, 1.5, 3.0], [0.0, 40.0], geometry_units='meters', solver_method=method, mesh_reference_ghz=1.5)
        fm = r['metadata']['frequency_metadata']
        print('meshref', method, [(x['frequency_ghz'], x['metadata']['panel_count']) for x in fm])
        r2 = S.solve_monostatic_rcs_2d(g, [0.8], [0.0, 40.0], geometry_units='meters', solver_method=method, mesh_reference_ghz=1.5)
        r3 = S.solve_monostatic_rcs_2d(g, [0.8], [0.0, 40.0], geometry_units='meters', solver_method=method)
        print('   0.8GHz single-call with ref panels', r2['metadata']['panel_count'], 'no ref', r3['metadata']['panel_count'],
              'sweep-vs-single(0.8) TE %.1e' % rel(get(r, 'TE', 0.8), get(r2, 'TE')), 'info:', [i[:120] for i in r['metadata'].get('information', [])][:2])
    rb = S.solve_bistatic_rcs_2d(g, [0.8, 1.5, 3.0], [0.0], [0.0, 40.0], geometry_units='meters', mesh_reference_ghz=1.5)
    print('meshref bistatic', [(x['frequency_ghz'], x['metadata']['panel_count']) for x in rb['metadata']['frequency_metadata']])

if 'csv' in which:
    d = '/home/user/20261028_GRIM/tools/GHOST/ghost_backend/geometry/geometries/material_examples'
    from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
    for fn in ('type3_csv_dielectric.geo', 'type2_csv_ibc.geo', 'type1_csv_thin_dielectric.geo'):
        txt = open(os.path.join(d, fn)).read()
        g = lib.snap(txt)
        fl = [0.8, 0.93, 1.0, 1.2]
        for method in ('direct', 'auto'):
            r = S.solve_monostatic_rcs_2d(g, fl, [12.0, 48.0], geometry_units='meters', material_base_dir=d, solver_method=method)
            e = 0
            for f in fl:
                r1 = S.solve_monostatic_rcs_2d(g, [f], [12.0, 48.0], geometry_units='meters', material_base_dir=d, solver_method=method)
                e = max(e, rel(get(r, 'TE', f), get(r1, 'TE')), rel(get(r, 'TM', f), get(r1, 'TM')))
            rr = S.solve_monostatic_rcs_2d(g, fl[::-1], [12.0, 48.0], geometry_units='meters', material_base_dir=d, solver_method=method)
            e2 = max(rel(get(r, p, f), get(rr, p, f)) for f in fl for p in ('TE', 'TM'))
            print('csv', fn, method, 'sweep-vs-single max rel', e, 'reversed order', e2)

if 'abort' in which:
    g = make('two', N=-60)
    before = tmpfiles()
    for method in ('direct', 'auto'):
        for trip in (2, 6, 12, 25):
            ev = threading.Event(); calls = [0]
            def cb(done, total, msg):
                calls[0] += 1
                if calls[0] >= trip: ev.set()
            t = time.time()
            try:
                S.solve_monostatic_rcs_2d(g, [1.5, 1.7], list(np.linspace(0, 90, 7)), geometry_units='meters', solver_method=method, progress_callback=cb, abort_event=ev)
                print('abort', method, trip, 'completed without abort, callbacks', calls[0])
            except InterruptedError as e:
                print('abort', method, trip, 'InterruptedError after %.1fs' % (time.time()-t))
            except Exception as e:
                print('abort', method, trip, 'OTHER', type(e).__name__, str(e)[:200])
        r = S.solve_monostatic_rcs_2d(make('pec'), [1.5], [0.0], geometry_units='meters', solver_method=method)
        print('  post-abort solve ok', r['samples'][0]['rcs_db'])
    print('  new temp entries:', sorted(tmpfiles()-before)[:10])
    print('  threads alive:', [t.name for t in threading.enumerate()])

if 'thread' in which:
    names = ['pec', 'diel', 'coatibc', 'sheetpec', 'pecibc', 'two']
    for method in ('direct', 'auto'):
        serial = {n: S.solve_monostatic_rcs_2d(make(n), [1.5], [0.0, 35.0, 80.0], geometry_units='meters', solver_method=method) for n in names}
        out = {}; errs = {}
        def work(n):
            try: out[n] = S.solve_monostatic_rcs_2d(make(n), [1.5], [0.0, 35.0, 80.0], geometry_units='meters', solver_method=method)
            except Exception as e: errs[n] = repr(e)[:300]
        ths = [threading.Thread(target=work, args=(n,)) for n in names]
        [t.start() for t in ths]; [t.join() for t in ths]
        print('thread', method, 'errors', errs)
        for n in out:
            print('   ', n, 'TE %.1e TM %.1e' % (rel(get(out[n], 'TE'), get(serial[n], 'TE')), rel(get(out[n], 'TM'), get(serial[n], 'TM'))),
                  'warnings', len(out[n]['metadata']['warnings']), 'fact', out[n]['metadata'].get('dense_factorization_count'), serial[n]['metadata'].get('dense_factorization_count'))
