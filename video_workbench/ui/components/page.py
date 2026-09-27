from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PageHeader(QWidget):
    def __init__(self, title: str, description: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("PageTitle")
        text_layout.addWidget(self.title_label)

        self.description_label = QLabel(description, self)
        self.description_label.setObjectName("PageDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        text_layout.addWidget(self.description_label)

        layout.addLayout(text_layout, 1)
        self.action_container = QWidget(self)
        self.action_layout = QHBoxLayout(self.action_container)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(8)
        layout.addWidget(self.action_container, 0, Qt.AlignmentFlag.AlignTop)

    def add_action(self, button: QPushButton) -> None:
        self.action_layout.addWidget(button)


class EmptyState(QFrame):
    def __init__(
        self,
        title: str,
        description: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(9)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("SectionTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.description_label = QLabel(description, self)
        self.description_label.setObjectName("EmptyDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setVisible(bool(description))

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)

        self.action_container = QWidget(self)
        self.action_layout = QHBoxLayout(self.action_container)
        self.action_layout.setContentsMargins(0, 8, 0, 0)
        self.action_layout.setSpacing(8)
        self.action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.action_container)

    def add_action(self, button: QPushButton) -> None:
        self.action_layout.addWidget(button)
