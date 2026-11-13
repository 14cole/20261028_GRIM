import pathlib,json
from run_methods import run
from geometry_cases import build
D=pathlib.Path(__file__).parent
for policy,extra in [('control',{}),('scaled',{'scaled_inverse':True}),('float32',{'inverse_float32':True})]:
 run('holdout-adjoint-'+policy,dict(body='diel',n=600,mode='compressed',angles=3,random_rhs_checks=True,**extra))
for case,geometry in [('lossless-star',dict(shape='star',material='diel',length_m=2.,frequency_ghz=1.,eps=[4.,0.],n=2200)),('thin-coating',dict(shape='circle',material='coated',length_m=2.,frequency_ghz=.5,eps=[3.,-.06],n=500,inner_ratio=.99))]:
 text,meta=build(geometry);path=D/(case+'.geo');path.write_text(text)
 (D/(case+'-geometry.json')).write_text(json.dumps(dict(geometry,generated=meta),indent=2))
 policies=[('control',{}),('scaled-coarse',{'scaled_inverse':True,'coarse_initial':True}),('float32',{'inverse_float32':True})]
 if case=='lossless-star':policies.append(('coarse',{'coarse_initial':True}))
 for policy,extra in policies:run('holdout-'+case+'-'+policy,dict(body='custom',geo=str(path),f=geometry['frequency_ghz'],mode='compressed',angles=19,probe_profile=True,**extra))
