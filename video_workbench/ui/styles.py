from __future__ import annotations

from PySide6.QtWidgets import QApplication

COLORS = {
    "text": "#EEF0FF",
    "secondary": "#A7A9C5",
    "muted": "#747894",
    "accent": "#8B6CFF",
    "cyan": "#62E3FF",
    "success": "#56E39F",
    "warning": "#F4C96B",
    "danger": "#FF6B86",
    "glass": "rgba(15, 18, 36, 220)",
    "surface": "rgba(20, 24, 46, 225)",
    "border": "rgba(139, 108, 255, 55)",
}

APP_STYLE = """
QWidget {
    color: #EEF0FF;
    font-family: "Segoe UI Variable", "Microsoft YaHei UI";
    font-size: 13px;
}

QMainWindow, QWidget#AppShell, QWidget#ToastHost {
    background: #070A14;
}

QFrame#GlassTopBar,
QFrame#GlassSidebar,
QFrame#GlassContent,
QFrame#GlassContext,
QFrame#GlassTaskDrawer,
QFrame#GlassPopover {
    background-color: rgba(13, 17, 34, 220);
    border: 1px solid rgba(139, 108, 255, 58);
    border-radius: 12px;
}

QFrame#GlassPopover {
    background-color: rgba(12, 15, 31, 248);
}

QLabel#AppTitle {
    font-size: 14px;
    font-weight: 600;
}

QLabel#ProjectTitle {
    font-size: 14px;
    font-weight: 600;
}

QLabel#PageTitle {
    font-size: 20px;
    font-weight: 600;
}

QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 600;
}

QLabel#SecondaryText,
QLabel#PageDescription,
QLabel#EmptyDescription,
QLabel#InlineMessageText,
QLabel#ContextHint {
    color: #A7A9C5;
}

QLabel#MetaText {
    color: #747894;
    font-size: 12px;
}

QToolButton#NavButton {
    min-height: 38px;
    padding: 0 10px;
    border: 0;
    border-radius: 9px;
    color: #B9BCD7;
    text-align: left;
}

QToolButton#NavButton:hover {
    color: #F3F1FF;
    background-color: rgba(120, 103, 255, 38);
    border: 1px solid rgba(120, 103, 255, 55);
}

QToolButton#NavButton:pressed {
    background-color: rgba(98, 227, 255, 34);
}

QToolButton#NavButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(116, 91, 255, 105), stop:1 rgba(72, 134, 255, 42));
    color: #F5F2FF;
    border: 1px solid rgba(142, 118, 255, 95);
    font-weight: 600;
}

QToolButton#NavButton:focus {
    border: 2px solid rgba(98, 227, 255, 165);
}

QPushButton {
    min-height: 32px;
    padding: 0 12px;
    border: 1px solid rgba(139, 143, 190, 55);
    border-radius: 8px;
    background-color: rgba(25, 30, 56, 190);
}

QPushButton:hover {
    border-color: rgba(98, 227, 255, 100);
    background-color: rgba(36, 42, 76, 225);
}

QPushButton:pressed {
    background-color: rgba(98, 227, 255, 35);
}

QPushButton:focus {
    border: 2px solid rgba(98, 227, 255, 170);
}

QPushButton:disabled {
    color: #686C88;
    background-color: rgba(22, 26, 48, 125);
}

QPushButton[role="primary"] {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #8668FF, stop:0.58 #5D7DFF, stop:1 #46D6EE);
    border-color: rgba(151, 126, 255, 210);
    font-weight: 600;
}

QPushButton[role="primary"]:hover {
    border-color: rgba(112, 232, 255, 220);
}

QPushButton[role="primary"]:pressed {
    background: #6854E8;
}

QPushButton[role="danger"] {
    color: #FF8299;
    border-color: rgba(255, 107, 134, 110);
    background-color: rgba(255, 107, 134, 24);
}

QPushButton#WindowControl {
    min-width: 30px;
    max-width: 30px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    border: 0;
    border-radius: 7px;
    background: transparent;
}

QPushButton#WindowControl:hover {
    background-color: rgba(139, 108, 255, 42);
}

QPushButton#WindowControl[close="true"]:hover {
    color: white;
    background-color: #FF5F7A;
}

QToolButton#DrawerToggle {
    min-width: 52px;
    min-height: 28px;
    padding: 0 10px;
    color: #DCDDF6;
    border: 1px solid rgba(139, 108, 255, 68);
    border-radius: 7px;
    background-color: rgba(31, 36, 68, 205);
}

QToolButton#DrawerToggle:hover {
    border-color: rgba(98, 227, 255, 95);
    background-color: rgba(42, 49, 86, 225);
}

QToolButton#DrawerToggle:pressed {
    background-color: rgba(98, 227, 255, 35);
}
QFrame#InlineMessage {
    border-radius: 9px;
    border: 1px solid rgba(139, 108, 255, 45);
    background-color: rgba(18, 23, 45, 185);
}

QFrame#InlineMessage[kind="success"] {
    border-color: rgba(36, 138, 61, 75);
    background-color: rgba(52, 199, 89, 20);
}

QFrame#InlineMessage[kind="warning"] {
    border-color: rgba(178, 94, 0, 75);
    background-color: rgba(255, 159, 10, 20);
}

QFrame#InlineMessage[kind="error"] {
    border-color: rgba(215, 0, 21, 75);
    background-color: rgba(255, 59, 48, 20);
}

QFrame#Toast[kind="success"] {
    border-left: 3px solid #34C759;
}

QFrame#Toast[kind="warning"] {
    border-left: 3px solid #FF9F0A;
}

QFrame#Toast[kind="error"] {
    border-left: 3px solid #FF3B30;
}

QFrame#Toast[kind="info"] {
    border-left: 3px solid #007AFF;
}

QFrame#Toast {
    background-color: rgba(14, 18, 37, 248);
    border: 1px solid rgba(139, 108, 255, 68);
    border-radius: 10px;
}

QFrame#EmptyState {
    border: 1px dashed rgba(139, 108, 255, 72);
    border-radius: 12px;
    background-color: rgba(17, 21, 41, 115);
}

QDialog {
    background-color: #0B0F20;
}

QScrollArea {
    border: 0;
    background: transparent;
}
QAbstractScrollArea QWidget#qt_scrollarea_viewport {

    background: transparent;
}

QCheckBox {
    color: #C8CAE3;
    spacing: 7px;
}

QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid rgba(139, 108, 255, 85);
    border-radius: 4px;
    background-color: rgba(18, 23, 45, 220);
}

QCheckBox::indicator:checked {
    border-color: rgba(98, 227, 255, 170);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #8668FF, stop:1 #46D6EE);
}

QMenu {
    padding: 6px;
    border: 1px solid rgba(139, 108, 255, 75);
    border-radius: 10px;
    background-color: #11162B;
}

QMenu::item {
    min-width: 150px;
    padding: 7px 12px;
    border-radius: 7px;
}

QMenu::item:selected {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(116, 91, 255, 185), stop:1 rgba(70, 176, 241, 120));
}

QFrame#WelcomePanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(28, 25, 62, 235), stop:0.52 rgba(17, 25, 55, 235),
        stop:1 rgba(10, 21, 44, 235));
    border: 1px solid rgba(127, 103, 255, 72);
    border-radius: 12px;
}

QFrame#DashboardCard {
    background-color: rgba(16, 21, 42, 225);
    border: 1px solid rgba(122, 119, 184, 45);
    border-radius: 10px;
}

QFrame#DashboardCard[hovered="true"] {
    background-color: rgba(21, 27, 52, 235);
    border: 1px solid rgba(98, 227, 255, 92);
}

QLabel#Eyebrow {
    color: #70E4FF;
    font-size: 10px;
    font-weight: 700;
}

QLabel#HeroTitle {
    color: #F3F2FF;
    font-size: 21px;
    font-weight: 700;
}

QLabel#HeroDescription {
    color: #A9ACCC;
}

QLabel#MetricLabel {
    color: #9699B9;
    font-size: 12px;
}

QLabel#MetricValue {
    color: #E9EAFF;
    font-size: 24px;
    font-weight: 700;
}

QLabel#MetricValue[accent="cyan"] {
    color: #78E7FF;
}

QLabel#MetricValue[accent="purple"] {
    color: #B69AFF;
}

QLabel#MetricValue[accent="blue"] {
    color: #79A8FF;
}

QLabel#CardTitle {
    color: #ECECFF;
    font-size: 14px;
    font-weight: 600;
}

QLabel#StatusPill {
    color: #79E7FF;
    background-color: rgba(65, 215, 245, 22);
    border: 1px solid rgba(84, 218, 245, 58);
    border-radius: 8px;
    padding: 3px 8px;
    font-size: 11px;
}

QLabel#NeonBadge {
    color: #A89AFF;
    background-color: rgba(123, 91, 255, 28);
    border: 1px solid rgba(139, 108, 255, 72);
    border-radius: 7px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 700;
}

QLabel#ProfileName {
    color: #F0EFFF;
    font-size: 16px;
    font-weight: 600;
}

QFrame#NeonDivider {
    color: rgba(111, 126, 194, 45);
    background-color: rgba(111, 126, 194, 45);
    max-height: 1px;
}

QComboBox#RangeSelector {
    min-width: 86px;
    min-height: 28px;
    padding: 0 26px 0 9px;
    color: #DCDDF6;
    border: 1px solid rgba(139, 108, 255, 68);
    border-radius: 8px;
    background-color: rgba(31, 36, 68, 205);
}

QComboBox#RangeSelector:hover,
QComboBox#RangeSelector:focus {
    border-color: rgba(98, 227, 255, 118);
    background-color: rgba(42, 49, 86, 225);
}

QComboBox#RangeSelector QAbstractItemView {
    color: #E7E8FF;
    border: 1px solid rgba(139, 108, 255, 75);
    border-radius: 8px;
    background-color: #11162B;
    selection-background-color: rgba(107, 83, 220, 170);
}

QLineEdit#PathInput,
QPlainTextEdit#DownloadLinkInput {
    padding: 8px 10px;
    color: #EEF0FF;
    border: 1px solid rgba(139, 108, 255, 58);
    border-radius: 9px;
    background-color: rgba(8, 12, 27, 205);
    selection-background-color: rgba(107, 83, 220, 170);
}

QPlainTextEdit#ScriptEditor,
QPlainTextEdit#NotesEditor,
QPlainTextEdit#SensitiveTextEditor {
    padding: 12px;
    color: #EEF0FF;
    border: 1px solid rgba(139, 108, 255, 48);
    border-radius: 9px;
    background-color: rgba(8, 12, 27, 215);
    selection-background-color: rgba(107, 83, 220, 170);
}

QWidget#ScriptEditorViewport,
QWidget#NotesEditorViewport,
QWidget#SensitiveTextEditorViewport {
    background-color: #080C1B;
}

QWidget#ScriptDocumentListViewport,
QWidget#SensitiveMatchListViewport {
    background-color: #10152A;
}

QPlainTextEdit#ScriptEditor:focus,
QPlainTextEdit#NotesEditor:focus,
QPlainTextEdit#SensitiveTextEditor:focus {
    border-color: rgba(98, 227, 255, 135);
}

QListWidget#ScriptDocumentList,
QListWidget#SensitiveMatchList {
    padding: 4px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    outline: 0;
}

QListWidget#ScriptDocumentList::item,
QListWidget#SensitiveMatchList::item {
    min-height: 32px;
    padding: 0 8px;
    border-radius: 7px;
}

QListWidget#ScriptDocumentList::item:hover,
QListWidget#SensitiveMatchList::item:hover {
    background-color: rgba(120, 103, 255, 38);
}

QListWidget#ScriptDocumentList::item:selected,
QListWidget#SensitiveMatchList::item:selected {
    color: #F5F2FF;
    border: 1px solid rgba(142, 118, 255, 95);
    background-color: rgba(116, 91, 255, 85);
}

QLabel#SaveStatus {
    color: #A7A9C5;
    border: 1px solid rgba(139, 143, 190, 55);
    border-radius: 7px;
    padding: 3px 8px;
    font-size: 11px;
}

QLabel#PathHint {
    color: #858AA8;
    font-size: 11px;
}

QLabel#SaveStatus[status="dirty"] {
    color: #F4C96B;
    border-color: rgba(244, 201, 107, 75);
    background-color: rgba(244, 201, 107, 18);
}

QLabel#SaveStatus[status="saving"] {
    color: #78E7FF;
    border-color: rgba(98, 227, 255, 75);
    background-color: rgba(98, 227, 255, 18);
}

QLabel#SaveStatus[status="saved"] {
    color: #65EDAF;
    border-color: rgba(86, 227, 159, 75);
    background-color: rgba(86, 227, 159, 18);
}

QLabel#SaveStatus[status="error"] {
    color: #FF8299;
    border-color: rgba(255, 107, 134, 75);
    background-color: rgba(255, 107, 134, 18);
}

QFrame#MaterialDropZone {
    border: 1px dashed rgba(139, 108, 255, 95);
    border-radius: 11px;
    background-color: rgba(17, 22, 43, 150);
}

QFrame#MaterialDropZone[dragActive="true"] {
    border: 1px solid rgba(98, 227, 255, 190);
    background-color: rgba(72, 134, 255, 42);
}

QLineEdit#SearchInput {
    min-height: 30px;
    padding: 0 10px;
    color: #EEF0FF;
    border: 1px solid rgba(139, 108, 255, 58);
    border-radius: 8px;
    background-color: rgba(8, 12, 27, 205);
    selection-background-color: rgba(107, 83, 220, 170);
}

QLineEdit#SearchInput:focus {
    border-color: rgba(98, 227, 255, 135);
}

QToolButton#ViewModeButton {
    min-height: 30px;
    padding: 0 10px;
    color: #B9BCD7;
    border: 1px solid rgba(139, 108, 255, 58);
    border-radius: 8px;
    background-color: rgba(31, 36, 68, 170);
}

QToolButton#ViewModeButton:hover,
QToolButton#ViewModeButton:checked {
    color: #F3F1FF;
    border-color: rgba(98, 227, 255, 125);
    background-color: rgba(116, 91, 255, 75);
}

QToolButton#ToolCategoryButton {
    min-height: 34px;
    padding: 0 13px;
    color: #B9BCD7;
    border: 1px solid rgba(139, 108, 255, 58);
    border-radius: 8px;
    background-color: rgba(31, 36, 68, 170);
}

QToolButton#ToolCategoryButton:hover,
QToolButton#ToolCategoryButton:checked {
    color: #F3F1FF;
    border-color: rgba(98, 227, 255, 125);
    background-color: rgba(116, 91, 255, 75);
}

QSpinBox, QDoubleSpinBox {
    min-height: 30px;
    min-width: 92px;
    padding: 0 8px;
    color: #EEF0FF;
    border: 1px solid rgba(139, 108, 255, 58);
    border-radius: 8px;
    background-color: rgba(8, 12, 27, 205);
    selection-background-color: rgba(107, 83, 220, 170);
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: rgba(98, 227, 255, 135);
}

QListWidget#MaterialList,
QListWidget#TagList {
    padding: 4px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    outline: 0;
}

QWidget#MaterialListViewport,
QWidget#TagListViewport {
    background-color: #10152A;
}

QListWidget#MaterialList::item,
QListWidget#TagList::item {
    min-height: 34px;
    padding: 5px 8px;
    border-radius: 7px;
}

QListWidget#MaterialList::item:hover,
QListWidget#TagList::item:hover {
    background-color: rgba(120, 103, 255, 38);
}

QListWidget#MaterialList::item:selected,
QListWidget#TagList::item:selected {
    color: #F5F2FF;
    border: 1px solid rgba(142, 118, 255, 95);
    background-color: rgba(116, 91, 255, 85);
}

QLabel#MaterialPreview {
    color: #747894;
    border: 1px solid rgba(139, 108, 255, 48);
    border-radius: 9px;
    background-color: rgba(8, 12, 27, 205);
}

QLineEdit#PathInput:focus,
QPlainTextEdit#DownloadLinkInput:focus {
    border-color: rgba(98, 227, 255, 135);
}

QPushButton#IconButton {
    min-width: 34px;
    max-width: 34px;
    padding: 0;
}

QPushButton#TaskCancelButton {
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}

QFrame#TaskRow {
    background-color: rgba(17, 22, 43, 185);
    border: 1px solid rgba(107, 116, 180, 42);
    border-radius: 8px;
}

QLabel#TaskTitle {
    color: #E7E9FF;
    font-size: 12px;
}

QLabel#TaskDetail {
    color: #858AA8;
    font-size: 11px;
}

QLabel#StatusPill[status="completed"] {
    color: #65EDAF;
    border-color: rgba(86, 227, 159, 75);
    background-color: rgba(86, 227, 159, 20);
}

QLabel#StatusPill[status="failed"] {
    color: #FF8299;
    border-color: rgba(255, 107, 134, 75);
    background-color: rgba(255, 107, 134, 20);
}

QLabel#StatusPill[status="canceled"] {
    color: #C0C3D8;
    border-color: rgba(192, 195, 216, 55);
    background-color: rgba(192, 195, 216, 14);
}

QScrollBar:vertical {
    width: 8px;
    margin: 4px 0;
    background: transparent;
}

QScrollBar::handle:vertical {
    min-height: 30px;
    border-radius: 4px;
    background: rgba(125, 112, 210, 90);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
"""


def apply_app_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
