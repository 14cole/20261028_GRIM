import json,pathlib,os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=pathlib.Path(__file__).parent
OUT=pathlib.Path(os.environ.get('GRIM_ROOT','/workspace/grim-fmm-study'))/'audits/codex-2026-11-13/solver-methods-research'
f=json.loads((D/'FMM_ANALYSIS.json').read_text());fig,axes=plt.subplots(1,2,figsize=(11,4.4))
for freq,color in [(2,'#2563eb'),(15,'#c2410c')]:
 rows=sorted([r for r in f['points'] if r['ghz']==freq and r['rhs']==1],key=lambda r:r['n'])
 axes[0].loglog([r['n'] for r in rows],[r['seconds'] for r in rows],'-o',color=color,label=f'{freq} GHz')
 for kind,style in [('S','-'),('W','--')]:
  rows=sorted([r for r in f['galerkin'] if r['ghz']==freq],key=lambda r:r['n']);ys=[next(q['apply_peak_rss_gib'] for q in r['results'] if q['operator']==kind) for r in rows]
  axes[1].plot([r['n'] for r in rows],ys,style+'o',color=color,label=f'{kind}, {freq} GHz')
axes[1].plot([4000,16000],[16*4000**2/2**30,16*16000**2/2**30],':',color='#525252',label='One dense operator: 16 N² bytes')
axes[0].set(xlabel='Point sources (not solver unknowns)',ylabel='Seconds',title='Native FMM point product, one strength vector')
axes[1].set(xlabel='P1 Galerkin nodes',ylabel='GiB',title='Process peak through product; references assembled later')
for ax in axes:ax.grid(True,alpha=.2);ax.legend(fontsize=8)
fig.suptitle('Research measurements: operator products, not complete scattering solves',fontsize=12)
fig.tight_layout();fig.savefig(OUT/'solver_methods.svg');plt.close(fig)
