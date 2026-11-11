import sys,json,importlib
sys.path.insert(0,sys.argv[1]+'/tools/GHOST')
unit=dict(geometry='x.geo',geometry_stem='x',frequency_ghz=1.25,polarization='HH',geometry_input_sha256='c'*64)
context={k:k+'value' for k in ['run_id','solver_source_sha256','runtime_environment_sha256','run_solve_spec_sha256','solver_config_sha256','angular_grid_sha256']}
context.update(solver_config={},aspects_deg=[0.,90.])
res={}
for name in ['runs.local_twod_driver','hpc.twod_driver','runs.local_bor_driver','hpc.bor_driver']:
 m=importlib.import_module('ghost_backend.'+name);m.load_default_settings()
 res[name]={'settings':m.current_settings(),'attestation':m._unit_attestation_fields(context,unit)}
print(json.dumps(res,sort_keys=True))
