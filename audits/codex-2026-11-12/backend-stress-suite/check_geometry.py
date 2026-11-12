"""Independent radial-polygon checks for the coated-star refusal cases.

For a polygon with strictly increasing angular vertices and angular steps < pi,
each edge occupies its own radial sector, so nonadjacent edges cannot cross.
Checking inner/outer radial order at the union of their vertex rays rules out
an inter-contour crossing: between those rays each contour is a straight edge.
This checks geometry validity, not electromagnetic accuracy or conditioning.
"""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent

def read(name):
    parts=[];points=[]
    for line in (P/'geometries'/(name+'.geo')).read_text().splitlines():
        if line.startswith('Segment:'):
            if points:parts.append(np.array(points));points=[]
        elif len(line.split())==4:
            try:a,b,c,d=map(float,line.split())
            except ValueError:continue
            points.append((a,b))
    if points:parts.append(np.array(points))
    return parts

def radial(points,theta):
    angle=np.unwrap(np.arctan2(-points[:,1],points[:,0]))
    assert abs(angle[0])<1e-12
    steps=np.diff(np.r_[angle,2*np.pi]);assert np.all((steps>0)&(steps<np.pi))
    assert np.all(np.linalg.norm(points,axis=1)>0)
    i=np.searchsorted(angle,theta,side='right')-1;i=np.clip(i,0,len(angle)-1)
    a=points[i];b=points[(i+1)%len(angle)];u=np.column_stack((np.cos(theta),-np.sin(theta)))
    cross=lambda x,y:x[:,0]*y[:,1]-x[:,1]*y[:,0]
    return cross(a,b)/cross(u,b-a)

rows=[]
for name in ('20ft-complex-thin-coating','20ft-complex-coating-thicker','20ft-complex-coating-1GHz'):
    outer,inner=read(name)
    theta=np.unique(np.r_[np.unwrap(np.arctan2(-outer[:,1],outer[:,0])),np.unwrap(np.arctan2(-inner[:,1],inner[:,0]))])
    gap=radial(outer,theta)-radial(inner,theta)
    assert gap.min()>1e-10,name
    rows.append(dict(geometry=name,outer_panels=len(outer),inner_panels=len(inner),simple_star_shaped_polygons=True,
        inner_strictly_contained=True,vertex_ray_min_clearance_m=float(gap.min()),vertex_ray_max_clearance_m=float(gap.max()),
        sha256=hashlib.sha256((P/'geometries'/(name+'.geo')).read_bytes()).hexdigest()))
control=read('20ft-complex-pec-control')[0]
assert np.array_equal(control,read('20ft-complex-thin-coating')[0])
out=dict(check='Angular-sector simplicity and strict radial containment on all vertex rays',
    pec_control_uses_exact_same_outer_polygon=True,rows=rows)
(P/'GEOMETRY_CHECKS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
