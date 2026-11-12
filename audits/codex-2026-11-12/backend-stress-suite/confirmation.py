"""Independent repeat and complete native-fallback controls. Run last, sequentially."""
import json,sys
from pathlib import Path
from suite import catalog,run,P
from experiments import experiments

def confirmation():
    source={s['case']:s for s in catalog()+experiments()};rows=[]
    def copy(ref,label,**kw):
        s=dict(source[ref]);s.update(case=label,geometry_id=label,group='experiment',reference_case=ref)
        s.update(kw);rows.append(s)
    for stem in ('ladder-pec-8000','ladder-diel-4000','ladder-coated-3000'):
        copy(stem+'-compressed','repeat-'+stem+'-stock')
        copy('experiment-'+stem+'-early-hmatrix','repeat-'+stem+'-early-hmatrix')
    for backend in ('dense','compressed'):
        for stem in ('fallback-small','millimeter-coating','close-dielectric-bodies'):
            ref=('experiment-native-fallback-control-'+backend if stem=='fallback-small' else stem+'-'+backend)
            copy(ref,'full-fallback-'+stem+'-'+backend,fallback=False,full_fallback=True)
    # Diagnose a condition-gate refusal without relaxing the gate.
    for label,changes in [('thicker',dict(inner_ratio=.999)),('1GHz',dict(frequency_ghz=1.))]:
        for backend in ('dense','compressed'):
            copy('20ft-complex-thin-coating-'+backend,'20ft-complex-coating-'+label+'-'+backend,
                group='extension',geometry_id='20ft-complex-coating-'+label,reference_case=None,**changes)
    for backend in ('dense','compressed'):
        copy('20ft-complex-thin-coating-'+backend,'20ft-complex-pec-control-'+backend,
            material='pec',n=6085,group='extension',geometry_id='20ft-complex-pec-control',reference_case=None)
        copy('20ft-complex-thin-coating-'+backend,'20ft-complex-pec-15GHz-'+backend,
            material='pec',frequency_ghz=15.,group='extension',geometry_id='20ft-complex-pec-15GHz',reference_case=None,timeout=480)
    return rows

if __name__=='__main__':
    rows=confirmation();(P/'confirmation-catalog.json').write_text(json.dumps(rows,indent=2)+'\n')
    for s in rows:
        if len(sys.argv)>2 and s['case'] not in sys.argv[2:]:continue
        run(Path(sys.argv[1]).resolve(),s)
