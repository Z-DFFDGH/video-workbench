from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ConfirmDialog(QDialog):
    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "确认",
        destructive: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(16)

        title_label = QLabel(title, self)
        title_label.setObjectName("SectionTitle")
        message_label = QLabel(message, self)
        message_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(message_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        self.cancel_button = QPushButton("取消", self)
        self.confirm_button = QPushButton(confirm_text, self)
        if destructive:
            self.confirm_button.setProperty("role", "danger")
        else:
            self.confirm_button.setProperty("role", "primary")

        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button.clicked.connect(self.accept)

        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)
        layout.addLayout(buttons)


def confirm(
    parent,
    title: str,
    message: str,
    confirm_text: str = "确认",
    destructive: bool = False,
) -> bool:
    dialog = ConfirmDialog(
        title=title,
        message=message,
        confirm_text=confirm_text,
        destructive=destructive,
        parent=parent,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted
