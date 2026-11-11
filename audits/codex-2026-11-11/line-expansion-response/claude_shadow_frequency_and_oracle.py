import sys, numpy as np
sys.path.insert(0,'tools/GHOST')  # run from the repository root of the audited tree
from ghost_backend.assembly.workflow import bor_shadow_triangles
from ghost_backend.geometry.occlusion import Occluder
from ghost_backend.geometry import line_visibility as LV
from ghost_backend.assembly.fields import radar_frame_basis
rng=np.random.default_rng(0)
def cyl(sag):
    profile=np.array([[0,.1],[.1,.1],[.1,-.1],[0,-.1]])
    return bor_shadow_triangles(profile,max_sag_m=sag,normal_tolerance_deg=2)[0]
for sag,label in ((299792458/.3e9/16,'cylinder as in Codex repro'),(1.0,'coarse cylinder')):
    tris=cyl(sag); print(label,'triangles',len(tris),'leaves',-(-len(tris)//256))
    N=400
    starts=rng.uniform(-.25,.25,(N,3)); ends=starts+rng.uniform(-.2,.2,(N,3))
    dirs=radar_frame_basis(list(rng.uniform(0,360,6)),list(rng.uniform(-80,80,6)))[0]
    crashed=0; total=0
    for d in dirs[:12]:
        for i in range(N):
            total+=1
            try: Occluder(tris).visible_line_intervals(starts[i:i+1],ends[i:i+1],d)
            except TypeError: crashed+=1
    print('  unpatched: crashed on',crashed,'of',total,'single-line queries')
    # bypass the crash only: normalise interval items to lists
    orig=LV._union
    LV._union=lambda intervals: orig([list(x) for x in intervals])
    worst=0.0; partial=0; full=0
    for d in dirs[:12]:
        occ=Occluder(tris)
        own,lo,hi=occ.visible_line_intervals(starts,ends,d)
        vis=np.zeros(N)
        np.add.at(vis,own,hi-lo)
        t=(np.arange(2000)+.5)/2000
        for i in range(0,N,4):
            pts=starts[i]+t[:,None]*(ends[i]-starts[i])
            ref=np.mean(occ.visible(pts,d))
            worst=max(worst,abs(ref-vis[i])); partial+= 0.02<ref<0.98; full+= ref<=0.02
    LV._union=orig
    print('  crash bypassed: max |visible fraction - 2000-point sampling| =',round(worst,5),'| partially shadowed lines',partial,'| fully shadowed',full)

