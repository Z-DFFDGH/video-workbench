from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WallpaperBackground(QWidget):
    """Full-window wallpaper canvas with a deterministic default wallpaper."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("WallpaperBackground")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._wallpaper = QPixmap()
        self._wallpaper_path: str | None = None

    @property
    def wallpaper_path(self) -> str | None:
        return self._wallpaper_path

    @property
    def is_default(self) -> bool:
        return self._wallpaper.isNull()

    def set_wallpaper_path(self, path: str | Path | None) -> bool:
        if path is None or not str(path).strip():
            self._wallpaper = QPixmap()
            self._wallpaper_path = None
            self.update()
            return True

        candidate = QPixmap(str(path))
        if candidate.isNull():
            self._wallpaper = QPixmap()
            self._wallpaper_path = None
            self.update()
            return False

        self._wallpaper = candidate
        self._wallpaper_path = str(Path(path))
        self.update()
        return True

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._wallpaper.isNull():
            self._paint_default_wallpaper(painter)
        else:
            self._paint_cover_image(painter)

        painter.fillRect(self.rect(), QColor(4, 7, 18, 72))

    def _paint_cover_image(self, painter: QPainter) -> None:
        target_width = max(1, self.width())
        target_height = max(1, self.height())
        source_width = self._wallpaper.width()
        source_height = self._wallpaper.height()

        target_ratio = target_width / target_height
        source_ratio = source_width / source_height
        if source_ratio > target_ratio:
            crop_width = int(source_height * target_ratio)
            source_x = (source_width - crop_width) // 2
            source = (source_x, 0, crop_width, source_height)
        else:
            crop_height = int(source_width / target_ratio)
            source_y = (source_height - crop_height) // 2
            source = (0, source_y, source_width, crop_height)

        painter.drawPixmap(self.rect(), self._wallpaper, source)

    def _paint_default_wallpaper(self, painter: QPainter) -> None:
        width = max(1, self.width())
        height = max(1, self.height())

        base = QLinearGradient(0, 0, width, height)
        base.setColorAt(0.0, QColor("#050711"))
        base.setColorAt(0.48, QColor("#0B1026"))
        base.setColorAt(1.0, QColor("#090D1C"))
        painter.fillRect(self.rect(), base)

        upper = QPainterPath()
        upper.moveTo(0, height * 0.35)
        upper.cubicTo(
            width * 0.24,
            height * 0.18,
            width * 0.56,
            height * 0.62,
            width,
            height * 0.25,
        )
        upper.lineTo(width, 0)
        upper.lineTo(0, 0)
        upper.closeSubpath()
        upper_gradient = QLinearGradient(0, 0, width, height * 0.55)
        upper_gradient.setColorAt(0.0, QColor(93, 67, 190, 72))
        upper_gradient.setColorAt(1.0, QColor(22, 34, 78, 34))
        painter.fillPath(upper, upper_gradient)

        lower = QPainterPath()
        lower.moveTo(0, height * 0.74)
        lower.cubicTo(
            width * 0.32,
            height * 0.57,
            width * 0.68,
            height * 0.94,
            width,
            height * 0.64,
        )
        lower.lineTo(width, height)
        lower.lineTo(0, height)
        lower.closeSubpath()
        lower_gradient = QLinearGradient(0, height * 0.5, width, height)
        lower_gradient.setColorAt(0.0, QColor(20, 31, 65, 72))
        lower_gradient.setColorAt(1.0, QColor(36, 73, 111, 42))
        painter.fillPath(lower, lower_gradient)

        accent = QPainterPath()
        accent.moveTo(0, height * 0.58)
        accent.cubicTo(
            width * 0.21,
            height * 0.43,
            width * 0.48,
            height * 0.81,
            width,
            height * 0.47,
        )
        accent.lineTo(width, height * 0.56)
        accent.cubicTo(
            width * 0.58,
            height * 0.88,
            width * 0.27,
            height * 0.55,
            0,
            height * 0.68,
        )
        accent.closeSubpath()
        painter.fillPath(accent, QColor(111, 84, 226, 38))


class WallpaperPanel(QFrame):
    wallpaper_selected = Signal(str)
    restore_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassPopover")
        self.setFixedWidth(340)
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("外观", self)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.preview = QLabel(self)
        self.preview.setFixedHeight(146)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "border: 1px solid rgba(60, 60, 67, 45); "
            "border-radius: 10px; background-color: rgba(255,255,255,90);"
        )
        layout.addWidget(self.preview)

        self.path_label = QLabel("默认壁纸", self)
        self.path_label.setObjectName("MetaText")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.choose_button = QPushButton("选择图片", self)
        self.choose_button.setProperty("role", "primary")
        self.restore_button = QPushButton("恢复默认", self)
        self.choose_button.clicked.connect(self._choose_wallpaper)
        self.restore_button.clicked.connect(self.restore_requested)
        buttons.addWidget(self.choose_button)
        buttons.addWidget(self.restore_button)
        layout.addLayout(buttons)

    def set_current_wallpaper(self, path: str | None) -> None:
        if path:
            self.path_label.setText(path)
            self.path_label.setToolTip(path)
            pixmap = QPixmap(path)
            if pixmap.isNull():
                self.preview.clear()
                self.preview.setText("壁纸不可用")
            else:
                self.preview.setPixmap(
                    pixmap.scaled(
                        self.preview.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        else:
            self.path_label.setText("默认壁纸")
            self.path_label.setToolTip("")
            self.preview.clear()
            self.preview.setText("默认")

    def _choose_wallpaper(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择壁纸",
            str(Path.home()),
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self.wallpaper_selected.emit(path)
