"""Read-only test of existing local material sizing on the repository airfoil."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod.preparation import prepare_geometry
from ghost_backend.twod.geometry import _mesh_wavelength_for_snapshot
from ghost_backend.twod.meshing import segment_wavelengths
from ghost_backend.execution.options import execution_scope
root=Path(sys.argv[1]);g=build_geometry_snapshot(*parse_geometry((root/'airfoil.geo').read_text()))
_,_,materials,_=prepare_geometry(g,units='inches');wavelength=_mesh_wavelength_for_snapshot(g,materials,3.)[0]
with execution_scope(dict(mesh_strategy='local')):
 waves=segment_wavelengths(g,materials,[3.],.0254,wavelength)
print(json.dumps(dict(frequency_ghz=3.,global_wavelength_m=wavelength,all_segments_keep_global_sizing=all(w==wavelength for w in waves),segments=[dict(name=s['name'],local_to_global_ratio=w/wavelength) for s,w in zip(g['segments'],waves)]),indent=2))
