"""Targeted follow-ups to the baseline suite; no production file edits.

Run after suite.py. Each experiment records its reference case and overrides.
"""
import json,sys
from pathlib import Path
from suite import catalog,run,P

def experiments():
    baseline={x['case']:x for x in catalog()};rows=[]
    def variant(reference,label,**changes):
        s=dict(baseline[reference]);s.update(case='experiment-'+label,geometry_id='experiment-'+label,
            group='experiment',reference_case=reference)
        s.update(changes);rows.append(s)
    for stem in ('ladder-pec-8000','ladder-diel-4000','ladder-coated-3000'):
        variant(stem+'-dense',stem+'-disk',storage='disk')
        variant(stem+'-compressed',stem+'-early-hmatrix',env={'GHOST_HMATRIX_MIN_UNKNOWNS':'1024'})
    for stem in ('ladder-pec-2000','ladder-diel-1000','ladder-coated-1000','small-star-coated'):
        variant(stem+'-compressed',stem+'-early-hmatrix',env={'GHOST_HMATRIX_MIN_UNKNOWNS':'1024'})
    for backend in ('dense','compressed'):
        variant('fallback-small-'+backend,'native-fallback-control-'+backend,fallback=False)
    for leaf in (64,256):
        variant('ladder-pec-16000-compressed','pec16000-leaf'+str(leaf),research_leaf=leaf)
    variant('ladder-diel-8000-dense','diel16000-tile128-reference',options=dict(assembly_tile=128))
    variant('ladder-diel-8000-dense','diel16000-4.8GiB-stock',options=dict(assembly_tile=128),cap=4.8)
    variant('ladder-diel-8000-dense','diel16000-4.8GiB-prototype',options=dict(assembly_tile=128),cap=4.8,research_forecast=True,
        reference_case='experiment-diel16000-tile128-reference')
    for backend in ('dense','compressed'):
        variant('ladder-pec-8000-'+backend,'pec8000-181angles-'+backend,angles=181,
            env={'GHOST_HMATRIX_MIN_UNKNOWNS':'1024'} if backend=='compressed' else {})
    # Genuine thin-gap and full-size complex geometry extensions.
    for material,shape,length,ratio,label in (
        ('coated','circle',1.,.999,'millimeter-coating'),
        ('coated','star',6.096,.99967,'20ft-complex-thin-coating')):
        for backend in ('dense','compressed'):
            rows.append(dict(case=label+'-'+backend,geometry_id=label,group='extension',backend=backend,
                material=material,shape=shape,length_m=length,frequency_ghz=2.,inner_ratio=ratio,timeout=300))
    for material,shape,label in [('diel','comb','small-dielectric-comb'),('pec','double_circle','close-pec-bodies'),('diel','double_circle','close-dielectric-bodies')]:
        for backend in ('dense','compressed'):
            rows.append(dict(case=label+'-'+backend,geometry_id=label,group='extension',backend=backend,
                material=material,shape=shape,length_m=.25,frequency_ghz=2.,gap_m=.001,timeout=180))
    for length,certified,label in ((.2,False,'partial-coating-small'),(1.,False,'partial-coating-large'),(.2,True,'partial-coating-certified')):
        for backend in ('dense','compressed'):
            rows.append(dict(case=label+'-'+backend,geometry_id=label,group='extension',backend=backend,
                material='coated',shape='partial',length_m=length,frequency_ghz=2.,eps=[3.,-.1],certified=certified,timeout=240))
    return rows

if __name__=='__main__':
    (P/'results').mkdir(exist_ok=True);(P/'geometries').mkdir(exist_ok=True)
    rows=experiments();(P/'experiment-catalog.json').write_text(json.dumps(rows,indent=2)+'\n')
    for row in rows:
        if len(sys.argv)>2 and row['case'] not in sys.argv[2:]:continue
        run(Path(sys.argv[1]).resolve(),row)
