import pathlib,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=pathlib.Path(__file__).parent
radii=[100,10,1,.2,.05,.01];old=[];new=[]
for r in radii:
 p=D/'claude_reference'/'fields';a=np.load(p/f'scale-r{r:g}-dense.npy');b=np.load(p/f'scale-r{r:g}-compressed.npy')
 old.append(np.max(abs(b-a))/np.max(abs(a)))
 a=np.load(D/f'scale-diel-{r:g}-dense.npy');b=np.load(D/f'scale-diel-{r:g}-compressed.npy');new.append(np.max(abs(b-a))/np.max(abs(a)))
fig,ax=plt.subplots(figsize=(9,4.6),layout='constrained')
ax.loglog(1/np.array(radii),old,'o-',label='Baseline compressed (Claude fields)',color='#b45309',lw=2)
ax.loglog(1/np.array(radii),new,'o-',label='Updated hierarchical compressed',color='#0369a1',lw=2)
ax.set(xlabel='Inverse physical radius (1/m), with fixed electrical size',ylabel='Relative maximum complex-field error vs Dense',title='Dielectric scale sensitivity: 4,000 unknowns, both polarizations')
ax.grid(True,which='both',alpha=.18);ax.legend(loc='upper left');ax.text(.99,.03,'Discrete-system comparison; mesh accuracy is a separate check.',transform=ax.transAxes,ha='right',fontsize=9,color='#475569')
fig.savefig(D/'scale_accuracy.png',dpi=160);fig.savefig(D/'scale_accuracy.svg')
