import pathlib,json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=pathlib.Path(__file__).parent
r=json.loads((D/'SUMMARY.json').read_text());fig,ax=plt.subplots(1,3,figsize=(13,4.2),layout='constrained');colors=['#3b5974','#d07327']
for j,engine in enumerate(['native','cached']):
 data=next(x for x in r['galerkin'] if x['name']==f'gal-large-{engine}-16000-15')
 values=[np.mean(next(z for z in data['results'] if z['operator']==op)['product_seconds']) for op in ['S','W']]
 ax[0].bar(np.arange(2)+(j-.5)*.32,values,width=.32,label={'native':'Native wrapper','cached':'Reusable plan'}[engine],color=colors[j]);ax[1].bar(j,max(z['peak_before_reference_gib'] for z in data['results']),color=colors[j]);ax[1].text(j,max(z['peak_before_reference_gib'] for z in data['results']),f" setup {data['setup_seconds']:.0f}s",ha='center',va='bottom',fontsize=9)
ax[0].set(xticks=[0,1],xticklabels=['S product','W product'],ylabel='Seconds / one-vector product',title='16,000 P1 nodes, 15 GHz');ax[0].legend(fontsize=8)
ax[1].set(xticks=[0,1],xticklabels=['Native wrapper','Reusable plan'],ylabel='Process high-water RSS (GiB)',title='Peak before reference assembly');ax[1].set_ylim(0,ax[1].get_ylim()[1]*1.15)
for sep in [1,2]:
 points=[next(x for x in r['points'] if x['name']==f'point-d{d}-s{sep}')['point_relative_error'] for d in [8,10,12,14]];ax[2].semilogy([8,10,12,14],points,'o-',label=f'Near separation {sep}')
ax[2].set(xticks=[8,10,12,14],xlabel='Requested expansion digits',ylabel='Sampled relative maximum error',title='Point accuracy: 4,000 points, k=60');ax[2].legend(fontsize=8);ax[2].grid(alpha=.2)
fig.suptitle('FMM research: repeated products, setup memory, and accuracy',fontsize=13);fig.savefig(D/'followup-results.png',dpi=180);fig.savefig(D/'followup-results.svg')
