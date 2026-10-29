"""Optional tool workspaces initialize on use without changing host contracts."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QLabel, QTabWidget, QWidget

from GRIM_Backend.integrations import ghost, freddy
from GRIM_Backend.tests.test_freddy_integration import _FakeImpedanceGui
from GRIM_Backend.ui.app import BLUE_PALETTE


class _GhostWorkspace(QWidget):
    files_exported = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.solver_tab = SimpleNamespace(apply_plot_theme=mock.Mock())
        self.geometry_tab = SimpleNamespace(apply_plot_theme=mock.Mock())
        self.current = None
        self.attachments = []

    def solve_is_running(self):
        return False

    def setCurrentWidget(self, tab):
        self.current = tab

    def attach_material_artifact(self, kind, path):
        self.attachments.append((kind, path))
        return True


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('kind', ['ghost', 'freddy'])
def test_lazy_tools_wait_for_tab_selection_and_keep_latest_palette(app, kind):
    module, factory, widget_class, workspace_class = (
        (ghost, '_load_workspace_class', ghost.GhostIntegrationWidget, _GhostWorkspace)
        if kind == 'ghost' else
        (freddy, '_load_impedance_gui_class', freddy.FreddyIntegrationWidget, _FakeImpedanceGui))
    with mock.patch.object(module, factory, return_value=workspace_class) as load:
        host = QTabWidget()
        host.addTab(QWidget(), 'Plotting')
        widget = widget_class(host, lazy=True)
        host.addTab(widget, kind)
        widget.apply_application_palette(BLUE_PALETTE)
        palette = dict(BLUE_PALETTE, panel_bg='#112233')
        widget.apply_application_palette(palette)
        assert widget.workspace is None
        assert not (widget.solve_is_running() if kind == 'ghost' else widget.job_is_running())
        host.show()
        app.processEvents()
        load.assert_not_called()
        host.setCurrentWidget(widget)
        app.processEvents()
        load.assert_called_once()
        assert widget.workspace is not None
        if kind == 'ghost':
            widget.workspace.geometry_tab.apply_plot_theme.assert_called_once_with(
                background='#112233', text=str(palette['text']), grid=str(palette['grid']))
        else:
            assert widget.workspace.host_themes[-1]['panel_bg'] == '#112233'
        host.setCurrentIndex(0)
        host.setCurrentWidget(widget)
        app.processEvents()
        load.assert_called_once()
        host.close()
        host.deleteLater()
        app.processEvents()


def test_ghost_attachment_loads_hidden_workspace_and_forwarded_signal_stays_connected(app):
    with mock.patch.object(ghost, '_load_workspace_class', return_value=_GhostWorkspace):
        widget = ghost.GhostIntegrationWidget(lazy=True)
        exported = []
        widget.files_exported.connect(lambda paths, solver: exported.append((paths, solver)))
        assert widget.attach_material_artifact('ibc', 'material.csv')
        assert widget.workspace.attachments == [('ibc', 'material.csv')]
        widget.workspace.files_exported.emit(['result.grim'], 'solver')
        assert exported == [(['result.grim'], 'solver')]
        widget.close()
        widget.deleteLater()


def test_freddy_focus_loads_hidden_workspace_and_artifact_signal_remains_available(app, tmp_path):
    path = tmp_path / 'material.csv'
    path.write_text('material')
    with mock.patch.object(freddy, '_load_impedance_gui_class', return_value=_FakeImpedanceGui):
        widget = freddy.FreddyIntegrationWidget(lazy=True)
        requested = []
        widget.attach_to_ghost_requested.connect(lambda kind, value: requested.append((kind, value)))
        widget.focus_workspace()
        assert widget.workspace.focus_probe.called
        widget.workspace.nominal_artifact_exported.emit('ibc', str(path))
        widget._request_attach_to_ghost()
        assert requested == [('ibc', str(path))]
        widget.close()
        widget.deleteLater()


@pytest.mark.parametrize('kind', ['ghost', 'freddy'])
def test_failed_optional_tool_shows_error_once_when_opened(app, kind):
    module, factory, widget_class = (
        (ghost, '_load_workspace_class', ghost.GhostIntegrationWidget)
        if kind == 'ghost' else
        (freddy, '_load_impedance_gui_class', freddy.FreddyIntegrationWidget))
    with mock.patch.object(module, factory, side_effect=ImportError('missing tool')) as load:
        widget = widget_class(lazy=True)
        assert not widget.load_error
        assert not widget.ensure_loaded()
        assert widget.load_error == 'missing tool'
        assert not widget.ensure_loaded()
        load.assert_called_once()
        assert any('missing tool' in label.text() for label in widget.findChildren(QLabel))
        widget.close()
        widget.deleteLater()
