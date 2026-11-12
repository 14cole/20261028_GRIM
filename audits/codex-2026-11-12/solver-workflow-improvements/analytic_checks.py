import json,sys,pathlib,numpy as np,os
sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.validation.cylinder import sigma_pec_cylinder,sigma_dielectric_cylinder,sigma_coated_pec_cylinder
D=pathlib.Path(os.environ.get('GRIM_EVIDENCE_DIR',pathlib.Path(__file__).parent));checks=[];cache={}
for p in sorted(D.glob('*.json')):
 try:r=json.loads(p.read_text())
 except Exception:continue
 if not isinstance(r,dict) or 'wall' not in r or r.get('error') is not None or r.get('body') not in ('pec','diel','coated'):continue
 samples=r.get('samples_complete',[]);a=r.get('radius',1.)
 for f in sorted({x['frequency_ghz'] for x in samples}):
  for pol in ['TE','TM']:
   key=(r['body'],a,f,pol)
   if key not in cache:
    cache[key]=(sigma_pec_cylinder(a,f*1e9,pol) if r['body']=='pec' else sigma_dielectric_cylinder(a,4-.2j,1,f*1e9,pol) if r['body']=='diel' else sigma_coated_pec_cylinder(.7*a,a,3-.06j,1,f*1e9,pol))
   values=np.array([x['rcs_linear'] for x in samples if x['polarization_internal']==pol and x['frequency_ghz']==f]);err=float(np.max(abs(10*np.log10(values/cache[key]))))
   checks.append(dict(case=p.stem,frequency_ghz=f,polarization=pol,max_rcs_error_db=err,passed=bool(np.isfinite(err) and err<.05)))
summary=dict(checks=checks,worst_db=max(x['max_rcs_error_db'] for x in checks),failures=[x for x in checks if not x['passed']])
(D/'ANALYTIC_CHECKS.json').write_text(json.dumps(summary,indent=2)+'\n')
print(len(checks),summary['worst_db'],summary['failures'])
