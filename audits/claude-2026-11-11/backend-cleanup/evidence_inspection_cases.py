import sys, json, numpy as np
sys.path.insert(0, sys.argv[1]+'/tools/GHOST')
import ghost_backend.data_tools.cem_tools.grim_native as g
K=g.MESH_CERTIFICATION_KEY; S=g.MESH_CERTIFICATION_SCHEMA
good={'schema':S}
cases={'empty':{}, 'garbage':{K:np.asarray('{not json')}, 'wrong schema':{K:np.asarray(json.dumps({'schema':'nope'}))}, 'list':{K:np.asarray(json.dumps([1,2]))},
 'schema only':{K:np.asarray(json.dumps(good))}, 'sources not list':{K:np.asarray(json.dumps(dict(good,sources=5)))}, 'sources empty':{K:np.asarray(json.dumps(dict(good,sources=[])))},
 'source not dict':{K:np.asarray(json.dumps(dict(good,sources=[1])))}, 'source partial':{K:np.asarray(json.dumps(dict(good,sources=[{'polarization':'VV'}])))},
 'bad pol':{K:np.asarray(json.dumps(dict(good,sources=[{'polarization':'XX','quality_gate':{'passed':True}}])))},
 'nan':{K:np.asarray(float('nan'))}, 'array':{K:np.asarray(['a','b'])}, 'huge nesting':{K:np.asarray(json.dumps({'schema':S,'sources':[{'quality_gate':{'passed':True},'mesh_convergence':{'passed':True,'published_mesh':'fine'}}]}))}}
out={}
for n,p in cases.items():
    try: out[n]=repr(g._mesh_certification_sources(p,'L'))
    except Exception as e: out[n]=type(e).__name__+': '+str(e)
print(json.dumps(out,sort_keys=True))
