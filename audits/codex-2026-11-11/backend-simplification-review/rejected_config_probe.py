import sys,importlib,json
sys.path.insert(0,sys.argv[1]+'/tools/GHOST');out={}
for name in ['runs.local_bor_driver','hpc.bor_driver']:
 m=importlib.import_module('ghost_backend.'+name);m.load_default_settings();before=m.current_settings();bad=dict(before,GEOMETRY_UNITS='meters',BOR_EXECUTION_OPTIONS={'factorization':'invalid'})
 try:m.configure(bad,script=__file__)
 except Exception as e:error=type(e).__name__+': '+str(e)
 after=m.current_settings();out[name]={'error':error,'previous_settings_preserved':after==before,'before_units':before['GEOMETRY_UNITS'],'after_units':after['GEOMETRY_UNITS'],'after_options':after['BOR_EXECUTION_OPTIONS']}
print(json.dumps(out,sort_keys=True))
