"""Non-focus-stealing toast.

``QSystemTrayIcon.showMessage`` goes through Shell_NotifyIcon/Windows toast,
which can pull foreground focus to the app — that makes the user's caret jump
and keystrokes land nowhere. This small widget is explicitly non-activating.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import palette


class Toast(QWidget):
    _active: list["Toast"] = []

    def __init__(self, title: str, message: str, timeout_ms: int = 3200) -> None:
        super().__init__(
            None,
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.title = title
        self.message = message
        self._timeout = max(800, int(timeout_ms))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self.resize(360, 92)

    # -- painting -------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(1, 1, self.width() - 2, self.height() - 2, 12, 12)
        painter.fillPath(path, QColor(16, 29, 44, 240))
        painter.setPen(QPen(QColor(palette.ACCENT), 1))
        painter.drawPath(path)

        painter.setPen(QColor(palette.CYAN))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(16, 26, self._elide(self.title, 30))

        painter.setPen(QColor(palette.TEXT))
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)
        text_rect = self.rect().adjusted(16, 34, -16, -8)
        painter.drawText(text_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
                         self.message)

    @staticmethod
    def _elide(text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    # -- show / hide ----------------------------------------------------
    def _place(self) -> None:
        screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else self.screen().availableGeometry()
        x = area.right() - self.width() - 24
        y = area.bottom() - self.height() - 24 - 56 * len(Toast._active)
        self.move(QPoint(x, max(area.top() + 24, y)))

    def show_message(self) -> None:
        Toast._active.append(self)
        self._place()
        self.show()          # WA_ShowWithoutActivating keeps the caret in place
        self._timer.start(self._timeout)

    def close(self) -> None:  # noqa: D102
        self._timer.stop()
        if self in Toast._active:
            Toast._active.remove(self)
        super().close()
        self.deleteLater()
        for index, toast in enumerate(list(Toast._active)):
            toast._place()

    @classmethod
    def push(cls, title: str, message: str, timeout_ms: int = 3200) -> "Toast":
        toast = cls(title, message, timeout_ms)
        toast.show_message()
        return toast


__all__ = ["Toast"]
