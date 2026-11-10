"""Minimal real-occluder repro, no Qt, solver, or mocked coefficients."""
import numpy as np
from ghost_backend.assembly.workflow import bor_shadow_triangles
from ghost_backend.geometry.occlusion import Occluder
from ghost_backend.assembly.fields import radar_frame_basis

# Closed cylinder, radius 0.1 m, axial extent [-0.1, 0.1] m.
profile=np.array([[0,.1],[.1,.1],[.1,-.1],[0,-.1]])
triangles,_=bor_shadow_triangles(profile,max_sag_m=299792458/(.3e9)/16,
                               normal_tolerance_deg=2)
direction=radar_frame_basis([0],[20])[0][0]
print('Shadow triangles:',len(triangles),'look:',direction,flush=True)
# Axis-frame line crosses the body's side, as a root-to-tip section can.
print(Occluder(triangles).visible_line_intervals(
    np.array([[0,.05,0]]),np.array([[0,.15,0]]),direction))
