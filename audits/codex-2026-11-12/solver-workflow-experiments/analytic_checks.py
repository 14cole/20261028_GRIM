import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.validation.cylinder import sigma_pec_cylinder,sigma_dielectric_cylinder,sigma_coated_pec_cylinder
P=Path(__file__).resolve().parent;checks=[];references={}
for f in sorted((P/'results').glob('*.json')):
 if f.name.count('.')!=1:continue
 r=json.loads(f.read_text());s=r['spec']
 if r['error'] is not None or s.get('shape','circle')!='circle':continue
 samples=json.loads(f.with_suffix('.samples.json').read_text());radius=s['length_m']/2;eps=complex(*s.get('eps',[4,-.2]));freq=s['frequency_ghz']*1e9
 for pol in ['TE','TM']:
  key=(s['material'],radius,eps,freq,pol)
  if key not in references:
   references[key]=(sigma_pec_cylinder(radius,freq,pol) if s['material']=='pec' else sigma_dielectric_cylinder(radius,eps,1,freq,pol) if s['material']=='diel' else sigma_coated_pec_cylinder(radius*s.get('inner_ratio',.7),radius,eps,1,freq,pol))
  reference=references[key];values=np.array([x['rcs_linear'] for x in samples if x['polarization_internal']==pol]);error=float(np.max(abs(10*np.log10(values/reference))))
  assert np.isfinite(error) and error<.05,(s['case'],pol,error)
  checks.append(dict(case=s['case'],polarization=pol,max_rcs_error_db=error,samples=len(values)))
(P/'ANALYTIC_CHECKS.json').write_text(json.dumps(dict(checks=checks,worst_db=max(x['max_rcs_error_db'] for x in checks)),indent=2)+'\n');print('Analytic checks',len(checks),'worst dB',max(x['max_rcs_error_db'] for x in checks))
