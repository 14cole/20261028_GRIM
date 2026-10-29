"""Native RCS scores and generic displayed-trace diagnostics stay distinct."""
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QApplication, QWidget

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.plotting.engineering_tools import linear_power_summary, measure_trace
from GRIM_Backend.plotting.markers import PlotMarkersMixin
from GRIM_Backend.ui.engineering_analysis import EngineeringAnalysisDialog
from GRIM_Backend.ui.inline_engineering_analysis import InlineEngineeringAnalysis


def power_grid(power, *, quantity="sigma_3d", log_unit="dBsm", frequencies=None):
    return RcsGrid([0.], [0.], np.arange(1., len(power)+1.) if frequencies is None else frequencies,
                   ["HH"], rcs_power=np.asarray(power, float).reshape(1, 1, -1, 1),
                   units={"azimuth":"deg", "elevation":"deg", "frequency":"GHz",
                          "rcs_linear_quantity":quantity, "rcs_log_unit":log_unit})


@pytest.mark.parametrize("quantity,unit", [("sigma_3d","m²"),("sigma_2d","m"),("power_ratio","dimensionless")])
def test_native_power_summary_keeps_zero_masks_invalid_and_respects_region(quantity, unit):
    cut=SimpleNamespace(x=np.array([0.,1.,2.,3.,4.,np.nan]),
                        power=np.array([0.,1.,100.,np.nan,-1.,np.inf]), linear_quantity=quantity)
    full=linear_power_summary(cut)
    assert full==dict(selected_count=5, valid_count=3, unit=unit, mean=101./3., median=1.)
    assert linear_power_summary(cut,region=(1.,0.))==dict(
        selected_count=2, valid_count=2, unit=unit, mean=.5, median=.5)
    assert linear_power_summary(cut,region=(3.,4.))==dict(selected_count=2, valid_count=0, unit=unit)
    assert linear_power_summary(cut,region=(10.,20.))==dict(selected_count=0, valid_count=0, unit=unit)
    # The shared arbitrary-ordinate measurement retains arithmetic dB/phase statistics.
    generic=measure_trace([0.,1.], [0.,20.])
    assert (generic["mean"],generic["median"],generic["std"])==(10.,10.,10.)


class MeasurementOwner(QWidget):
    _marker_arrays=staticmethod(PlotMarkersMixin._marker_arrays)

    def __init__(self, dataset):
        super().__init__()
        self.active_dataset=dataset
        self.plot_figure=Figure()
        self.plot_canvas=FigureCanvasQTAgg(self.plot_figure)
        self.plot_ax=self.plot_figure.add_subplot(111)
        self.lines=[]
        self.markers=[]

    def _selected_datasets(self): return [("Run",self.active_dataset)]
    def _marker_lines(self): return self.lines
    def _add_plot_marker(self,line,index): self.markers.append((line,index))


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=["dialog","inline"])
def panel_factory(application, request):
    opened=[]

    def make(dataset):
        owner=MeasurementOwner(dataset)
        if request.param=="dialog":
            panel=EngineeringAnalysisDialog(owner)
        else:
            panel=InlineEngineeringAnalysis(owner)
            panel.open_tool("measure")
        opened.append((owner,panel))
        return owner,panel

    yield make
    for owner,panel in opened:
        panel.close()
        owner.plot_canvas.close()
        owner.close()
    application.processEvents()


def table_rows(panel):
    return {row[0]:row[1:] for row in panel._panels["measure"][2].rows}


def test_native_measurement_both_uis_show_power_scores_with_zero_and_region(panel_factory):
    _owner,panel=panel_factory(power_grid([0.,1.,100.,np.nan]))
    rows=table_rows(panel)
    assert float(rows["Mean (linear power)"][0])==pytest.approx(101./3.)
    assert rows["Median (linear power)"]==["1","m²"]
    assert rows["Valid power / selected samples"][0]=="3 / 4"
    assert rows["Finite displayed / selected samples"][0]=="2 / 4"
    assert rows["Displayed standard deviation"]==["10","displayed dBsm"]
    assert rows["Displayed peak to peak"]==["20","displayed dBsm"]
    assert "Mean" not in rows and "Median" not in rows
    assert "including zero" in panel._panels["measure"][3].text()
    measured=panel._measurement[2]
    assert measured["peak"]["y"]==20.
    assert measured["power_summary"]["median"]==1.

    panel._select_region(1.,2.)
    rows=table_rows(panel)
    assert rows["Mean (linear power)"]==["0.5","m²"]
    assert rows["Median (linear power)"]==["0.5","m²"]
    assert rows["Valid power / selected samples"][0]=="2 / 2"
    if isinstance(panel,InlineEngineeringAnalysis):
        assert "2 power samples" in panel.summary.text()
        assert "Mean power 0.5 m²" in panel.summary.text()
        assert "Median power 0.5 m²" in panel.summary.text()


@pytest.mark.parametrize("quantity,log_unit,unit", [("sigma_2d","dBke","m"),("power_ratio","dB","dimensionless")])
def test_native_measurement_width_and_ratio_keep_physical_units(panel_factory, quantity, log_unit, unit):
    _owner,panel=panel_factory(power_grid([100.,1.],quantity=quantity,log_unit=log_unit,frequencies=[1.,10.]))
    rows=table_rows(panel)
    assert rows["Mean (linear power)"]==["50.5",unit]
    assert rows["Median (linear power)"]==["50.5",unit]
    assert panel._measurement[2]["power_summary"]["valid_count"]==2


@pytest.mark.parametrize("ylabel", ["Phase (deg)","RCS (dBsm)"])
def test_current_trace_keeps_displayed_statistics_and_peak_markers(panel_factory, ylabel):
    owner,panel=panel_factory(power_grid([1.,100.]))
    axes=owner.plot_figure.axes[0]
    axes.set(xlabel="Azimuth (deg)",ylabel=ylabel)
    line,=axes.plot([0.,1.,2.],[-20.,0.,20.],label="Displayed trace")
    owner.lines=[line]
    if isinstance(panel,InlineEngineeringAnalysis):
        panel._prefer_native_source=False
    panel.refresh_sources()
    panel.trace_combo.setCurrentIndex(1)
    panel._update_current()
    result=panel._measurement[2]
    assert "power_summary" not in result
    assert result["mean"]==0. and result["median"]==0.
    assert result["std"]==pytest.approx(np.std([-20.,0.,20.]))
    rows=table_rows(panel)
    assert rows["Mean"]==["0",f"displayed {ylabel}"]
    assert rows["Median"]==["0",f"displayed {ylabel}"]
    assert "Mean (linear power)" not in rows
    panel._mark_measurement("peak")
    assert owner.markers[-1]==(line,2)
