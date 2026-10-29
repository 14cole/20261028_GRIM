"""Model-backed coordinate lists populate instantly and keep the QListWidget-style API."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication

from GRIM_Backend.ui.coordinate_list import CoordinateListView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_large_axis_populates_in_constant_time(app):
    view = CoordinateListView()
    view.setSelectionMode(QAbstractItemView.ExtendedSelection)
    values = np.linspace(-180., 180., 100_000)
    start = time.perf_counter()
    view.set_coordinates(values)
    elapsed = time.perf_counter() - start
    assert view.count() == 100_000 and elapsed < 0.5
    start = time.perf_counter()
    view.selectAll()
    assert time.perf_counter() - start < 0.5
    assert len(view.selected_rows()) == 100_000
    assert view.item(99_999).data(Qt.UserRole + 1) == 99_999
    assert view.item(0).text() == str(values[0])
    assert view.coordinate_values()[-1] == values[-1]
    view.clear()
    assert view.count() == 0 and view.item(0) is None


def test_subset_indices_selection_and_signals(app):
    view = CoordinateListView()
    view.setSelectionMode(QAbstractItemView.ExtendedSelection)
    changes = []
    view.itemSelectionChanged.connect(lambda: changes.append(1))
    view.set_coordinates(np.array([10., 20., 30., 40.]), [3, 1])
    assert [view.item(row).data(Qt.UserRole) for row in range(view.count())] == [40., 20.]
    assert list(view.displayed_axis_indices()) == [3, 1]
    view.item(1).setSelected(True)
    assert view.selected_axis_indices() == [1] and view.selected_values() == [20.]
    assert changes == [1]
    assert view.selectedItems() == [view.item(1)]
    assert view.row(view.selectedItems()[0]) == 1 and view.item(1).isSelected()
    view.blockSignals(True)
    view.select_rows([0, 1], clear=True)
    view.blockSignals(False)
    assert changes == [1] and view.selected_rows() == [0, 1]
    view.setCurrentItem(view.item(0), QItemSelectionModel.NoUpdate)
    assert view.currentItem() == view.item(0)
    view.clearSelection()
    assert view.selected_rows() == [] and not view.item(1).isSelected()
    view.set_coordinates(np.array(["VV", "HH"], dtype=object))
    assert view.item(1).text() == "HH" and view.coordinate_values() == ["VV", "HH"]


def test_inline_edits_emit_item_changed_and_restore(app):
    view = CoordinateListView()
    view.set_coordinates(np.array([1.5, 2.5]))
    edits = []
    view.itemChanged.connect(edits.append)
    item = view.item(1)
    item.setText("9.5")
    assert item.text() == "9.5" and item.data(Qt.UserRole) == 2.5 and edits == [item]
    view.blockSignals(True)
    item.setText("2.5")
    item.setData(Qt.UserRole, 2.5)
    view.blockSignals(False)
    assert edits == [item] and item.text() == "2.5"
    model = view.model()
    assert model.setData(model.index(0, 0), "7", Qt.EditRole)
    assert view.item(0).text() == "7" and model.data(model.index(0, 0), Qt.DisplayRole) == "7"
    assert len(edits) == 2 and edits[-1].data(Qt.UserRole + 1) == 0
    item.setToolTip("tip")
    assert item.toolTip() == "tip"
    assert bool(item.flags() & Qt.ItemIsEditable)
