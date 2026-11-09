from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QVBoxLayout

# Shared palette for widgets, custom painting and native Qt popups.
BACKGROUND = "#0b1220"
SURFACE = "#111c2e"
ACCENT = "#60a5fa"
INK = "#eaf2ff"
MUTED = "#9fb2cc"

STYLE = """
QWidget { font-family: 'Adwaita Sans', 'Noto Sans', sans-serif; font-size: 14px; color: #eaf2ff; }
QMainWindow, QDialog { background: #0b1220; }
QWidget#page { background: #0b1220; }
QFrame#sidebar { background: #0e1726; border-right: 1px solid #22324a; }
QLabel { background: transparent; }
QLabel#brand { font-size: 29px; font-weight: 650; }
QLabel#title { font-size: 30px; font-weight: 600; }
QLabel#sectionTitle { font-size: 17px; font-weight: 600; }
QLabel#eyebrow { color: #93c5fd; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; }
QLabel#muted { color: #9fb2cc; font-size: 13px; }
QLabel#hint { color: #8ea4bf; font-size: 11px; }
QLabel#number { font-size: 27px; font-weight: 600; }
QLabel#badge { color: #bfdbfe; background: #172f4f; padding: 7px 12px; border-radius: 14px; font-size: 12px; }
QLabel#error { color: #ffb5a3; background: #3e2823; padding: 10px; border-radius: 7px; }
QFrame#card { background: #111c2e; border: 1px solid #233550; border-radius: 18px; }
QFrame#softCard { background: #142a47; border: 1px solid #28476c; border-radius: 16px; }
QFrame#miniSurface { background: #111c2e; border: 1px solid #355d83; border-radius: 14px; }
QFrame#separator { background: #263a55; max-height: 1px; }
QPushButton { background: #172740; border: 1px solid transparent; padding: 10px 16px; border-radius: 9px; font-weight: 600; }
QPushButton:hover { background: #1e3554; }
QPushButton:pressed { background: #26466f; }
QPushButton:focus { border: 1px solid #60a5fa; }
QPushButton:disabled { color: #60758f; background: #121d2e; }
QPushButton#primary { background: #60a5fa; color: #071425; }
QPushButton#primary:hover { background: #93c5fd; }
QPushButton#primary:pressed { background: #3b82f6; }
QPushButton#primary:disabled { color: #8da1ba; background: #263c59; }
QPushButton#secondary { background: #111f34; border: 1px solid #304a6c; }
QPushButton#secondary:hover { background: #1a2e49; }
QPushButton#danger { color: #ffb5a3; background: #3e2823; }
QPushButton#danger:hover { background: #55332c; }
QPushButton#nav { text-align: left; padding: 13px 17px; font-size: 14px; background: transparent; color: #a9bbd1; border-radius: 11px; }
QPushButton#nav:hover { background: #142944; }
QPushButton#nav:checked { background: #193c63; color: #bfdbfe; }
QPushButton#segment { background: transparent; color: #9fb2cc; border-radius: 9px; padding: 10px 20px; }
QPushButton#segment:checked { background: #193c63; color: #bfdbfe; }
QPushButton#link { background: transparent; color: #7dd3fc; padding: 6px; font-size: 12px; }
QPushButton#link:hover { color: #bae6fd; background: #112d48; }
QLineEdit, QSpinBox, QTimeEdit, QComboBox { background: #0c1627; color: #eaf2ff; border: 1px solid #355372; border-radius: 8px; padding: 9px; min-height: 20px; selection-background-color: #1d4ed8; selection-color: #f7fbff; }
QLineEdit:focus, QSpinBox:focus, QTimeEdit:focus, QComboBox:focus { border: 1px solid #60a5fa; }
QLineEdit:disabled, QSpinBox:disabled, QTimeEdit:disabled, QComboBox:disabled { color: #71859f; background: #101b2d; border-color: #263a55; }
QComboBox QAbstractItemView { background: #111f34; color: #eaf2ff; border: 1px solid #3c5f85; padding: 4px; selection-background-color: #1e4e82; selection-color: #f7fbff; outline: none; }
QAbstractItemView { background: #111c2e; alternate-background-color: #172740; color: #eaf2ff; selection-background-color: #1e4e82; selection-color: #f7fbff; }
QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #496a91; border-radius: 5px; background: #0b1627; }
QCheckBox::indicator:checked { background: #60a5fa; border: 4px solid #244b78; }
QCheckBox::indicator:hover { border-color: #60a5fa; }
QProgressBar { border: none; background: #263a55; border-radius: 4px; max-height: 7px; min-height: 7px; }
QProgressBar::chunk { background: #60a5fa; border-radius: 4px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #355d83; border-radius: 3px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #4779a8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:horizontal { background: #355d83; border-radius: 3px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QMenu { background: #111f34; color: #eaf2ff; border: 1px solid #355372; padding: 5px; }
QMenu::item:selected { background: #1e4e82; color: #f7fbff; }
QMenu::item:disabled { color: #71859f; }
QToolTip { background: #18395e; color: #f7fbff; padding: 8px; border: 1px solid #4c7fb2; }
"""


def apply_theme(application):
    """Keep native controls and popup views dark, independent of desktop theme."""
    application.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BACKGROUND,
        QPalette.ColorRole.WindowText: INK,
        QPalette.ColorRole.Base: "#0c1627",
        QPalette.ColorRole.AlternateBase: "#172740",
        QPalette.ColorRole.ToolTipBase: "#18395e",
        QPalette.ColorRole.ToolTipText: "#f7fbff",
        QPalette.ColorRole.Text: INK,
        QPalette.ColorRole.Button: "#172740",
        QPalette.ColorRole.ButtonText: INK,
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: "#1d4ed8",
        QPalette.ColorRole.HighlightedText: "#f7fbff",
        QPalette.ColorRole.Link: ACCENT,
        QPalette.ColorRole.LinkVisited: "#a5b4fc",
        QPalette.ColorRole.PlaceholderText: "#8196b0",
        QPalette.ColorRole.Light: "#4779a8",
        QPalette.ColorRole.Midlight: "#355d83",
        QPalette.ColorRole.Mid: "#263c59",
        QPalette.ColorRole.Dark: "#0c1627",
        QPalette.ColorRole.Shadow: "#050914",
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#71859f"))
    application.setPalette(palette)
    if hasattr(application.styleHints(), "setColorScheme"):
        application.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    application.setStyleSheet(STYLE)


def label(text, name="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback=None, name="secondary"):
    widget = QPushButton(text)
    widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        widget.clicked.connect(callback)
    return widget


def card(name="card", margins=22):
    frame = QFrame()
    frame.setObjectName(name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(14)
    return frame, layout


def clock_text(seconds, hours=True):
    value = max(0, int(seconds))
    h, remainder = divmod(value, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if hours or h else f"{m:02d}:{s:02d}"


def human_time(seconds):
    mins = max(0, int(seconds)) // 60
    hours, mins = divmod(mins, 60)
    return f"{hours} sa {mins:02d} dk" if hours else f"{mins} dk"
