"""Editors that keep table navigation separate from deliberate edits."""

try:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QComboBox, QSpinBox, QDoubleSpinBox
except ImportError:
    from PySide2.QtCore import QPointF  # type: ignore
    from PySide2.QtGui import QWheelEvent  # type: ignore
    from PySide2.QtWidgets import (  # type: ignore
        QApplication, QAbstractScrollArea, QComboBox, QSpinBox, QDoubleSpinBox,
    )


class _ScrollSafeEditor:
    """Pass wheel movement to the enclosing scroll area, even while focused."""

    def wheelEvent(self, event):
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QAbstractScrollArea):
            parent = parent.parentWidget()
        if parent is None:
            event.ignore()
            return

        viewport = parent.viewport()
        global_pos = (
            event.globalPosition()
            if hasattr(event, "globalPosition")
            else event.globalPosF()
        )
        forwarded = QWheelEvent(
            QPointF(viewport.mapFromGlobal(global_pos.toPoint())),
            global_pos,
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
            event.source(),
        )
        QApplication.sendEvent(viewport, forwarded)
        event.accept()


class ScrollSafeComboBox(_ScrollSafeEditor, QComboBox):
    """Scroll the enclosing table instead of editing a closed dropdown.

    Focus does not opt into wheel editing: clicking or using the keyboard can
    change the value, and an explicitly opened popup retains normal scrolling.
    """

    def wheelEvent(self, event):
        if self.view().isVisible():
            QComboBox.wheelEvent(self, event)
            return
        super().wheelEvent(event)


class ScrollSafeSpinBox(_ScrollSafeEditor, QSpinBox):
    """Integer editor changed only by typing, keys, or arrow buttons."""


class ScrollSafeDoubleSpinBox(_ScrollSafeEditor, QDoubleSpinBox):
    """Decimal editor changed only by typing, keys, or arrow buttons."""
