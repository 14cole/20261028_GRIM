import sys, os
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ.pop('GHOST_BACKEND_PATH',None)
root=os.path.abspath(sys.argv[1]); sys.path.insert(0,root)
from GRIM_Backend.integrations import ghost as G
print(os.path.basename(root),'discover_ghost_backend ->', G.discover_ghost_backend(None))
for name in ('assembly_inspector','grim_io','line_expand'):
    try:
        m=G.load_ghost_module(name); print('   load_ghost_module(%r) ok: %s'%(name, os.path.relpath(m.__file__,root)))
    except Exception as e: print('   load_ghost_module(%r) FAILED: %s: %s'%(name,type(e).__name__,str(e)[:150]))
