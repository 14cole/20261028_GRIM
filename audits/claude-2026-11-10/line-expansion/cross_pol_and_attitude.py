import sys, math, tempfile, importlib, json
sys.path.insert(0,'tools/GHOST')  # run from the repository root of the audited tree
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ghost_backend.assembly.line_expansion import SeamCoefficients
from ghost_backend.data_tools.cem_tools.native_samples import decode_native_samples, raw_amplitude
from ghost_backend.io.grim import _save_grim_npz
wing=importlib.import_module('ghost_backend.assembly.expand_wing_sections')
def coeff(snapshot, frequency, angles, **kw):
    a=np.asarray(angles,float)
    # anisotropic and angle dependent, unequal TM/TE
    return SeamCoefficients(frequency, angles, -4*math.pi*(1+0.3*np.cos(np.radians(a))), 8*math.pi*(1+0.2j*np.sin(np.radians(a))))
def payload(path):
    with np.load(path, allow_pickle=False) as s: return decode_native_samples({k:s[k] for k in s.files})
with tempfile.TemporaryDirectory() as work:
    root=Path(work); geo=root/'section.geo'
    geo.write_text('Title: strip\nSegment: strip\nproperties: 2 10 0 0 0\n-0.01 0 0.01 0\nIBCS_Resistances:\nDielectrics:\n')
    section=dict(geometry=str(geo), root=(0,0,0), tip=(0.2,0.05,0.03), normal=(0,1,1))
    settings=dict(coordinate_units='meters', geometry_units='meters', section_angle_step_deg=30, shadow=False)
    captured=[]
    real=np.einsum
    def spy(sub,*ops,**kw):
        out=real(sub,*ops,**kw)
        if sub=="nai,nab,nbj->nij": captured.append(out.copy())
        return out
    with patch.object(wing,'coefficients_from_2d',side_effect=coeff), patch.object(wing.np,'einsum',side_effect=spy):
        r=wing.expand_wing_sections([section], output_grim=str(root/'a.grim'), frequencies_ghz=[0.3,1.0], azimuths_deg=[0,45,90,200], elevations_deg=[-30,20], **settings)
    radar=np.concatenate(captured)
    asym=np.max(np.abs(radar[:,0,1]-radar[:,1,0]))/np.max(np.abs(radar))
    print('radar-frame matrix asymmetry |S01-S10|/max|S| =', asym, '| max cross-pol', np.max(np.abs(radar[:,0,1]))/np.max(np.abs(radar)))
    base=payload(r['output'])
    amp=raw_amplitude(base)
    # HV-only label
    for labels in (['VV','HH','HV'],['HH','VV','VH']):
        b=dict(base); b['polarizations']=np.array(labels); z=np.zeros_like(amp); b['rcs_amp_real']=z.real; b['rcs_amp_imag']=z.imag; b['rcs_power']=np.zeros(amp.shape); b['rcs_phase']=np.zeros(amp.shape)
        p=root/('b'+''.join(labels)+'.grim'); _save_grim_npz(b,str(p))
        with patch.object(wing,'coefficients_from_2d',side_effect=coeff):
            rr=wing.expand_wing_sections([section], output_grim=str(root/('o'+''.join(labels)+'.grim')), body_grim=str(p), **settings)
        out=raw_amplitude(payload(rr['output'])); want={'VV':amp[...,0],'HH':amp[...,1],'VH':amp[...,2],'HV':amp[...,2]}
        print(labels,'max mismatch vs sections-only by label:',max(float(np.max(np.abs(out[...,i]-want[l]))) for i,l in enumerate(labels)),'| warnings',[w[:60] for w in rr['warnings']])
    # attitude metadata: what does the base loader find, and is anything said?
    from ghost_backend.assembly.fields import load_body_requested_radar_grid
    try: g=load_body_requested_radar_grid(str(root/'a.grim'))
    except Exception as e: g='raised '+type(e).__name__+': '+str(e)[:80]
    print('requested radar grid stored in a sections-only output:', g if not isinstance(g,dict) else {k:g[k] for k in g if 'axis' in k or 'roll' in k})
    keys=[k for k in base if 'axis' in k or 'roll' in k or 'grid' in k or 'attitude' in k]; print('attitude-like keys in output file:',keys)
    with patch.object(wing,'coefficients_from_2d',side_effect=coeff):
        r2=wing.expand_wing_sections([section], output_grim=str(root/'att.grim'), frequencies_ghz=[0.3], azimuths_deg=[0,45], elevations_deg=[20], axis_az_deg=30.0, axis_el_deg=10.0, **settings)
        p2=payload(r2['output']); print('output written with axis_az=30, axis_el=10 -> attitude keys:',[k for k in p2 if 'axis' in k or 'roll' in k or 'grid' in k])
        try: g2=load_body_requested_radar_grid(r2['output'])
        except Exception as e: g2='raised '+type(e).__name__
        print('   reloaded attitude:', g2 if not isinstance(g2,dict) else {k:g2[k] for k in g2 if 'axis' in k or 'roll' in k})
        r3=wing.expand_wing_sections([section], output_grim=str(root/'att2.grim'), body_grim=r2['output'], **settings)
        a2=raw_amplitude(payload(r2['output'])); a3=raw_amplitude(payload(r3['output']))
        print('   re-using that output as a base, second pass adds the same sections: ratio |out|/|base| per sample', np.round(np.abs(a3[...,0]).ravel()/np.abs(a2[...,0]).ravel(),4), '(2.0 = same attitude used)')
