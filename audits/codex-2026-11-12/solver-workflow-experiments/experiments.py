import json,sys
from pathlib import Path
from monitor import run
P=Path(__file__).resolve().parent
for d in ('results','geometries','matrices'): (P/d).mkdir(exist_ok=True)
base=dict(material='pec',shape='circle',length_m=6.096,frequency_ghz=.8,cap=8.,cpus=4,angles=19,timeout=240)
models=[('pec4k',dict(n=4000)),('diel4k',dict(n=2000,material='diel',frequency_ghz=.8)),('coated4k',dict(n=1500,material='coated',frequency_ghz=.6)),('star',dict(n=1600,material='coated',shape='star',inner_ratio=.95,length_m=1.,frequency_ghz=1.)),('pec8k',dict(n=8000,frequency_ghz=1.8)),('diel8k',dict(n=4000,material='diel',frequency_ghz=1.5))]
cases=[]
for name,m in models:
 for backend,variants in [('dense',['baseline','mixed','scaled_mixed','disk4','disk32','disk_zstd']),('compressed',['baseline','inverse32','inverse32_build','compact'])]:
  for variant in variants:
   spec=dict(base,**m);spec.update(case=name+'-'+backend+'-'+variant,geometry_id=name,backend=backend,variant=variant,group=name,storage='disk' if variant.startswith('disk') else 'auto')
   if backend=='dense' and variant=='baseline' and name in ('pec4k','diel4k','pec8k'):spec['capture_matrix']=True
   cases.append(spec)
 if name in ('pec4k','diel4k','pec8k','diel8k'):
  spec=dict(base,**m);spec.update(case=name+'-dense-fourier',geometry_id=name,backend='dense',variant='fourier',group=name);cases.append(spec)
(P/'catalog.json').write_text(json.dumps(cases,indent=2)+'\n')
for spec in cases:
 if len(sys.argv)>2 and spec['group'] not in sys.argv[2:] and spec['case'] not in sys.argv[2:]:continue
 run(Path(sys.argv[1]),spec)
