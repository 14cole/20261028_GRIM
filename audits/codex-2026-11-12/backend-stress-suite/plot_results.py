"""Standalone scientific figures; no solver execution."""
import json,os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/ghost-stress-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from geometry_cases import build
from suite import catalog
from experiments import experiments
P=Path(__file__).resolve().parent;(P/'figures').mkdir(exist_ok=True)
data=json.loads((P/'SUMMARY.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
for method,color in [('dense','#b34c20'),('compressed','#246ca6')]:
    rows=[r for r in data['rows'] if r['backend']==method and r['status']=='success' and r['group'] not in ('experiment','extension')]
    for ax,key in zip(axes,('peak_tree_rss_gib','wall_seconds')):
        ax.scatter([r['actual_unknowns'] for r in rows],[r[key] for r in rows],s=25,alpha=.75,label=method.title(),color=color)
        ax.set_xscale('log');ax.set_yscale('log');ax.grid(alpha=.2,which='both');ax.set_xlabel('Actual system unknowns')
axes[0].set_ylabel('Peak process-tree RSS (GiB)');axes[1].set_ylabel('Solve wall time (seconds)')
axes[0].axhline(8,color='#555',ls='--',lw=1,label='8 GiB solve budget')
axes[0].legend();axes[1].legend();fig.suptitle('Completed baseline cases: four CPUs, unchanged production solver')
fig.savefig(P/'figures/backend-scaling.svg');fig.savefig(P/'figures/backend-scaling.png',dpi=160);plt.close(fig)
names=['small-pec','small-dielectric','small-coated','small-multilayer','small-star-coated','large-ellipse-dielectric','small-cavity','small-comb','close-dielectric-bodies','partial-coating-small','millimeter-coating','20ft-complex-thin-coating']
cases={c['geometry_id']:c for c in catalog()+experiments()}
fig,axes=plt.subplots(3,4,figsize=(12,9),layout='constrained')
for ax,name in zip(axes.ravel(),names):
    spec=cases[name];text,_=build(spec);points=[];kind=0
    def draw():
        if points:
            a=np.array(points);ax.plot(a[:,0],a[:,1],lw=1,color='#246ca6' if kind in (3,5) else '#383838')
    for line in text.splitlines():
        if line.startswith('Segment:'):
            draw();points=[];kind=int(line.split()[-1])
        elif len(line.split())==4:
            try:x0,y0,x1,y1=map(float,line.split())
            except ValueError:continue
            if not points:points.append((x0,y0))
            points.append((x1,y1))
    draw();ax.set_aspect('equal',adjustable='datalim');ax.set_box_aspect(1);ax.set_title(name.replace('small-','').replace('large-','').replace('-',' '),fontsize=9)
    ax.set_xlabel('x (m)');ax.set_ylabel('y (m)');ax.grid(alpha=.15)
fig.suptitle('Examples from the synthetic geometry suite; blue = dielectric interfaces')
fig.savefig(P/'figures/geometries.svg');fig.savefig(P/'figures/geometries.png',dpi=160);plt.close(fig)
