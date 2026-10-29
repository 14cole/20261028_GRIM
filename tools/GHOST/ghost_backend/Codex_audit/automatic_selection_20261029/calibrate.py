"""Offline held-out-family assessment; never modifies admission or policy constants."""
import json
import math
from pathlib import Path
import statistics
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=HERE.parent/'solver_studies_20261029/runs'
sys.path.insert(0,str(ROOT.parent))
from ghost_backend.execution.policy import relative_cost

def read(path):return json.loads(path.read_text())
def meta(name):return read(OLD/name/'metadata.json')

groups=[('ordinary_metal','metal15_r0_adaptive',
         [f'metal15_r{r}_dense' for r in range(3)],[f'metal15_r{r}_compressed' for r in range(3)]),
        ('narrow_metal','narrow15_r0_adaptive',
         [f'narrow15_r{r}_dense' for r in range(2)],[f'narrow15_r{r}_compressed' for r in range(2)]),
        ('moderate_dielectric','capacity_inlet_dielectric_15ghz',
         ['capacity_inlet_dielectric_15ghz'],['dielectric15_compressed_probe'])]
rows=[]
for family,selection_name,dense_names,compressed_names in groups:
    source=meta(selection_name)
    for i,step in enumerate(source['adaptive_mesh']['steps']):
        selection=step['backend_selection']
        meshes=selection.get('meshes',source['backend_selection']['meshes'])
        meshes=[r for r in meshes if r['polynomial_degree']==step['polynomial_degree'] and
                r['resources']['nodes']==step['nodes']]
        assert len(meshes)==2,(family,i)
        costs={m:sum(relative_cost(r['resources'],361,m,4,4) for r in meshes) for m in ('dense','compressed')}
        measured={}
        for mode,names in [('dense',dense_names),('compressed',compressed_names)]:
            values=[]
            for name in names:
                actual=meta(name)['adaptive_mesh']['steps'][i]
                assert (actual['nodes'],actual['panels'],actual['polynomial_degree'])==(
                    step['nodes'],step['panels'],step['polynomial_degree'])
                values.append(actual['seconds'])
            measured[mode]=statistics.median(values)
        rows.append(dict(family=family,step=i+1,unknowns=meshes[0]['unknowns'],
            budget_gib=read(OLD/dense_names[0]/'case.json').get('ram',24),
            prior_costs=costs,median_seconds=measured,
            repeats=dict(dense=len(dense_names),compressed=len(compressed_names)),
            prior_ratio=costs['dense']/costs['compressed'],
            measured_ratio=measured['dense']/measured['compressed']))

# A deliberately simple baseline: fit one positive seconds-per-work-unit
# multiplier per backend on the other geometry/material families. Repetitions
# are collapsed first so they cannot leak into validation or overweight a mesh.
folds=[]
for family,_,_,_ in groups:
    train=[r for r in rows if r['family']!=family]
    held=[r for r in rows if r['family']==family]
    scales={m:statistics.median(r['median_seconds'][m]/r['prior_costs'][m] for r in train)
            for m in ('dense','compressed')}
    evaluated=[]
    for row in held:
        predicted={m:row['prior_costs'][m]*scales[m] for m in scales}
        ratio=predicted['dense']/predicted['compressed']
        measured=row['measured_ratio']
        evaluated.append(dict(step=row['step'],predicted_seconds=predicted,
            calibrated_ratio=ratio,measured_ratio=measured,
            ratio_error_factor=max(ratio/measured,measured/ratio),
            winner_correct=(ratio<=1)==(measured<=1)))
    folds.append(dict(held_out_family=family,training_scales=scales,results=evaluated))
report=dict(scope='Offline baseline calibration on historical pure-backend steps; no deployed model change.',
    samples=rows,held_out_families=folds,
    limits=['Only three geometry/material families; material timings are single pairs.',
            'Budgets are recorded, not pooled as identical allocation regimes.',
            'Stage reuse, inverse hints and optional copies are not represented by this scalar baseline.',
            'A whole family is held out; repetitions of its meshes are never used for training.',
            'Predicting initial meshes separately requires repricing their resources, not reusing aggregate costs.'],
    production_prior_changed=False,ram_admission_changed=False)
(HERE/'calibration.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(rows=len(rows),folds=[dict(family=f['held_out_family'],
    correct=sum(r['winner_correct'] for r in f['results']),total=len(f['results']),
    max_ratio_error=max(r['ratio_error_factor'] for r in f['results'])) for f in folds]),indent=2))
