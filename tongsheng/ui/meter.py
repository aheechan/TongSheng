"""Live input level meter (right side of the control window)."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..audio import wav
from . import palette

FLOOR_DB = -50.0
CEIL_DB = 0.0


class LevelMeter(QWidget):
    """Vertical VU bar driven by a callable returning dBFS."""

    def __init__(self, level_provider, parent=None) -> None:
        super().__init__(parent)
        self._provider = level_provider
        self._level = FLOOR_DB
        self._peak = FLOOR_DB
        self._recording = False
        self.setMinimumWidth(54)
        self.setMaximumWidth(64)
        self.setToolTip("")
        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_recording(self, recording: bool) -> None:
        self._recording = recording

    def _tick(self) -> None:
        try:
            level = float(self._provider())
        except Exception:
            level = FLOOR_DB
        self._level = max(FLOOR_DB, min(CEIL_DB, level))
        self._peak = max(self._peak - 1.2, self._level)
        self.update()

    # -- painting -------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(8, 22, -8, -26)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(palette.PANEL))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(QColor(palette.LINE), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)

        span = rect.height()
        ratio = (self._level - FLOOR_DB) / (CEIL_DB - FLOOR_DB)
        height = int(span * max(0.0, min(1.0, ratio)))
        if height > 1:
            bar = QRect(rect.left() + 2, rect.bottom() - height + 2,
                        rect.width() - 4, height - 3)
            gradient = QLinearGradient(bar.left(), bar.bottom(), bar.left(), bar.top())
            gradient.setColorAt(0.0, QColor("#2FD47A"))
            gradient.setColorAt(0.65, QColor("#F5C542"))
            gradient.setColorAt(1.0, QColor("#FF5C5C"))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(bar, 4, 4)

        # ticks so an idle bar still looks like a meter
        painter.setPen(QPen(QColor(palette.LINE), 1))
        for db in (0, -10, -20, -30, -40):
            ratio = (db - FLOOR_DB) / (CEIL_DB - FLOOR_DB)
            y = rect.bottom() - int(span * ratio)
            painter.drawLine(rect.left() + 1, y, rect.left() + 6, y)
            painter.drawLine(rect.right() - 6, y, rect.right() - 1, y)

        # peak hold line
        peak_ratio = (self._peak - FLOOR_DB) / (CEIL_DB - FLOOR_DB)
        y = rect.bottom() - int(span * max(0.0, min(1.0, peak_ratio)))
        if self._peak > FLOOR_DB + 1:
            painter.setPen(QPen(QColor(palette.TEXT), 2))
            painter.drawLine(rect.left() + 3, y, rect.right() - 3, y)

        # labels
        painter.setPen(QColor(palette.MUTED if not self._recording else palette.CYAN))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(QRect(self.rect().left(), 2, self.width(), 18),
                         Qt.AlignCenter, "MIC")
        db_text = "--" if self._level <= FLOOR_DB + 0.5 else f"{self._level:.0f}"
        painter.drawText(QRect(self.rect().left(), self.rect().bottom() - 20,
                               self.width(), 18), Qt.AlignCenter, db_text)


__all__ = ["LevelMeter", "FLOOR_DB", "CEIL_DB"]
