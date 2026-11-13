import json,pstats
from pathlib import Path
import numpy as np
root=Path('results');out={}
for unknowns in [16384,32768]:
 stem=root/f'growth-{unknowns}'
 if not stem.with_suffix('.npz').exists():continue
 d=json.loads(stem.with_suffix('.json').read_text());p=pstats.Stats(str(stem)+'.prof');categories={}
 # Cumulative categories overlap and must not be summed.
 names={'far_native':('far.py','run'),'near':('operators.py','_near_pair_blocks'),'cross':('hmatrix.py','cross_approximation'),'norms':('hmatrix.py','_norms'),'sample':('hmatrix.py','_sample'),'coefficients':('coefficients.py','get_with_error'),'qr':('_decomp_qr.py','safecall')}
 for label,(file,function) in names.items():
  matches=[v for k,v in p.stats.items() if Path(k[0]).name==file and k[2]==function]
  categories[label]=dict(calls=sum(v[1] for v in matches),self_seconds=sum(v[2] for v in matches),cumulative_seconds=sum(v[3] for v in matches))
 row=dict(assembly_seconds=d['assembly_seconds'],factor_seconds=d['factor_seconds'],solve_seconds=d['solve_seconds'],operator_bytes=d['operator_bytes'],inverse_bytes=d['inverse_bytes'],evidence=d['operator_evidence'],profile=categories)
 levels=Path(str(stem)+'.levels.json')
 if levels.exists():
  row['levels']={k:dict(lists=v['lists'],bytes=v['bytes'],rank_min=min(v['ranks']),rank_max=max(v['ranks']),rank_mean=float(np.mean(v['ranks']))) for k,v in json.loads(levels.read_text()).items()}
 out[str(unknowns)]=row
for file in root.glob('norms-*-norms.json'):
 d=json.loads(file.read_text());d['norm_time_reduction']=1-d['medians']['new']/d['medians']['old'];out[file.stem]=d
comparisons=[]
for a,b in [('growth-16384','norms-16384-1-TE'),('norms-4096-1-TE','norms-4096-4-TE'),('fmm-4096-reference','fmm-4096-native'),('fmm-8192-reference','fmm-8192-native'),('dense-reference-8192','fmm-8192-native'),('compressed-reference-8192','fmm-8192-native')]:
 if not all((root/(s+'.npz')).exists() for s in [a,b]):continue
 aa=np.load(root/(a+'.npz'));bb=np.load(root/(b+'.npz'))
 row=dict(reference=a,candidate=b)
 for key in ['density','field']:
  row[key]=dict(bitwise=bool(np.array_equal(aa[key],bb[key])),relative=float(np.linalg.norm(aa[key]-bb[key])/np.linalg.norm(aa[key])),relative_max=float(abs(aa[key]-bb[key]).max()/abs(aa[key]).max()))
 comparisons.append(row)
out['comparisons']=comparisons
for name in ['fmm-4096-reference','fmm-4096-native','fmm-8192-reference','fmm-8192-native']:
 p=root/(name+'.json')
 if p.exists():out[name]=json.loads(p.read_text())
for pair in comparisons:
 if pair['reference'].startswith(('growth-','norms-')):assert pair['field']['bitwise'] and pair['density']['bitwise']
 else:assert pair['field']['relative_max']<1e-10
(root/'SUMMARY.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
