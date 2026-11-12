"""Selected workflow controls and interleaved repeat measurements."""
import json,sys
from pathlib import Path
from monitor import run
P=Path(__file__).resolve().parent;root=Path(sys.argv[1]);catalog=json.loads((P/'catalog.json').read_text());cases=[]
def get(model,backend,variant):return next(x for x in catalog if x['geometry_id']==model and x['backend']==backend and x['variant']==variant)
# Existing assembly settings: practical allocation/speed tradeoff without numerical changes.
for model in ['diel4k','pec8k']:
 for tile in [64,128]:
  s=dict(get(model,'dense','baseline'));s.pop('capture_matrix',None);s.update(case=f'{model}-dense-tile{tile}',variant=f'tile{tile}',options=dict(assembly_tile=tile));cases.append(s)
# Each method receives two further runs; reverse order in the second round.
for rep in [1,2]:
 for model,backend,variants in [('pec4k','dense',['baseline','fourier']),('star','dense',['baseline','scaled_mixed']),('pec8k','dense',['baseline','mixed','disk32','fourier']),('diel8k','compressed',['baseline','inverse32_build']),('star','compressed',['baseline','inverse32_build'])]:
  for v in variants[::1 if rep==1 else -1]:
   s=dict(get(model,backend,v));s.pop('capture_matrix',None);s.update(case=s['case']+f'-r{rep}',repeat=rep);cases.append(s)
for model in ['pec4k','diel4k','star','pec8k','diel8k']:
 s=dict(get(model,'compressed','baseline'));s.update(case=model+'-compressed-inverse32_fast',variant='inverse32_fast');cases.append(s)
for n in [1792,7168]:
 for backend,variant in [('dense','baseline'),('dense','sector7'),('compressed','baseline')]:
  s=dict(get('pec8k',backend,'baseline'));s.pop('capture_matrix',None);s.update(case=f'star7-{n}-{backend}-{variant}',geometry_id=f'star7-{n}',shape='star',n=n,frequency_ghz=1.,variant=variant);cases.append(s)
for backend,variant in [('dense','baseline'),('dense','mixed'),('dense','disk32'),('compressed','baseline'),('compressed','inverse32_fast')]:
 s=dict(get('diel8k',backend,'baseline'));s.pop('capture_matrix',None);s.update(case=f'diel8k-181-{backend}-{variant}',geometry_id='diel8k-181',angles=181,variant=variant,storage='disk' if variant.startswith('disk') else 'auto');cases.append(s)
for backend,variant in [('dense','baseline'),('dense','scaled_mixed'),('compressed','baseline'),('compressed','inverse32_fast')]:
 s=dict(get('diel4k',backend,'baseline'));s.pop('capture_matrix',None);s.update(case=f'diel15GHz-{backend}-{variant}',geometry_id='diel15GHz',frequency_ghz=15.,length_m=6.096*.8/15.,variant=variant);cases.append(s)
for model in ['diel4k','diel8k']:
 s=dict(get(model,'dense','baseline'));s.pop('capture_matrix',None);s.update(case=f'{model}-dense-schur',variant='schur');cases.append(s)
for model in ['pec4k','pec8k']:
 s=dict(get(model,'dense','baseline'));s.pop('capture_matrix',None);s.update(case=f'{model}-dense-baseline-r3',repeat=3);cases.append(s)
s=dict(get('pec8k','dense','disk32'));s.update(case='pec8k-dense-disk32-r3',repeat=3);cases.append(s)
# Nonuniform geometry must not enter the rotational-symmetry route.
s=dict(get('diel4k','dense','fourier'));s.update(case='ellipse-fourier-rejection',geometry_id='ellipse-fourier',shape='ellipse',aspect=.6,n=512);cases.append(s)
s=dict(next(x for x in cases if x['case']=='diel15GHz-compressed-baseline'));s.update(case='diel15GHz-compressed-operator14',variant='operator14');cases.append(s)
(P/'followup_catalog.json').write_text(json.dumps(cases,indent=2)+'\n')
for s in cases:
 if len(sys.argv)>2 and s['case'] not in sys.argv[2:]:continue
 run(root,s)
