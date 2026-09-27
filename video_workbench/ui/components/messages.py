from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

MESSAGE_LEVELS = {"info", "success", "warning", "error"}


def _normalize_level(level: str) -> str:
    return level if level in MESSAGE_LEVELS else "info"


def _refresh_style(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class InlineMessage(QFrame):
    def __init__(
        self,
        text: str = "",
        kind: str = "info",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InlineMessage")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(8)

        self.text_label = QLabel(text, self)
        self.text_label.setObjectName("InlineMessageText")
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label, 1)

        self.set_message(text, kind)

    @property
    def kind(self) -> str:
        return str(self.property("kind"))

    def set_message(self, text: str, kind: str = "info") -> None:
        normalized = _normalize_level(kind)
        self.text_label.setText(text)
        self.setProperty("kind", normalized)
        self.setVisible(bool(text))
        _refresh_style(self)


class Toast(QFrame):
    closed = Signal(object)

    def __init__(self, message: str, kind: str = "info", parent=None) -> None:
        super().__init__(parent)
        self.message = message
        self.kind = _normalize_level(kind)
        self.setObjectName("Toast")
        self.setProperty("kind", self.kind)
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(8)

        self.message_label = QLabel(message, self)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

        self.close_button = QPushButton(self)
        self.close_button.setObjectName("WindowControl")
        self.close_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )
        self.close_button.setToolTip("关闭通知")
        self.close_button.clicked.connect(lambda: self.closed.emit(self))
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)


class ToastHost(QWidget):
    """Non-blocking notification stack positioned by the main window."""

    def __init__(
        self,
        parent=None,
        animations_enabled: bool = True,
    ) -> None:
        super().__init__(parent)
        self._animations_enabled = animations_enabled
        self.setObjectName("ToastHost")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.reveal_animation: QPropertyAnimation | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self._toasts: list[Toast] = []

    @property
    def active_messages(self) -> Iterable[tuple[str, str]]:
        return tuple((toast.message, toast.kind) for toast in self._toasts)

    def show_message(
        self,
        message: str,
        kind: str = "info",
        duration_ms: int = 3000,
    ) -> Toast:
        normalized = _normalize_level(kind)
        for toast in self._toasts:
            if toast.message == message and toast.kind == normalized:
                self._restart_dismiss_timer(toast, duration_ms)
                self._animate_in(toast)
                return toast

        toast = Toast(message, normalized, self)
        toast.closed.connect(self._remove_toast)
        self._toasts.append(toast)
        self._layout.addWidget(toast, 0, Qt.AlignmentFlag.AlignRight)
        toast.show()
        self._restart_dismiss_timer(toast, duration_ms)
        self.fit_to_contents()
        self._animate_in(toast)
        return toast

    def clear(self) -> None:
        for toast in tuple(self._toasts):
            self._remove_toast(toast)

    def fit_to_contents(self) -> None:
        self._layout.activate()
        self.resize(self.sizeHint())

    def _animate_in(self, toast: Toast) -> None:
        if not self._animations_enabled:
            return
        previous = getattr(toast, "_reveal_animation", None)
        if previous is not None:
            previous.stop()
            toast.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", toast)
        animation.setDuration(220)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda: self._finish_reveal_animation(toast, animation)
        )
        toast._reveal_animation = animation
        self.reveal_animation = animation
        animation.start()

    def _finish_reveal_animation(
        self,
        toast: Toast,
        animation: QPropertyAnimation,
    ) -> None:
        if getattr(toast, "_reveal_animation", None) is animation:
            toast._reveal_animation = None
        if self.reveal_animation is animation:
            self.reveal_animation = None
        toast.setGraphicsEffect(None)

    def _restart_dismiss_timer(self, toast: Toast, duration_ms: int) -> None:
        timer = toast.findChild(QTimer, "dismiss_timer")
        if timer is None:
            timer = QTimer(toast)
            timer.setObjectName("dismiss_timer")
            timer.setSingleShot(True)
            timer.timeout.connect(lambda current=toast: self._remove_toast(current))
        timer.stop()
        if duration_ms > 0:
            timer.start(duration_ms)

    def _remove_toast(self, toast: Toast) -> None:
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)
        self._layout.removeWidget(toast)
        toast.deleteLater()
        self.fit_to_contents()
