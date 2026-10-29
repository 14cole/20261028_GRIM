"""Independent release audit regressions, beyond existing feature tests."""
import csv
import json
import numpy as np
import pytest
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.result_storage import select_result
from GRIM_Backend.io.csv import write_flat_csv
from GRIM_Backend.io.loaders import load_flat_csv
from GRIM_Backend.assembly.values import FeatureAssemblyValues, LEGACY_LINE_RESPONSE_DEFAULTS
from GRIM_Backend.assembly.recipe import read_feature_assembly_recipe, write_feature_assembly_recipe


@pytest.mark.parametrize('rows', [1, 3])
@pytest.mark.parametrize('selection', [slice(None,None,-1), slice(0,None,-1), slice(0,1,-1)])
def test_mixed_reverse_and_advanced_selection_matches_numpy(rows, selection):
    array = np.arange(rows*6).reshape(rows,6)
    key = selection, np.array([0,2,4])
    np.testing.assert_array_equal(select_result(array,key), array[key])


@pytest.mark.parametrize('delimiter', [',','\t'])
def test_csv_multiline_metadata_survives_export_import(tmp_path, delimiter):
    reference = 'origin at x=0\nsecond line, with "quotes"\rand CR'
    grid = RcsGrid([0,90], [0], [3], ['VV'], rcs=np.array([1+2j,3-4j]).reshape(2,1,1,1),
                   units={'frequency':'GHz'}, extra={'phase_reference':reference})
    path = tmp_path/'multiline.csv'
    write_flat_csv(grid,path,delimiter=delimiter,include_phase=True)
    with path.open(newline='',encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream,delimiter=delimiter))
    assert len(rows) == 2
    assert all(row['phase_reference'] == reference for row in rows)
    restored = load_flat_csv(path)
    np.testing.assert_allclose(restored.rcs, grid.rcs, atol=1e-14)
    assert restored.extra['phase_reference'] == reference


@pytest.mark.parametrize('version',[5,6])
def test_old_recipe_implicit_and_explicit_phases_are_preserved(tmp_path,version):
    values = FeatureAssemblyValues(line_datasets={'implicit':'a.grim','explicit':'b.grim'},
        line_response_settings={'explicit':{'psi_tm_deg':23.,'psi_te_deg':-7.,'grazing_taper_deg':0.}})
    path = write_feature_assembly_recipe(values,tmp_path/'recipe',name='old',variant='phase')
    payload=json.loads(path.read_text())
    payload['version']=version
    path.write_text(json.dumps(payload))
    old=read_feature_assembly_recipe(path)
    assert old.values.line_response_settings['implicit'] == LEGACY_LINE_RESPONSE_DEFAULTS
    assert old.values.line_response_settings['explicit'] == values.line_response_settings['explicit']
    assert any('Historical line phase' in item for item in old.source_warnings)


@pytest.mark.parametrize('power_only',[False,True])
def test_range_calibration_accepts_known_zero_dut(power_only):
    from GRIM_Backend.tests.test_range_calibration import _grid
    dut = _grid(0j)
    if power_only:
        dut = RcsGrid(dut.azimuths,dut.elevations,dut.frequencies,dut.polarizations,
                      rcs_power=np.zeros(dut.shape),units=dut.units)
    result = dut.range_calibrate(_grid(2+1j),_grid(3-2j),.12)
    np.testing.assert_array_equal(result.rcs,np.zeros(dut.shape,complex))


def test_release_inventory_excludes_audit_documents(tmp_path):
    from GRIM_Backend.release_validation import source_inventory
    for directory in ('GRIM_Backend','tools/GHOST','tools/FREDDY'):
        folder=tmp_path/directory
        folder.mkdir(parents=True)
        (folder/'README.md').write_text('product')
        (folder/'AUDIT_FIXES.md').write_text('local audit')
    assert all('AUDIT' not in item['path'] for item in source_inventory(tmp_path))
