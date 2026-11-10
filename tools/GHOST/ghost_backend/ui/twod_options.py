"""Independent linear-solver and specified-mesh controls for 2-D runs."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QWidget
from ghost_backend.ui.table_editors import ScrollSafeComboBox as QComboBox

from ghost_backend.runs.controls import (FACTORIZATION_LABELS, DIAGNOSTIC_FACTORIZATION_LABELS,
                                        run_control_options)


class TwoDOptionsWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._automatic_mesh = True
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.factorization = QComboBox()
        for key, label in FACTORIZATION_LABELS.items():
            self.factorization.addItem(label, key)
        self.factorization.setToolTip(
            'Shared by all mesh workflows. Compressed uses less memory; Dense can be faster '
            'on smaller problems. Mesh checking does not change this selection. Dense may '
            'use hierarchical factors internally, with LU fallback.')
        self.form.addRow('Linear solver', self.factorization)
        self.mesh = QComboBox()
        self.mesh.addItem('Global wavelength sizing', 'global')
        self.mesh.addItem('Local material sizing', 'local')
        self.mesh.setToolTip(
            'Uses the geometry N values. Global sizes wavelength-based counts using the '
            'controlling material wavelength; Local uses local material sizing. A failed '
            'Local mesh comparison can retry Global sizing with the same linear solver.')
        self.form.addRow('Specified mesh sizing', self.mesh)
        self.order = QComboBox()
        for degree in (1, 2, 3):
            self.order.addItem('P{} ({})'.format(degree, ('linear', 'quadratic', 'cubic')[degree - 1]), degree)
        self.order.setToolTip('Keep the polynomial order used to validate your specified mesh.')
        self.form.addRow('Polynomial order', self.order)
        self.automatic_note = QLabel(
            'Automatic mesh search chooses P2/P3 candidates when suitable, with P1 fallback. '
            'Your specified-mesh sizing and polynomial order are retained for the other workflows.')
        self.automatic_note.setWordWrap(True)
        self.form.addRow(self.automatic_note)
        self.grading = QCheckBox('Grade corners, open ends, and material junctions')
        self.grading.setChecked(True)
        self.grading.setToolTip(
            'Clustering can add or redistribute panels, including in a single-mesh solve. '
            'Keep the grading used when validating your mesh; turn it off for an already '
            'specified panel layout that needs no additional grading.')
        self.form.addRow(self.grading)
        self.mesh_note = QLabel(
            'N in Geometry controls subdivision: 0 / negative values use wavelength sizing; '
            'positive values give panels per drawn primitive. A previous result\'s refined '
            'mesh is not automatically reused.')
        self.mesh_note.setWordWrap(True)
        self.form.addRow(self.mesh_note)
        for combo in (self.factorization, self.mesh, self.order):
            combo.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.grading.toggled.connect(lambda *_: self.changed.emit())
        self._sync_mesh_rows()

    def _sync_mesh_rows(self):
        for widget in (self.mesh, self.order, self.mesh_note):
            self.form.setRowVisible(widget, not self._automatic_mesh)
        self.form.setRowVisible(self.automatic_note, self._automatic_mesh)

    def set_automatic_mesh(self, enabled):
        """Change mesh workflow without resetting backend, manual mesh, or grading."""
        enabled = bool(enabled)
        if enabled != self._automatic_mesh:
            self._automatic_mesh = enabled
            self._sync_mesh_rows()
            self.changed.emit()

    def value(self):
        return dict(factorization=self.factorization.currentData(),
                    mesh_strategy='adaptive' if self._automatic_mesh else self.mesh.currentData(),
                    basis_order=1 if self._automatic_mesh else self.order.currentData(),
                    mesh_grading=self.grading.isChecked())

    def set_value(self, controls):
        """Restore explicit saved choices, including diagnostic backend settings."""
        value = run_control_options(controls)
        blocked = self.blockSignals(True)
        try:
            self.factorization.clear()
            for key, label in FACTORIZATION_LABELS.items():
                self.factorization.addItem(label, key)
            mode = value['factorization']
            if mode in DIAGNOSTIC_FACTORIZATION_LABELS:
                self.factorization.addItem(DIAGNOSTIC_FACTORIZATION_LABELS[mode], mode)
            self.factorization.setCurrentIndex(self.factorization.findData(mode))
            if value['mesh_strategy'] != 'adaptive':
                self.mesh.setCurrentIndex(self.mesh.findData(value['mesh_strategy']))
                self.order.setCurrentIndex(self.order.findData(value['basis_order']))
            self.grading.setChecked(value['mesh_grading'])
            self._automatic_mesh = value['mesh_strategy'] == 'adaptive'
            self._sync_mesh_rows()
        finally:
            self.blockSignals(blocked)
        self.changed.emit()
