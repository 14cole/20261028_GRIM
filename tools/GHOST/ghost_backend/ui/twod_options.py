"""Advanced 2-D monostatic controls; numerical policy stays in runs.controls."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QWidget

from ghost_backend.runs.controls import (FACTORIZATION_LABELS, DIAGNOSTIC_FACTORIZATION_LABELS,
                                        run_control_options)


class TwoDOptionsWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.factorization = QComboBox()
        for key, label in FACTORIZATION_LABELS.items():
            self.factorization.addItem(label, key)
        self.factorization.setToolTip(
            'Compressed is the default and uses less memory for larger problems. '
            'Choose Dense explicitly when needed; it can use hierarchical '
            'factorization internally, with LU fallback.')
        self.factorization_override = QCheckBox('Override compressed solver (advanced)')
        form.addRow(self.factorization_override)
        form.addRow('Solver', self.factorization)
        self.factorization.setEnabled(False)
        self.mesh = QComboBox()
        for key in ('adaptive', 'local', 'global'):
            self.mesh.addItem(key.capitalize(), key)
        self.mesh.setToolTip(
            'Adaptive chooses and checks polynomial meshes when certification is on. '
            'Local and Global retain manual polynomial-order control.')
        form.addRow('Mesh strategy', self.mesh)
        self.order = QComboBox()
        self.order.addItem('Automatic', 0)
        for degree in (1, 2, 3):
            self.order.addItem('P{}'.format(degree), degree)
        self.order.setToolTip('Manual order applies to Local or Global meshes. Adaptive controls it automatically.')
        form.addRow('Polynomial order', self.order)
        self.grading = QCheckBox('Grade corners, open ends, and material junctions')
        self.grading.setChecked(True)
        form.addRow(self.grading)
        self._manual_order = 1
        self.mesh.currentIndexChanged.connect(self._sync)
        self.factorization.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.factorization_override.toggled.connect(self._sync_factorization)
        self.order.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.grading.toggled.connect(lambda *_: self.changed.emit())
        self._sync()

    def _sync_factorization(self, manual):
        self.factorization.setEnabled(manual)
        if not manual:
            self.factorization.setCurrentIndex(self.factorization.findData('compressed'))
        self.changed.emit()

    def _sync(self, *_):
        adaptive = self.mesh.currentData() == 'adaptive'
        current = self.order.currentData()
        if adaptive and current:
            self._manual_order = current
        blocked = self.order.blockSignals(True)
        self.order.setCurrentIndex(self.order.findData(0 if adaptive else (current or self._manual_order)))
        # Automatic is display-only: fixed meshes must select a real degree.
        self.order.model().item(0).setEnabled(adaptive)
        self.order.blockSignals(blocked)
        self.order.setEnabled(not adaptive)
        self.changed.emit()

    def value(self):
        return dict(factorization=self.factorization.currentData(), mesh_strategy=self.mesh.currentData(),
                    basis_order=self.order.currentData() or 1, mesh_grading=self.grading.isChecked())

    def set_value(self, controls):
        # Preserve explicit saved diagnostic choices rather than silently changing
        # their numerical/fallback semantics. Fresh runs offer only the core modes.
        value = run_control_options(controls)
        blocked = self.factorization.blockSignals(True)
        self.factorization.clear()
        for key, label in FACTORIZATION_LABELS.items():
            self.factorization.addItem(label, key)
        mode = value['factorization']
        if mode in DIAGNOSTIC_FACTORIZATION_LABELS:
            self.factorization.addItem(DIAGNOSTIC_FACTORIZATION_LABELS[mode], mode)
        self.factorization.setCurrentIndex(self.factorization.findData(value['factorization']))
        self.factorization.blockSignals(blocked)
        blocked = self.factorization_override.blockSignals(True)
        self.factorization_override.setChecked(mode != 'compressed')
        self.factorization_override.blockSignals(blocked)
        self.factorization.setEnabled(mode != 'compressed')
        self.mesh.setCurrentIndex(self.mesh.findData(value['mesh_strategy']))
        self._manual_order = value['basis_order']
        self.order.setCurrentIndex(self.order.findData(value['basis_order']))
        self.grading.setChecked(value['mesh_grading'])
        self._sync()
