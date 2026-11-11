"""Independent scope checks for Claude's response; production is not edited."""
import importlib
import json
import math
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ghost_backend.assembly.line_expansion import SeamCoefficients
from ghost_backend.assembly.workflow import bor_shadow_triangles
from ghost_backend.assembly.fields import load_body_requested_radar_grid
from ghost_backend.geometry.occlusion import Occluder
from ghost_backend.geometry import line_visibility as lv
from ghost_backend.data_tools.cem_tools.native_samples import decode_native_samples,raw_amplitude
from ghost_backend.io.grim import _save_grim_npz

wing=importlib.import_module('ghost_backend.assembly.expand_wing_sections')
observations={}
def payload(path):
    with np.load(path,allow_pickle=False) as p:
        return decode_native_samples({k:p[k] for k in p.files})
def coeff(snapshot,frequency,angles,**kwargs):
    a=np.deg2rad(angles)
    return SeamCoefficients(frequency,angles,-4*math.pi*(1+.3*np.cos(a)),8*math.pi*(1+.2j*np.sin(a)))
with tempfile.TemporaryDirectory() as work:
    root=Path(work);geo=root/'section.geo'
    geo.write_text('Title: strip\nSegment: strip\nproperties: 2 10 0 0 0\n-.01 0 .01 0\nIBCS_Resistances:\nDielectrics:\n')
    section=dict(geometry=str(geo),root=(0,0,0),tip=(.2,.05,.03),normal=(0,1,1))
    settings=dict(coordinate_units='meters',geometry_units='meters',section_angle_step_deg=30,shadow=False)
    grid=dict(frequencies_ghz=[.3],azimuths_deg=[0,45],elevations_deg=[20])
    def run(name,**kwargs):
        return wing.expand_wing_sections([section],output_grim=str(root/(name+'.grim')),**settings,**kwargs)
    with patch.object(wing,'coefficients_from_2d',side_effect=coeff):
        first=run('nonzero',axis_az_deg=30,axis_el_deg=10,**grid)
        base=payload(first['output']);a=raw_amplitude(base)
        wrong=run('implicit',body_grim=first['output'])
        explicit=run('explicit',body_grim=first['output'],axis_az_deg=30,axis_el_deg=10)
        bad=raw_amplitude(payload(wrong['output']));good=raw_amplitude(payload(explicit['output']))
        assert not np.allclose(bad,2*a) and np.allclose(good,2*a,atol=1e-14)
        observations['attitude']={
            'implicit_VV_ratios':(abs(bad[...,0])/abs(a[...,0])).ravel().tolist(),
            'explicit_VV_ratios':(abs(good[...,0])/abs(a[...,0])).ravel().tolist(),
            'implicit_max_complex_error_relative_to_expected':float(np.max(abs(bad-2*a))/np.max(abs(2*a))),
            'warnings':wrong['warnings'],
            'machine_readable_attitude':load_body_requested_radar_grid(first['output']),
            'history':str(base['history'])}
        zero=run('zero',**grid);zero_plus=run('zero_plus',body_grim=zero['output'])
        assert np.allclose(raw_amplitude(payload(zero_plus['output'])),2*raw_amplitude(payload(zero['output'])),atol=1e-14)
        observations['zero_attitude_chain_doubles']=True
        declared=dict(base)
        declared['requested_radar_grid_json']=json.dumps(dict(schema='ghost.workflow.requested-radar-grid.v1',axis_az_deg=30,axis_el_deg=10,roll_deg=0,**grid))
        declared_path=root/'declared.grim';_save_grim_npz(declared,str(declared_path))
        kept=run('retained',body_grim=str(declared_path))
        assert np.allclose(raw_amplitude(payload(kept['output'])),2*a,atol=1e-14)
        observations['valid_attitude_record_chain_doubles']=True
        declared['requested_radar_grid_json']='{malformed'
        invalid_path=root/'malformed.grim';_save_grim_npz(declared,str(invalid_path))
        malformed=run('malformed_plus',body_grim=str(invalid_path))
        assert np.allclose(raw_amplitude(payload(malformed['output'])),bad,atol=1e-14)
        observations['malformed_record_silently_matches_zero_fallback']=dict(warnings=malformed['warnings'])
        # Confirm symmetry with an actual turning end normal as well.
        twisted=dict(section,normal_end=(0,.5,1))
        captured=[];real_einsum=np.einsum
        def spy(sub,*operands,**kwargs):
            value=real_einsum(sub,*operands,**kwargs)
            if sub=='nai,nab,nbj->nij':captured.append(value.copy())
            return value
        with patch.object(wing.np,'einsum',side_effect=spy):
            wing.expand_wing_sections([twisted],output_grim=str(root/'twist.grim'),**settings,**grid)
        s=np.concatenate(captured);asym=float(np.max(abs(s[:,0,1]-s[:,1,0]))/np.max(abs(s)))
        assert asym<1e-14
        observations['twisted_cross_pol_relative_asymmetry']=asym

profile=np.array([[0,.1],[.1,.1],[.1,-.1],[0,-.1]])
a,_=bor_shadow_triangles(profile,max_sag_m=299792458/.3e9/16,normal_tolerance_deg=2)
b,_=bor_shadow_triangles(profile,max_sag_m=1,normal_tolerance_deg=2)
observations['claude_shadow_tessellations']=dict(triangles_a=len(a),triangles_b=len(b),byte_identical=np.array_equal(a,b))

# Independent analytical cube oracle: no use of Occluder.visible as reference.
v=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],float)
faces=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
tri=v[np.array(faces)]
# Repeat faces to force a multi-leaf BVH while preserving the exact same solid.
multi=np.tile(tri,(30,1,1))
cases=[((-2,0,-2),(2,0,-2),(0,0,1),.5),
       ((-.5,0,-2),(.5,0,-2),(0,0,1),0),
       ((2,0,-2),(3,0,-2),(0,0,1),1),
       ((-2,0,-2),(2,0,-2),(1,0,1),.5),
       ((0,0,-2),(4,0,-2),(1,0,1),1),
       ((-2,0,2),(2,0,2),(0,0,1),1)]
oracle=[];original_union=lv._union
for count,mesh,normalize in [(12,tri,False),(360,multi,False),(360,multi,True)]:
    for start,end,direction,want in cases:
        try:
            with patch.object(lv,'_union',side_effect=(lambda x:original_union([list(t) for t in x])) if normalize else original_union):
                _,lo,hi=Occluder(mesh).visible_line_intervals(np.array([start]),np.array([end]),np.array(direction))
            got=float(np.sum(hi-lo));error=None
        except TypeError as exc:
            got=None;error=str(exc)
        oracle.append(dict(triangles=count,normalization=normalize,start=start,end=end,direction=direction,expected_visible_fraction=want,actual_visible_fraction=got,error=error))
        if count==12 or normalize:
            assert error is None and abs(got-want)<1e-12,oracle[-1]
observations['independent_cube_oracle']=oracle
Path(__file__).with_name('verification-results.json').write_text(json.dumps(observations,indent=2))
print(json.dumps(observations,indent=2))
