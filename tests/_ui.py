from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from video_workbench.ui.styles import apply_app_style

_APPLICATION: QApplication | None = None


def application() -> QApplication:
    global _APPLICATION
    if _APPLICATION is None:
        _APPLICATION = QApplication.instance() or QApplication([])
        apply_app_style(_APPLICATION)
    return _APPLICATION
