"""Real Qt-thread/2-D-solver/GRIM roundtrip, with a PEC-cylinder series oracle."""
import json
import argparse
import math
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from ghost_backend.ui.line_expansion import LineExpansionTab
from ghost_backend.twod import solver
from ghost_backend.validation.cylinder import pec_cylinder_backscatter_amplitude
from ghost_backend.data_tools.cem_tools.native_samples import decode_native_samples, raw_amplitude

parser=argparse.ArgumentParser();parser.add_argument('--angle-step',type=float,default=30)
parser.add_argument('--cancel-after-ms',type=int);parser.add_argument('--report-name',default='real-gui-results.json')
args=parser.parse_args()
app=QApplication([]); tab=LineExpansionTab();tab.show()
records=[]; original=solver.solve_monostatic_rcs_2d_certified
def measured(**kwargs):
    start=time.perf_counter();result=original(**kwargs)
    records.append(dict(seconds=time.perf_counter()-start,
        frequencies=kwargs['frequencies_ghz'],angle_count=len(kwargs['elevations_deg']),
        certified=result['metadata'].get('mesh_convergence_certified'),
        execution_options=result['metadata'].get('execution_options'),
        panel_count=result['metadata'].get('panel_count'),
        abort_event_present=kwargs.get('abort_event') is not None,
        progress_callback_present=kwargs.get('progress_callback') is not None))
    return result
with tempfile.TemporaryDirectory(prefix='line-real-') as work:
    root=Path(work);geo=root/'cylinder.geo';out=root/'real.grim'
    radius=.1;count=128;length=.2;f=.3
    points=[(radius*math.cos(-2*math.pi*i/count),radius*math.sin(-2*math.pi*i/count)) for i in range(count+1)]
    geo.write_text('Title: cylinder\nSegment: circle\nproperties: 2 1 0 0 0\n'+
        '\n'.join(' '.join(map(str,(*a,*b))) for a,b in zip(points,points[1:]))+'\nIBCS_Resistances:\nDielectrics:\n')
    tab._append_row([str(geo),'0','0','0',str(length),'0','0','0','0','1','','',''])
    for control in (tab.coordinate_units,tab.geometry_units):
        control.setCurrentIndex(control.findData('meters'))
    tab.grid_fields['frequencies_ghz'].setText(str(f))
    tab.grid_fields['azimuths_deg'].setText('0,30,60')
    tab.grid_fields['elevations_deg'].setText('30')
    tab.angle_step.setValue(args.angle_step);tab.output_edit.setText(str(out))
    exported=[];tab.files_exported.connect(lambda paths,source:exported.append((paths,source)))
    loop=QEventLoop();timer=QTimer();timer.setInterval(20)
    timer.timeout.connect(lambda: loop.quit() if not tab.job_is_running() else None)
    start=time.perf_counter()
    cancellation=[]
    def cancel():
        cancellation.append(time.perf_counter()-start);tab.cancel_button.click()
    with patch.object(solver,'solve_monostatic_rcs_2d_certified',side_effect=measured):
        tab.run_button.click()
        locked=not tab.run_button.isEnabled() and not tab.section_table.isEnabled()
        if args.cancel_after_ms is not None:
            QTimer.singleShot(args.cancel_after_ms,cancel)
        timer.start();loop.exec();timer.stop()
    elapsed=time.perf_counter()-start
    if args.cancel_after_ms is not None:
        assert cancellation and not out.exists() and not exported and not tab.job_is_running()
        report=dict(total_seconds=elapsed,cancel_requested_seconds=cancellation[0],
                    cancel_to_idle_seconds=elapsed-cancellation[0],section_solves=records,
                    output_exists=out.exists(),status=tab.status_label.text())
        Path(__file__).with_name(args.report_name).write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2),flush=True)
        raise SystemExit(0)
    assert out.is_file(),tab.status_label.text()
    assert exported and not tab.job_is_running() and tab.run_button.isEnabled()
    with np.load(out,allow_pickle=False) as stored:
        data=decode_native_samples({k:stored[k] for k in stored.files})
    field=raw_amplitude(data)
    expected=np.array([pec_cylinder_backscatter_amplitude(radius,f*1e9,'TE'),
                       -pec_cylinder_backscatter_amplitude(radius,f*1e9,'TM')])*length/(4*math.pi)
    actual=field[0,0,0,:2]
    relative=abs(actual-expected)/abs(expected)
    assert np.max(relative)<.002,relative
    report=dict(gui_end_to_end_seconds=elapsed,section_solves=records,
        inputs_locked_during_worker=locked,controls_restored=True,export_signal_count=len(exported),
        shape=list(field.shape),finite=bool(np.all(np.isfinite(field))),
        broadside_complex_relative_error_VV_HH=relative.tolist(),
        status=tab.status_label.text(),provenance_saved='line_expansion_provenance_json' in data)
    Path(__file__).with_name(args.report_name).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)
