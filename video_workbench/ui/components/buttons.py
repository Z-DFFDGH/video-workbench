from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton


class LoadingButton(QPushButton):
    """Push button with a deterministic loading spinner and text state."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._idle_text = text
        self._loading_text = "处理中"
        self._loading = False
        self._dot_count = 0
        self._spinner_angle = 0
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(90)
        self._animation_timer.timeout.connect(self._advance_animation)

    @property
    def is_loading(self) -> bool:
        return self._loading

    @property
    def spinner_angle(self) -> int:
        return self._spinner_angle

    def set_loading(self, loading: bool, text: str | None = None) -> None:
        if loading == self._loading:
            return

        self._loading = loading
        if loading:
            self._dot_count = 0
            self._spinner_angle = 0
            self._loading_text = text or "处理中"
            self.setEnabled(False)
            self._render_loading_text()
            self._animation_timer.start()
        else:
            self._animation_timer.stop()
            self._spinner_angle = 0
            self.setEnabled(True)
            self.setText(self._idle_text)
            self.update()

    def set_idle_text(self, text: str) -> None:
        self._idle_text = text
        if not self._loading:
            self.setText(text)

    def _advance_animation(self) -> None:
        if not self._loading:
            return
        self._dot_count = (self._dot_count + 1) % 4
        self._spinner_angle = (self._spinner_angle + 30) % 360
        self._render_loading_text()
        self.update()

    def _render_loading_text(self) -> None:
        self.setText(self._loading_text + "." * self._dot_count)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._loading:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        size = 12.0
        spinner_rect = QRectF(
            14.0,
            (self.height() - size) / 2.0,
            size,
            size,
        )

        primary_pen = QPen(QColor(112, 228, 255, 225), 2.0)
        primary_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(primary_pen)
        painter.drawArc(
            spinner_rect,
            self._spinner_angle * 16,
            235 * 16,
        )

        secondary_pen = QPen(QColor(139, 108, 255, 205), 1.4)
        secondary_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(secondary_pen)
        painter.drawArc(
            spinner_rect.adjusted(1.8, 1.8, -1.8, -1.8),
            int((-self._spinner_angle * 1.5) * 16),
            150 * 16,
        )
