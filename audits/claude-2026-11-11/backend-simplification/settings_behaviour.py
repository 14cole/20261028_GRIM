import sys, importlib, json, pickle, copy
root=sys.argv[1]; sys.path.insert(0, root+'/tools/GHOST')
out={}
for name in ('runs.local_twod_driver','hpc.twod_driver','runs.local_bor_driver','hpc.bor_driver'):
    d=importlib.import_module('ghost_backend.'+name); r={}
    r['attr_before_configure']=hasattr(d,'GEOMETRY_UNITS')
    r['settings_before_configure']=d.current_settings()
    d.load_default_settings(); s=d.current_settings()
    r['default_keys']=sorted(s); r['defaults']=json.loads(json.dumps(s,default=str,sort_keys=True))
    r['attr_read']=d.GEOMETRY_UNITS
    bad=dict(s); bad.pop('GEOMETRY_UNITS')
    try: d.configure(bad, script=__file__); r['missing']='accepted'
    except Exception as e: r['missing']=type(e).__name__+': '+str(e)
    r['after_rejected_configure_units']=d.current_settings().get('GEOMETRY_UNITS','<gone>')
    s2=dict(s); s2['GEOMETRY_UNITS']='meters'; s2['EXTRA_UNKNOWN_KEY']=1
    try:
        d.configure(s2, script=__file__); r['reconfigure_units']=d.GEOMETRY_UNITS; r['extra_key_kept']='EXTRA_UNKNOWN_KEY' in d.current_settings()
    except Exception as e: r['reconfigure_units']=type(e).__name__+': '+str(e)[:120]
    freq=[k for k in s if 'FREQ' in k][0]; lst=list(s[freq]) if isinstance(s[freq],(list,tuple)) else [1.0]
    s3=dict(s2); s3.pop('EXTRA_UNKNOWN_KEY'); s3[freq]=lst
    try:
        d.configure(s3, script=__file__); lst.append(123.0); r['caller_mutation_visible']=123.0 in d.current_settings()[freq]
        got=d.current_settings(); got[freq]=['x']; r['returned_dict_mutation_visible']=d.current_settings()[freq]==['x']
    except Exception as e: r['caller_mutation_visible']=type(e).__name__+': '+str(e)[:120]
    try: r['unknown_attr']=d.NOT_A_SETTING
    except Exception as e: r['unknown_attr']=type(e).__name__
    r['pickle_roundtrip_equal']=pickle.loads(pickle.dumps(d.current_settings()))==d.current_settings()
    out[name]=r
print(json.dumps(out,indent=1,sort_keys=True,default=str))
