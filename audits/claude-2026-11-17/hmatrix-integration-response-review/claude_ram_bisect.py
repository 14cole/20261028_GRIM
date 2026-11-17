"""Reviewer check: smallest solver RAM budget at which each production tree completes a real solve."""
import os,sys,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;trees=json.loads(sys.argv[1]);out={}
G=dict(count=180,hook='claude_builder',builder='production',packing='none',frequency_ghz=5.0,method='compressed')
cases={'partial-TE':dict(G,material='partial',shape='partial',length_m=0.6,eps=[12.0,-0.01],pol='TE'),'pec-circle-TE':dict(G,material='pec',shape='circle',length_m=3.0,pol='TE')}
def run(tree,root,case,gib):
    label=f'{tree}-{case}-ram{int(round(gib*1024))}';o=HERE/'ram'/label
    if not Path(str(o)+'.json').exists():
        spec=dict(cases[case],ram_gib=gib,out=str(o));env=dict(os.environ,GRIM_ROOT=root,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with open(str(o)+'.log','w') as log:rc=subprocess.run([sys.executable,str(HERE/'claude_run_geometry3.py'),json.dumps(spec)],env=env,stdout=log,stderr=subprocess.STDOUT).returncode
        if not Path(str(o)+'.json').exists():Path(str(o)+'.json').write_text(json.dumps(dict(error='no record; return code %d'%rc,peak_gib=None,factors=[])))
    d=json.loads(Path(str(o)+'.json').read_text());f=d['factors'][0] if d.get('factors') else {}
    return dict(mib=int(round(gib*1024)),ok=d.get('error') is None,error=(d.get('error') or '')[:220],peak_gib=d.get('peak_gib'),builds=(d.get('hooks') or {}).get('builds'),inverse_bytes=[p.get('bytes') for p in f.get('preconditioners',[])],refinement=f.get('refinement_steps'))
for case in cases:
    for tree,root in trees.items():
        trail=[];hi=1.0;lo=0.03125;r=run(tree,root,case,hi);trail.append(r);assert r['ok'],r
        r=run(tree,root,case,lo);trail.append(r)
        if r['ok']:out[f'{tree}|{case}']=dict(threshold_mib='below %d'%r['mib'],trail=trail);continue
        while (hi-lo)*1024>4:
            mid=round((hi+lo)/2*256)/256;r=run(tree,root,case,mid);trail.append(r)
            if r['ok']:hi=mid
            else:lo=mid
        out[f'{tree}|{case}']=dict(lowest_passing_mib=int(round(hi*1024)),highest_failing_mib=int(round(lo*1024)),failing_error=[t['error'] for t in trail if t['mib']==int(round(lo*1024))][0],trail=trail)
        print(tree,case,{k:v for k,v in out[f'{tree}|{case}'].items() if k!='trail'},flush=True)
json.dump(out,open(HERE/'claude_ram_bisect.json','w'),indent=1)
