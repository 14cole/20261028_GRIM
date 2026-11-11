import coverage, glob, os, sys, collections
root=sys.argv[1]+'/tools/GHOST/ghost_backend/'
ex={}
for name in ('dense','tile','hmatrix'):
    d=collections.defaultdict(set)
    for f in glob.glob('covdata/%s.*'%name):
        c=coverage.CoverageData(f); c.read()
        for m in c.measured_files():
            d[os.path.relpath(m,root)]|=set(c.lines(m) or [])
    ex[name]=d
files=sorted(set().union(*[set(d) for d in ex.values()]))
def pk(f): return f.split('/')[0] if '/' in f else '.'
tot=collections.Counter(); 
rows=[]
for f in files:
    D,T,H=(ex[n].get(f,set()) for n in ('dense','tile','hmatrix'))
    only_t=T-D-H; only_h=H-D-T; only_d=D-T-H; comp=(T|H)-D
    rows.append((f,len(D|T|H),len(only_d),len(only_t),len(only_h),len(comp)))
    for k,v in zip(('any','only_d','only_t','only_h','comp'),rows[-1][1:]): tot[(pk(f),k)]+=v; tot[('ALL',k)]+=v
print('executed statements: file any dense-only tile-only hmatrix-only compressed-only')
for r in rows:
    if r[2]+r[3]+r[4]>15: print('%-45s %5d %5d %5d %5d %5d'%r)
print()
for p in sorted(set(k[0] for k in tot)):
    print('%-12s'%p,*[tot[(p,k)] for k in ('any','only_d','only_t','only_h','comp')])
