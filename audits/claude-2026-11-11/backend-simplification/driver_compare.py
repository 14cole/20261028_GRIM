import json, sys, numpy as np, os
S=sys.argv[1]
for spec in ('local-twod-0','local-twod-1','hpc-twod-0','hpc-twod-1','local-bor-0','local-bor-1','hpc-bor-0','hpc-bor-1'):
    pa, pb = (os.path.join(S,'drvout',t+'-'+spec) for t in ('base','new'))
    if not (os.path.exists(pa+'/arrays.npz') and os.path.exists(pb+'/arrays.npz')):
        print(spec,'MISSING', os.path.exists(pa+'/arrays.npz'), os.path.exists(pb+'/arrays.npz')); continue
    a,b=np.load(pa+'/arrays.npz'),np.load(pb+'/arrays.npz')
    ea,eb=json.load(open(pa+'/events.json')),json.load(open(pb+'/events.json'))
    keys_equal=sorted(a.files)==sorted(b.files)
    diff=[k for k in a.files if k in b.files and not (a[k].shape==b[k].shape and a[k].dtype==b[k].dtype and np.array_equal(a[k],b[k],equal_nan=(a[k].dtype.kind in 'fc')))]
    field=[k for k in a.files if k.split('::')[1].startswith('rcs_')]
    ev={k:(ea[k],eb[k]) for k in ea if k not in ('frozen_runtime_files',) and ea[k]!=eb.get(k)}
    print(spec,'| artifacts',len(ea['artifacts']),'| arrays',len(a.files),'| same keys',keys_equal,'| field arrays',len(field),'| arrays differing',[d.split('/')[-1] for d in diff][:6],'| event differences',{k:(str(v[0])[:60],str(v[1])[:60]) for k,v in ev.items()})
    if spec.startswith('hpc'): print('     ',{k:eb.get(k) for k in ('worker_rc','resume_rc','resume_rewrote','partial_rc','partial_restored_victim','partial_rewrote_others','partial_arrays_equal','tamper_rc','tamper_restored_victim','tamper_artifact_count')}, '|', eb['tamper_message'][:110])
