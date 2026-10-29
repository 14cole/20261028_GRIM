"""Compact CSV values, units, reload, and desktop export defaults."""
import csv
import os
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QDialog
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.io.csv import write_flat_csv, has_flat_csv_signature
from GRIM_Backend.io.loaders import load_flat_csv
from GRIM_Backend.io.batch import _stage_and_publish_csv_batch
from GRIM_Backend.ui.dataset_dialogs import ExportCsvDialog
from GRIM_Backend.ui.dataset_actions import DatasetOpsMixin


def source(quantity='sigma_3d'):
    power=np.arange(1.,25.).reshape(2,2,3,2)
    phase=np.linspace(-3.,3.,24).reshape(power.shape)
    return RcsGrid([.1,.3],[-.2,.2],[8.,9.,10.],['V,V','H"H'],
        rcs_power=power,rcs_phase=phase,units={'azimuth':'rad','elevation':'rad','frequency':'GHz',
            'rcs_linear_quantity':quantity,'rcs_log_unit':{'sigma_3d':'dBsm','sigma_2d':'dBke','power_ratio':'dB'}[quantity]},
        extra={'phase_reference':'A long fixed-origin declaration '*10, 'time_convention':'+jwt'})


@pytest.mark.parametrize('quantity,scale,unit',[
    ('sigma_3d','linear','m^2'),('sigma_2d','linear','m'),('power_ratio','linear','1'),
    ('sigma_3d','dbsm','dBsm'),('sigma_2d','dbke','dBke'),('power_ratio','db','dB')])
@pytest.mark.parametrize('delimiter',[',','\t'])
def test_simple_values_units_and_reload(tmp_path,quantity,scale,unit,delimiter):
    grid=source(quantity)
    path=tmp_path/'simple.csv'
    write_flat_csv(grid,path,scale=scale,simple=True,delimiter=delimiter)
    with path.open(newline='',encoding='utf-8') as stream:
        reader=csv.DictReader(stream,delimiter=delimiter);rows=list(reader)
    assert reader.fieldnames[:6]==['polarization','elevation','azimuth','frequency','magnitude','phase']
    assert len(reader.fieldnames)==11 and len(rows)==24
    assert {r['magnitude_unit'] for r in rows}=={unit}
    assert {r['phase_unit'] for r in rows}=={'deg'}
    assert 'phase_reference' not in reader.fieldnames
    for row in rows:
        ia=list(grid.azimuths).index(float(row['azimuth']))
        ie=list(grid.elevations).index(float(row['elevation']))
        jf=list(grid.frequencies).index(float(row['frequency']))
        ip=list(grid.polarizations).index(row['polarization'])
        power=float(grid.power[ia,ie,jf,ip])
        expected=(power if scale=='linear' else 10*np.log10(power*(2*np.pi*grid.frequencies[jf]*1e9/299792458. if scale=='dbke' else 1.)))
        assert float(row['magnitude'])==pytest.approx(expected,abs=1e-12)
        assert float(row['phase'])==pytest.approx(np.degrees(grid.phase[ia,ie,jf,ip]),abs=1e-12)
    assert has_flat_csv_signature(path)
    loaded=load_flat_csv(path)
    np.testing.assert_allclose(loaded.power,grid.power,rtol=1e-12)
    np.testing.assert_allclose(loaded.phase,grid.phase,atol=1e-12)
    assert loaded.linear_quantity()==quantity
    assert loaded.units['frequency']=='GHz' and loaded.units['azimuth']=='rad'


def test_simple_smaller_and_full_format_still_available(tmp_path):
    grid=source();small=tmp_path/'small.csv';full=tmp_path/'full.csv'
    write_flat_csv(grid,small,simple=True)
    write_flat_csv(grid,full,include_phase=True)
    assert small.stat().st_size < full.stat().st_size*.5
    assert 'grim_csv_schema' in full.read_text().splitlines()[0]


def test_unknown_phase_is_blank_and_zero_power_is_preserved(tmp_path):
    grid=RcsGrid([0.],[0.],[9.,10.],['VV'],rcs_power=np.array([0.,4.]).reshape(1,1,2,1),units={'frequency':'GHz'})
    path=tmp_path/'unknown.csv';write_flat_csv(grid,path,simple=True,scale='dbsm')
    with path.open(newline='') as stream:rows=list(csv.DictReader(stream))
    assert [r['phase'] for r in rows]==['','']
    assert rows[0]['magnitude']=='-inf'
    loaded=load_flat_csv(path)
    np.testing.assert_allclose(loaded.power,grid.power)
    assert np.isnan(loaded.phase).all()


def test_simple_failure_keeps_existing_file(tmp_path):
    path=tmp_path/'kept.csv';path.write_text('existing')
    with pytest.raises(ValueError,match='one magnitude column'):
        write_flat_csv(source(),path,simple=True,scale='both')
    assert path.read_text()=='existing'


def test_simple_batch_uses_compact_format(tmp_path):
    paths=[tmp_path/'a.csv',tmp_path/'b.csv']
    _stage_and_publish_csv_batch([(source(),p) for p in paths],scale='linear',include_phase=True,simple=True)
    assert all(p.read_text().startswith('polarization,elevation,azimuth,frequency,magnitude,phase,') for p in paths)


def test_dialog_defaults_and_full_format_controls():
    app=QApplication.instance() or QApplication([])
    dialog=ExportCsvDialog()
    assert dialog.get_options()==('linear',True,True)
    assert not dialog._chk_phase.isEnabled()
    both=dialog._combo_scale.findData('both')
    assert not dialog._combo_scale.model().item(both).isEnabled()
    dialog._chk_simple.setChecked(False)
    dialog._combo_scale.setCurrentIndex(both)
    dialog._chk_phase.setChecked(False)
    assert dialog.get_options()==('both',False,False)
    dialog._chk_simple.setChecked(True)
    assert dialog.get_options()==('linear',True,True)
    dialog.close()


def test_desktop_action_passes_simple_default_to_worker(tmp_path):
    app=QApplication.instance() or QApplication([])
    dialog=ExportCsvDialog()
    owner=SimpleNamespace(_selected_datasets_ordered=lambda **kwargs:[('sample',source())],
        status=SimpleNamespace(showMessage=mock.Mock()),_on_csv_export_progress=lambda *args:None,
        _on_csv_export_finished=lambda *args:None,_try_start_background_job=mock.Mock(return_value=True))
    target=tmp_path/'simple.csv'
    with mock.patch('GRIM_Backend.ui.dataset_actions.ExportCsvDialog',return_value=dialog),\
         mock.patch.object(dialog,'exec',return_value=QDialog.Accepted),\
         mock.patch('GRIM_Backend.ui.dataset_actions.QFileDialog.getSaveFileName',return_value=(str(target),'')):
        DatasetOpsMixin._export_csv_selected(owner)
    worker=owner._try_start_background_job.call_args.args[1]
    assert worker._simple
    worker.run()
    assert target.read_text().startswith('polarization,elevation,azimuth,frequency,magnitude,phase,')
    dialog.close()
