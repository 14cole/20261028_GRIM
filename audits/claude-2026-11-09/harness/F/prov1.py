import sys, os, time
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
from ghost_backend.execution import provenance as P
from ghost_backend.execution.paths import backend_root
import ghost_backend.hpc.scheduler as H
root=str(backend_root())
def t(label,n=3):
    for i in range(n):
        a=time.perf_counter(); c=time.process_time(); fp=P.backend_source_fingerprint(root,{}); print(label,i,'wall ms',round(1e3*(time.perf_counter()-a),1),'cpu ms',round(1e3*(time.process_time()-c),1))
t('no cache')
H.install_fingerprint_cache()
t('fingerprint cache')
a=time.process_time(); P.runtime_environment_fingerprint(); print('runtime env fp cpu ms', round(1e3*(time.process_time()-a),1))
a=time.process_time(); P.runtime_environment_fingerprint(); print('runtime env fp cpu ms (2nd)', round(1e3*(time.process_time()-a),1))
print('files', len(P.backend_source_records(root)))
