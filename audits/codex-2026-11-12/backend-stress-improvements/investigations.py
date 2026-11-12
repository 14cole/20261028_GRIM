"""Run after suite.py; production qualification and explicitly marked research."""
import json,sys
from pathlib import Path
from suite import catalog,run,P

def catalog_extra():
    source={s['case']:s for s in catalog()};rows=[]
    def variant(ref,label,**kw):
        s=dict(source[ref],case=label,geometry_id=label,reference_case=ref,group='qualification')
        s.update(kw)
        if s['case'].endswith('-'+s['backend']):s['geometry_id']=s['case'][:-len(s['backend'])-1]
        rows.append(s)
    for degree in (2,3):
        for backend in ('dense','compressed'):
            variant('small-dielectric-'+backend,f'dielectric-P{degree}-'+backend,degree=degree)
    for cap in (1.8,):
        for backend in ('dense','automatic'):
            variant('ladder-diel-4000-dense',f'ownership-8000-{cap}-{backend}',cap=cap,backend=backend)
    variant('ladder-diel-4000-dense','ownership-8000-2.3-automatic',cap=2.3,backend='automatic')
    variant('ladder-diel-4000-dense','ownership-8000-2.3-disk-automatic',cap=2.3,backend='automatic',storage='disk')
    variant('ladder-diel-8000-dense','ownership-16000-4.8-dense',cap=4.8,options=dict(assembly_tile=128))
    variant('ladder-diel-8000-dense','ownership-16000-matched-reference',options=dict(assembly_tile=128))
    variant('ladder-diel-4000-dense','ownership-8000-memory-refusal',cap=1.8,storage='memory')
    for backend in ('dense','compressed'):
        for stem in ('small-pec','small-dielectric','small-coated'):
            variant(stem+'-'+backend,'full-fallback-'+stem+'-'+backend,full_fallback=True)
    for material,n in (('pec',1200),('diel',600),('coated',400)):
        for disabled in (False,True):
            name='fallback-h-'+material+('-disabled' if disabled else '-native')
            rows.append(dict(case=name,geometry_id=name,group='qualification',backend='compressed',
                material=material,shape='circle',n=n,length_m=.5,frequency_ghz=2.,full_fallback=disabled,
                reference_case='fallback-h-'+material+'-native' if disabled else None))
    for backend in ('dense','compressed'):
        for stem in ('small-coated','large-star-coated'):
            variant(stem+'-'+backend,'research-balance-'+stem+'-'+backend,research_balance=True,group='research')
        rows.append(dict(case='research-balance-20ft-star-'+backend,geometry_id='research-balance-20ft-star',group='research',backend=backend,
            material='coated',shape='star',length_m=6.096,frequency_ghz=2.,inner_ratio=.99967,timeout=360,research_balance=True))
    for loss in ('lossless','moderate-loss','high-loss'):
        variant('material-'+loss+'-compressed','research-loss-span-'+loss,research_loss_span=True,group='research')
    for backend in ('dense','compressed'):
        rows.append(dict(case='magnetic-thin-'+backend,geometry_id='magnetic-thin',group='qualification',backend=backend,
            material='pec',shape='circle',n=600,length_m=.3,frequency_ghz=2.,magnetic_thin_layer=True))
    for forced in (False,True):
        rows.append(dict(case='forced-h-fallback-'+str(forced),geometry_id='forced-h-fallback-'+str(forced),group='qualification',backend='compressed',
            material='pec',shape='circle',n=1200,length_m=.3,frequency_ghz=2.,force_hmatrix_rejection=forced,
            reference_case='forced-h-fallback-False' if forced else None))
    # Geometry-only loss hypothesis: any admission remains bounded by live
    # allocation checks, strict numerical gates and the independent watchdog.
    variant('20ft-diel-10GHz-compressed','research-loss-span-20ft-diel-10GHz',research_loss_span=True,group='research',cap=12.,timeout=600)
    rows.append(dict(case='diagnostic-unbalanced-20ft-star-TM-dense',geometry_id='diagnostic-unbalanced-20ft-star-TM',group='research',backend='dense',
        material='coated',shape='star',length_m=6.096,frequency_ghz=2.,inner_ratio=.99967,timeout=240,polarization='TM'))
    for stem in ('small-coated','large-star-coated'):
        variant(stem+'-dense','research-scaled-lu-'+stem+'-dense',research_balance=True,research_scaled_lu=True,group='research')
    rows.append(dict(case='research-scaled-lu-20ft-star-dense',geometry_id='research-scaled-lu-20ft-star',group='research',backend='dense',
        material='coated',shape='star',length_m=6.096,frequency_ghz=2.,inner_ratio=.99967,timeout=360,research_balance=True,research_scaled_lu=True,
        reference_case='research-balance-20ft-star-compressed'))
    return rows

if __name__=='__main__':
    rows=catalog_extra();(P/'investigation-catalog.json').write_text(json.dumps(rows,indent=2)+'\n')
    for s in rows:
        if len(sys.argv)>2 and s['case'] not in sys.argv[2:] and s['group'] not in sys.argv[2:]:continue
        run(Path(sys.argv[1]).resolve(),s)
