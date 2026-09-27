from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from video_workbench.ui.main_window import MainWindow
from video_workbench.ui.animations import system_animations_enabled
from video_workbench.ui.styles import apply_app_style


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("自媒体剪辑辅助工具")
    app.setOrganizationName("LocalVideoWorkbench")
    apply_app_style(app)

    window = MainWindow(animations_enabled=system_animations_enabled())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
