from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _add_soft_shadow(
    widget: QWidget,
    color: str = "#070A16",
) -> QGraphicsDropShadowEffect:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 8)
    shadow.setColor(QColor(color))
    widget.setGraphicsEffect(shadow)
    return shadow


class DashboardCard(QFrame):
    """Base card used by the dark dashboard composition."""

    def __init__(self, parent=None, animations_enabled: bool = True) -> None:
        super().__init__(parent)
        self._animations_enabled = animations_enabled
        self.setObjectName("DashboardCard")
        self._shadow = _add_soft_shadow(self)
        self._hover_animation = QParallelAnimationGroup(self)

        self._blur_animation = QPropertyAnimation(self._shadow, b"blurRadius")
        self._color_animation = QPropertyAnimation(self._shadow, b"color")
        self._offset_animation = QPropertyAnimation(self._shadow, b"offset")
        for animation in (
            self._blur_animation,
            self._color_animation,
            self._offset_animation,
        ):
            animation.setDuration(170)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._hover_animation.addAnimation(animation)

    def set_hovered(self, hovered: bool) -> None:
        self.setProperty("hovered", hovered)
        self.style().unpolish(self)
        self.style().polish(self)

        target_blur = 40 if hovered else 28
        target_color = (
            QColor(83, 214, 255, 78) if hovered else QColor("#070A16")
        )
        target_offset = QPointF(0, 13 if hovered else 8)
        if not self._animations_enabled:
            self._shadow.setBlurRadius(target_blur)
            self._shadow.setColor(target_color)
            self._shadow.setOffset(target_offset)
            return

        self._hover_animation.stop()
        self._blur_animation.setStartValue(self._shadow.blurRadius())
        self._blur_animation.setEndValue(target_blur)
        self._color_animation.setStartValue(self._shadow.color())
        self._color_animation.setEndValue(target_color)
        self._offset_animation.setStartValue(self._shadow.offset())
        self._offset_animation.setEndValue(target_offset)
        self._hover_animation.start()

    def enterEvent(self, event) -> None:
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.set_hovered(False)
        super().leaveEvent(event)


class MetricCard(DashboardCard):
    def __init__(
        self,
        label: str,
        accent: str = "purple",
        animations_enabled: bool = True,
        parent=None,
    ) -> None:
        super().__init__(
            parent,
            animations_enabled=animations_enabled,
        )
        self.setProperty("accent", accent)
        self.setMinimumHeight(92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(5)

        self.label = QLabel(label, self)
        self.label.setObjectName("MetricLabel")
        self.value = QLabel("—", self)
        self.value.setObjectName("MetricValue")
        self.value.setProperty("accent", accent)
        self.hint = QLabel("等待项目数据", self)
        self.hint.setObjectName("MetaText")

        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.hint)


class Sparkline(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(118)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        width = max(1, self.width())
        height = max(1, self.height())
        grid_pen = QPen(QColor(155, 145, 255, 24), 1)
        painter.setPen(grid_pen)
        for row in range(1, 4):
            y = height * row / 4
            painter.drawLine(QPointF(0, y), QPointF(width, y))
        for column in range(1, 6):
            x = width * column / 6
            painter.drawLine(QPointF(x, 0), QPointF(x, height))

        points = (
            QPointF(0, height * 0.72),
            QPointF(width * 0.14, height * 0.62),
            QPointF(width * 0.28, height * 0.68),
            QPointF(width * 0.42, height * 0.42),
            QPointF(width * 0.57, height * 0.48),
            QPointF(width * 0.70, height * 0.27),
            QPointF(width * 0.84, height * 0.34),
            QPointF(width, height * 0.15),
        )

        area = QPainterPath(points[0])
        for point in points[1:]:
            area.lineTo(point)
        area.lineTo(width, height)
        area.lineTo(0, height)
        area.closeSubpath()
        fill = QLinearGradient(0, 0, width, height)
        fill.setColorAt(0.0, QColor(129, 91, 255, 10))
        fill.setColorAt(1.0, QColor(77, 222, 255, 45))
        painter.fillPath(area, fill)

        line = QPainterPath(points[0])
        for point in points[1:]:
            line.lineTo(point)
        line_gradient = QLinearGradient(0, 0, width, 0)
        line_gradient.setColorAt(0.0, QColor("#8C6CFF"))
        line_gradient.setColorAt(0.55, QColor("#6F8CFF"))
        line_gradient.setColorAt(1.0, QColor("#63E6FF"))
        painter.setPen(QPen(line_gradient, 2.2))
        painter.drawPath(line)

        painter.setPen(Qt.PenStyle.NoPen)
        for point in points:
            painter.setBrush(QColor(99, 230, 255, 125))
            painter.drawEllipse(point, 3.2, 3.2)


class SparklineCard(DashboardCard):
    def __init__(self, parent=None, animations_enabled: bool = True) -> None:
        super().__init__(
            parent,
            animations_enabled=animations_enabled,
        )
        self.setMinimumHeight(204)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("项目活跃度", self)
        title.setObjectName("CardTitle")
        self.range_selector = QComboBox(self)
        self.range_selector.setObjectName("RangeSelector")
        self.range_selector.addItems(["近 7 天", "近 30 天", "全部"])
        self.range_selector.setToolTip("切换图表展示范围")
        self.status_label = QLabel("近 7 天 · 等待数据", self)
        self.status_label.setObjectName("StatusPill")
        self.range_selector.currentTextChanged.connect(self._on_range_changed)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        header.addWidget(self.range_selector)

        layout.addLayout(header)
        self.chart = Sparkline(self)
        layout.addWidget(self.chart, 1)

    def _on_range_changed(self, range_text: str) -> None:
        self.status_label.setText(f"{range_text} · 等待数据")


class AvatarBadge(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(68, 68)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = QPointF(self.width() / 2, self.height() / 2)

        glow = QRadialGradient(center, 34)
        glow.setColorAt(0.0, QColor(116, 92, 255, 105))
        glow.setColorAt(0.72, QColor(67, 197, 255, 38))
        glow.setColorAt(1.0, QColor(10, 13, 28, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, 34, 34)

        painter.setBrush(QColor("#151A36"))
        painter.setPen(QPen(QColor(111, 140, 255, 150), 1.5))
        painter.drawEllipse(center, 27, 27)

        painter.setBrush(QColor("#8C6CFF"))
        painter.drawEllipse(QPointF(center.x(), center.y() - 8), 7, 7)

        body = QPainterPath()
        body.moveTo(center.x() - 13, center.y() + 16)
        body.cubicTo(
            center.x() - 12,
            center.y() + 4,
            center.x() + 12,
            center.y() + 4,
            center.x() + 13,
            center.y() + 16,
        )
        body.closeSubpath()
        body_gradient = QLinearGradient(
            center.x() - 13,
            center.y(),
            center.x() + 13,
            center.y() + 16,
        )
        body_gradient.setColorAt(0.0, QColor("#6D72FF"))
        body_gradient.setColorAt(1.0, QColor("#48DDF4"))
        painter.setBrush(body_gradient)
        painter.drawPath(body)


class ProfileCard(DashboardCard):
    def __init__(self, parent=None, animations_enabled: bool = True) -> None:
        super().__init__(
            parent,
            animations_enabled=animations_enabled,
        )
        self.setMinimumWidth(240)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        avatar_row = QHBoxLayout()
        self.avatar = AvatarBadge(self)
        avatar_row.addWidget(self.avatar)
        avatar_row.addStretch(1)
        layout.addLayout(avatar_row)

        self.name = QLabel("本地工作区", self)
        self.name.setObjectName("ProfileName")
        self.state = QLabel("未打开项目", self)
        self.state.setObjectName("MetaText")
        badge = QLabel("LOCAL ONLY", self)
        badge.setObjectName("NeonBadge")

        layout.addWidget(self.name)
        layout.addWidget(self.state)
        layout.addSpacing(2)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)


class ActivityCard(DashboardCard):
    def __init__(self, parent=None, animations_enabled: bool = True) -> None:
        super().__init__(
            parent,
            animations_enabled=animations_enabled,
        )
        self.setMinimumHeight(92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("最近处理", self)
        title.setObjectName("CardTitle")
        state = QLabel("暂无记录", self)
        state.setObjectName("MetaText")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(state)
        layout.addLayout(header)

        divider = QFrame(self)
        divider.setObjectName("NeonDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        empty = QLabel("暂无处理记录", self)
        empty.setObjectName("MetaText")
        layout.addWidget(empty)


class PlanetIllustration(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(220, 142)
        self.setMaximumHeight(150)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = max(1, self.width())
        height = max(1, self.height())
        center = QPointF(width * 0.61, height * 0.52)
        radius = min(width, height) * 0.27

        halo = QRadialGradient(center, radius * 2.0)
        halo.setColorAt(0.0, QColor(133, 102, 255, 70))
        halo.setColorAt(0.52, QColor(61, 126, 255, 30))
        halo.setColorAt(1.0, QColor(4, 7, 18, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, radius * 2.0, radius * 2.0)

        planet_gradient = QRadialGradient(
            center.x() - radius * 0.36,
            center.y() - radius * 0.42,
            radius * 1.45,
        )
        planet_gradient.setColorAt(0.0, QColor("#B5A8FF"))
        planet_gradient.setColorAt(0.28, QColor("#746BEA"))
        planet_gradient.setColorAt(0.72, QColor("#3340A6"))
        planet_gradient.setColorAt(1.0, QColor("#121735"))
        painter.setBrush(planet_gradient)
        painter.drawEllipse(center, radius, radius)

        ring_rect = (
            center.x() - radius * 1.55,
            center.y() - radius * 0.42,
            radius * 3.1,
            radius * 0.84,
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(102, 221, 255, 115), 2))
        painter.drawEllipse(*ring_rect)

        painter.setPen(QPen(QColor(169, 128, 255, 120), 1))
        painter.drawArc(*ring_rect, 205 * 16, 128 * 16)

        painter.setPen(Qt.PenStyle.NoPen)
        for x_ratio, y_ratio, size, color in (
            (0.12, 0.20, 2.4, QColor("#6FE7FF")),
            (0.28, 0.76, 1.8, QColor("#9B82FF")),
            (0.86, 0.20, 2.0, QColor("#B9A9FF")),
            (0.92, 0.68, 1.5, QColor("#5AD8FF")),
        ):
            painter.setBrush(color)
            painter.drawEllipse(
                QPointF(width * x_ratio, height * y_ratio),
                size,
                size,
            )


class DashboardHome(QWidget):
    new_project_requested = Signal()
    open_project_requested = Signal()

    def __init__(self, parent=None, animations_enabled: bool = True) -> None:
        super().__init__(parent)
        self._animations_enabled = animations_enabled
        self.setObjectName("DashboardHome")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero = QFrame(self)
        hero.setObjectName("WelcomePanel")
        _add_soft_shadow(hero, "#070A18")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 12, 14)
        hero_layout.setSpacing(12)

        copy_layout = QVBoxLayout()
        copy_layout.setSpacing(5)
        eyebrow = QLabel("LOCAL MEDIA DASHBOARD", hero)
        eyebrow.setObjectName("Eyebrow")
        self.project_name = QLabel("未打开项目", hero)
        self.project_name.setObjectName("HeroTitle")
        self.project_state = QLabel("等待项目接入", hero)
        self.project_state.setObjectName("HeroDescription")
        copy_layout.addWidget(eyebrow)
        copy_layout.addWidget(self.project_name)
        copy_layout.addWidget(self.project_state)
        copy_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        new_button = QPushButton("新建项目", hero)
        new_button.setProperty("role", "primary")
        new_button.setMinimumWidth(112)
        new_button.setMaximumWidth(132)
        new_button.clicked.connect(self.new_project_requested)
        self.open_button = QPushButton("打开项目", hero)
        self.open_button.setMinimumWidth(112)
        self.open_button.setMaximumWidth(132)
        self.open_button.setToolTip("选择已有项目文件夹")
        self.open_button.clicked.connect(self.open_project_requested)
        actions.addWidget(new_button)
        actions.addWidget(self.open_button)
        actions.addStretch(1)
        copy_layout.addLayout(actions)

        hero_layout.addLayout(copy_layout, 1)
        hero_layout.addWidget(PlanetIllustration(hero), 0)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.material_metric = MetricCard(
            "素材",
            "cyan",
            animations_enabled=animations_enabled,
            parent=self,
        )
        self.script_metric = MetricCard(
            "脚本",
            "purple",
            animations_enabled=animations_enabled,
            parent=self,
        )
        self.output_metric = MetricCard(
            "输出",
            "blue",
            animations_enabled=animations_enabled,
            parent=self,
        )
        metrics.addWidget(self.material_metric)
        metrics.addWidget(self.script_metric)
        metrics.addWidget(self.output_metric)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        self.activity_chart = SparklineCard(
            self,
            animations_enabled=animations_enabled,
        )
        self.profile = ProfileCard(
            self,
            animations_enabled=animations_enabled,
        )
        lower.addWidget(self.activity_chart, 1)
        lower.addWidget(self.profile)

        activity = ActivityCard(
            self,
            animations_enabled=animations_enabled,
        )

        layout.addWidget(hero)
        layout.addLayout(metrics)
        layout.addLayout(lower, 1)
        layout.addWidget(activity)

    def set_project(self, name: str | None) -> None:
        display_name = name or "未打开项目"
        self.project_name.setText(display_name)
        self.profile.name.setText(name or "本地工作区")
        self.profile.state.setText(name or "未打开项目")
        self.project_state.setText(
            "项目已就绪，等待素材与脚本数据"
            if name
            else "等待项目接入"
        )
