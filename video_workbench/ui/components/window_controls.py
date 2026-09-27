from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QStyle


class WindowControls(QFrame):
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.minimize_button = self._button(
            QStyle.StandardPixmap.SP_TitleBarMinButton,
            "最小化",
        )
        self.maximize_button = self._button(
            QStyle.StandardPixmap.SP_TitleBarMaxButton,
            "最大化",
        )
        self.close_button = self._button(
            QStyle.StandardPixmap.SP_TitleBarCloseButton,
            "关闭",
        )
        self.close_button.setProperty("close", True)

        self.minimize_button.clicked.connect(self.minimize_requested)
        self.maximize_button.clicked.connect(self.maximize_requested)
        self.close_button.clicked.connect(self.close_requested)

        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def _button(
        self,
        icon: QStyle.StandardPixmap,
        tooltip: str,
    ) -> QPushButton:
        button = QPushButton(self)
        button.setObjectName("WindowControl")
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        return button
