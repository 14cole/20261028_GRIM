from dlib import *
import sys, json
case=sys.argv[1]; f=float(sys.argv[2]); w=int(sys.argv[3]) if len(sys.argv)>3 else 2
P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
asp=list(np.linspace(0,180,19))
if case=='pec': g=geo([('b',2,'2 0 0 0 0',rows(P))])
if case=='ibc': g=geo([('b',2,'2 0 10 0 0',rows(P))],ibc='10 constant 100 50 0 0')
if case=='diel': g=geo([('b',3,'3 0 0 1 0',rows(P))],diel='1 2.5 -0.1 1 0')
if case=='coat':
    Pc=[(0,0.28),(0.09,0.1),(0.09,-0.09),(0,-0.09)]
    g=geo([('o',3,'3 0 0 1 0',rows(P)),('c',4,'4 0 0 1 0',rows(Pc))],diel='1 2.5 -0.1 1 0')
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    t=time.time(); e=D.estimate_bor_resources(g,f,asp,geometry_units='meters',workers=w,mesh_certification=False); te=time.time()-t
t=time.time(); r=run(g,f,asp,workers=w); ts=time.time()-t
rp=r['metadata']['runtime_profile']; pf=r['metadata']['per_frequency'][0]
print(json.dumps(dict(case=case,f=f,workers=w,est_elems=e['mesh_elements'],est_unknowns=e['n_unknowns_estimate'],n_unknowns=pf['n_unknowns'],
  est_modecap=e['mode_cap_estimate'],modes_used=pf['modes_used'],est_peak_gb=round(e['estimated_peak_gb'],3),held_assembly_gb=round(e['held_assembly_gb'],3),
  persistent_gb=round(e['persistent_assembly_gb'],3), linear_peak_gb=round(e['worker_plan']['linear_peak_gb'],4), near_scratch_gb=e['near_preparation']['scratch_gb'],
  rss_peak_gb=round(rp['sampled_peak_process_rss_bytes']/1e9,3), rss_init_gb=round(rp['initial_process_rss_bytes']/1e9,3), tree_rss_gb=round((rp.get('sampled_peak_process_tree_rss_bytes') or 0)/1e9,3),
  t_est=round(te,2), t_solve=round(ts,1), stages={k:round(v,1) for k,v in rp['stage_seconds'].items()}, near_backend=pf['near_preparation'].get('backend'), near_workers=pf['near_preparation'].get('workers'), mode_workers=pf['modal_execution']['worker_plan']['workers'])),flush=True)
