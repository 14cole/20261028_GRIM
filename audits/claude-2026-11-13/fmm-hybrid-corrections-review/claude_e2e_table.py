import json, glob, os, numpy as np
rows = {}
for t in sorted(glob.glob('results/*.time')):
    name = os.path.basename(t)[:-5]; tm = json.load(open(t))
    try: r = json.loads(open('results/%s.json' % name).read().strip().splitlines()[-1])
    except Exception: print(name, 'FAILED', tm, open('results/%s.stderr' % name).read()[-300:]); continue
    if 'fmm_setup_seconds' in r:
        d = dict(setup=r['compressed_operator_seconds']+r['fmm_setup_seconds'], factor=r['compressed_inverse_seconds'], solve=r['solve_seconds'], its=[x['iterations'] for x in r['results']],
                 retained_mib=(r['fmm_bytes']+r['preconditioner_reachable_array_bytes'])/2**20, inverse_mib=r['inverse_bytes']/2**20, fmm_mib=r['fmm_bytes']/2**20, pre_op_s=r['compressed_operator_seconds'], fmm_s=r['fmm_setup_seconds'],
                 peak_before_validation=r['peak_before_reference_gib'], rowerr=max(r['exact_sampled_rowwise_backward_error']))
    elif 'lu_bytes' in r: d = dict(setup=r['assembly_seconds'], factor=r['factor_seconds'], solve=r['solve_seconds'], retained_mib=r['lu_bytes']/2**20)
    else: d = dict(setup=r['assembly_seconds'], factor=r['factor_seconds'], solve=r['solve_seconds'], retained_mib=(r['operator_bytes']+r['inverse_bytes'])/2**20, inverse_mib=r['inverse_bytes']/2**20)
    d.update(wall=tm['wall_s'], peak=tm['peak_gib'], n=r['n'], k=r['k']); rows[name] = d
    print(name, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}))
def field(name): return np.load('results/%s.npz' % name)
for a, b in (('e2e-fmm-4096', 'e2e-dense-4096'), ('e2e-comp-4096', 'e2e-dense-4096'), ('e2e-fmm-stream-4096', 'e2e-dense-4096'), ('e2e-fmm-4096-r2', 'e2e-dense-4096'), ('ppw-fmm-2048', 'ppw-comp-2048'), ('ppw-fmm-8192', 'ppw-comp-8192')):
    if os.path.exists('results/%s.npz' % a) and os.path.exists('results/%s.npz' % b):
        x, y = field(a), field(b); print(a, 'vs', b, 'field %.2e density %.2e' % (abs(x['field']-y['field']).max()/abs(y['field']).max(), abs(x['density']-y['density']).max()/abs(y['density']).max()))
