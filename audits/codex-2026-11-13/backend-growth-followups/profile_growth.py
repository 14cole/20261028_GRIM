"""Run the unmodified production control with cProfile and per-level storage."""
import cProfile,json,pstats,runpy,sys
from pathlib import Path
spec=json.loads(sys.argv[1]); dest=Path(spec['out'])
p=cProfile.Profile();p.enable()
g=runpy.run_path(str(Path(__file__).with_name('compressed_control.py')),run_name='__main__')
p.disable();p.dump_stats(str(dest)+'.prof')
h=g['h']; levels={}
for row in h.far:
 level=int(h.tree.level[row.row]); d=levels.setdefault(level,dict(lists=0,bytes=0,ranks=[],shapes=[]))
 d['lists']+=1;d['bytes']+=row.nbytes;d['ranks'].append(row.u.shape[1]);d['shapes'].append(list(row.u.shape)+[row.v.shape[1]])
Path(str(dest)+'.levels.json').write_text(json.dumps(levels,indent=2))
with open(str(dest)+'.profile.txt','w') as f:
 pstats.Stats(p,stream=f).strip_dirs().sort_stats('cumulative').print_stats(65)
 pstats.Stats(p,stream=f).strip_dirs().sort_stats('tottime').print_stats(40)
