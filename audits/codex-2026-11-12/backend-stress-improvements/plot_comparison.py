"""Standalone measured old/new comparison; no forecast bars."""
import json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;old=Path(sys.argv[1]);names=['ladder-pec-8000-compressed','ladder-diel-4000-compressed','ladder-coated-3000-compressed']
fig,axes=plt.subplots(1,2,figsize=(10,4));x=np.arange(3)
for ax,field,title in zip(axes,['wall_seconds','peak_tree_rss_gib'],['Solve time (seconds)','Peak process-tree RSS (GiB)']):
    values=[]
    for directory in (old,P):
        measured=[]
        for name in names:
            r=json.loads((directory/'results'/(name+'.json')).read_text());m=json.loads((directory/'results'/(name+'.monitor.json')).read_text());assert r['error'] is None
            measured.append(r[field] if field in r else m[field])
        values.append(measured)
    for offset,label,color,v in [(-.18,'Previous explicit Compressed','#9aa6b2',values[0]),(.18,'Updated explicit Compressed','#1663a7',values[1])]:
        bars=ax.bar(x+offset,v,.34,label=label,color=color)
        ax.bar_label(bars,fmt='%.2f',fontsize=9,padding=3)
    ax.set_xticks(x,['PEC\n8,000 unknowns','Dielectric\n8,000 unknowns','Coated PEC\n8,100 unknowns']);ax.set_title(title);ax.spines[['top','right']].set_visible(False);ax.set_ylim(0,max(max(v) for v in values)*1.22)
axes[0].legend(fontsize=8);fig.suptitle('Measured medium-system improvement — same meshes, both polarizations')
fig.text(.5,.01,'Linux • 16 GiB host • four allocated CPUs • 8 GiB solve reservation • individual runs',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.05,1,.95]);(P/'figures').mkdir(exist_ok=True)
fig.savefig(P/'figures'/'compressed-comparison.png',dpi=160)
