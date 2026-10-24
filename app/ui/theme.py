"""Application theme: colour tokens, generated arrow/check assets and QSS."""

from __future__ import annotations

import sys
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

DARK = {
    "bg": "#0A0D13",
    "bg_soft": "#0D1119",
    "surface": "#111622",
    "surface_alt": "#151B28",
    "surface_hover": "#1A2233",
    "sidebar": "#0C1018",
    "border": "#222B3C",
    "border_strong": "#2E3A50",
    "text": "#E9EEF8",
    "text_soft": "#C3CCDD",
    "muted": "#8C99B0",
    "dim": "#5C6980",
    "accent": "#6C8CFF",
    "accent_hover": "#7E9BFF",
    "accent_pressed": "#5A79E6",
    "accent_text": "#0A0D13",
    "accent_soft": "rgba(108, 140, 255, 0.14)",
    "accent_soft2": "rgba(108, 140, 255, 0.22)",
    "success": "#3DDC97",
    "success_soft": "rgba(61, 220, 151, 0.14)",
    "warn": "#FFB35C",
    "warn_soft": "rgba(255, 179, 92, 0.14)",
    "danger": "#FF6B7A",
    "danger_soft": "rgba(255, 107, 122, 0.14)",
    "shadow": "rgba(0, 0, 0, 0.35)",
    "scroll": "#2A3448",
    "scroll_hover": "#3A4762",
}

LIGHT = {
    "bg": "#F3F5FA",
    "bg_soft": "#EDF0F7",
    "surface": "#FFFFFF",
    "surface_alt": "#F6F8FC",
    "surface_hover": "#EEF2FA",
    "sidebar": "#FFFFFF",
    "border": "#E3E8F1",
    "border_strong": "#D2DAE8",
    "text": "#111827",
    "text_soft": "#374151",
    "muted": "#667085",
    "dim": "#98A2B3",
    "accent": "#4C6FFF",
    "accent_hover": "#3D60F0",
    "accent_pressed": "#3452D6",
    "accent_text": "#FFFFFF",
    "accent_soft": "rgba(76, 111, 255, 0.10)",
    "accent_soft2": "rgba(76, 111, 255, 0.18)",
    "success": "#12B76A",
    "success_soft": "rgba(18, 183, 106, 0.12)",
    "warn": "#F79009",
    "warn_soft": "rgba(247, 144, 9, 0.12)",
    "danger": "#F04438",
    "danger_soft": "rgba(240, 68, 56, 0.10)",
    "shadow": "rgba(16, 24, 40, 0.08)",
    "scroll": "#CDD6E4",
    "scroll_hover": "#B4C0D3",
}


def _assets_dir(mode: str) -> Path:
    from app.core.paths import cache_dir

    path = cache_dir() / "ui-assets" / mode
    path.mkdir(parents=True, exist_ok=True)
    return path


def _make_png(path: Path, size: int, draw) -> None:
    for scale in (1, 2):
        px = QPixmap(size * scale, size * scale)
        px.setDevicePixelRatio(scale)
        px.fill(Qt.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.Antialiasing, True)
        draw(painter, QRectF(0, 0, size, size))
        painter.end()
        target = path.with_name(path.stem + ("@2x" if scale == 2 else "") + ".png")
        px.save(str(target), "PNG")


def _ensure_assets(tokens: dict[str, str], mode: str) -> dict[str, str]:
    base = _assets_dir(mode)
    muted = QColor(tokens["muted"])

    chevron = base / "chevron.png"
    if not chevron.is_file():
        def draw_chevron(p: QPainter, r: QRectF) -> None:
            pen = QPen(muted, 1.6)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            path = QPainterPath()
            path.moveTo(r.width() * 0.22, r.height() * 0.38)
            path.lineTo(r.width() * 0.5, r.height() * 0.64)
            path.lineTo(r.width() * 0.78, r.height() * 0.38)
            p.drawPath(path)

        _make_png(chevron, 12, draw_chevron)

    check = base / "check.png"
    if not check.is_file():
        def draw_check(p: QPainter, r: QRectF) -> None:
            pen = QPen(QColor("#FFFFFF"), 1.9)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            path = QPainterPath()
            path.moveTo(r.width() * 0.22, r.height() * 0.52)
            path.lineTo(r.width() * 0.42, r.height() * 0.72)
            path.lineTo(r.width() * 0.80, r.height() * 0.28)
            p.drawPath(path)

        _make_png(check, 12, draw_check)

    radio = base / "radio.png"
    if not radio.is_file():
        def draw_radio(p: QPainter, r: QRectF) -> None:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(r.width() * 0.28, r.height() * 0.28,
                                 r.width() * 0.44, r.height() * 0.44))

        _make_png(radio, 12, draw_radio)

    close = base / "close.png"
    if not close.is_file():
        def draw_close(p: QPainter, r: QRectF) -> None:
            pen = QPen(muted, 1.6)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(r.width() * 0.28, r.height() * 0.28),
                       QPointF(r.width() * 0.72, r.height() * 0.72))
            p.drawLine(QPointF(r.width() * 0.72, r.height() * 0.28),
                       QPointF(r.width() * 0.28, r.height() * 0.72))

        _make_png(close, 12, draw_close)

    return {
        "chevron": chevron.as_posix(),
        "check": check.as_posix(),
        "radio": radio.as_posix(),
        "close": close.as_posix(),
    }


QSS = Template("""
* {
    outline: none;
}
QWidget {
    background: transparent;
    color: $text;
    font-size: 13px;
    font-family: "PingFang SC", "Microsoft YaHei UI", "Segoe UI", "Helvetica Neue", sans-serif;
}
QMainWindow, #RootSurface {
    background: $bg;
}
QToolTip {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 6px 8px;
}

/* ---------------- sidebar ---------------- */
#Sidebar {
    background: $sidebar;
    border-right: 1px solid $border;
}
#BrandName { font-size: 17px; font-weight: 700; letter-spacing: 0.2px; }
#BrandSub { color: $muted; font-size: 11px; }
#Sidebar Footer, #SidebarFooter { color: $dim; font-size: 11px; }
QPushButton#NavButton {
    text-align: left;
    padding: 9px 12px;
    border-radius: 9px;
    border: 1px solid transparent;
    color: $muted;
    font-size: 13.5px;
    font-weight: 500;
    background: transparent;
}
QPushButton#NavButton:hover {
    background: $surface_hover;
    color: $text;
}
QPushButton#NavButton:checked {
    background: $accent_soft;
    border: 1px solid $accent_soft2;
    color: $text;
    font-weight: 600;
}

/* ---------------- cards & text ---------------- */
#Card {
    background: $surface;
    border: 1px solid $border;
    border-radius: 14px;
}
#CardSoft {
    background: $surface_alt;
    border: 1px solid $border;
    border-radius: 12px;
}
#HeroCard {
    background: $surface;
    border: 1px solid $border;
    border-radius: 16px;
}
QLabel#PageTitle { font-size: 22px; font-weight: 700; }
QLabel#PageSub { color: $muted; font-size: 12.5px; }
QLabel#SectionTitle { font-size: 14px; font-weight: 600; color: $text; }
QLabel#SectionHint { color: $muted; font-size: 12px; }
QLabel#Muted { color: $muted; }
QLabel#Dim { color: $dim; font-size: 11.5px; }
QLabel#CardTitle { font-size: 16px; font-weight: 600; }
QLabel#Value { font-size: 15px; font-weight: 600; }
QLabel#Badge {
    background: $accent_soft;
    color: $accent;
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#PillOk { background: $success_soft; color: $success; border-radius: 9px; padding: 2px 9px; font-size: 11.5px; font-weight: 600; }
QLabel#PillWarn { background: $warn_soft; color: $warn; border-radius: 9px; padding: 2px 9px; font-size: 11.5px; font-weight: 600; }
QLabel#PillErr { background: $danger_soft; color: $danger; border-radius: 9px; padding: 2px 9px; font-size: 11.5px; font-weight: 600; }
QLabel#PillInfo { background: $surface_hover; color: $muted; border-radius: 9px; padding: 2px 9px; font-size: 11.5px; }

/* ---------------- buttons ---------------- */
QPushButton {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover { background: $surface_hover; border-color: $border_strong; }
QPushButton:pressed { background: $bg_soft; }
QPushButton:disabled { color: $dim; border-color: $border; background: $surface_alt; }
QPushButton[role="primary"] {
    background: $accent;
    color: $accent_text;
    border: 1px solid $accent;
    font-weight: 600;
}
QPushButton[role="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[role="primary"]:pressed { background: $accent_pressed; }
QPushButton[role="primary"]:disabled { background: $border; border-color: $border; color: $dim; }
QPushButton[role="ghost"] {
    background: transparent;
    border: 1px solid $border_strong;
    color: $text_soft;
}
QPushButton[role="ghost"]:hover { background: $surface_hover; color: $text; }
QPushButton[role="quiet"] {
    background: transparent;
    border: 1px solid transparent;
    color: $muted;
    padding: 6px 10px;
}
QPushButton[role="quiet"]:hover { background: $surface_hover; color: $text; }
QPushButton[role="danger"] {
    background: $danger_soft;
    color: $danger;
    border: 1px solid transparent;
}
QPushButton[role="danger"]:hover { border-color: $danger; }
QPushButton[role="chip"] {
    background: $surface_alt;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 5px 11px;
    color: $muted;
    font-size: 12px;
}
QPushButton[role="chip"]:hover { color: $text; border-color: $border_strong; }
QPushButton#IconButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px;
}
QPushButton#IconButton:hover { background: $surface_hover; }

/* ---------------- inputs ---------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 8px 11px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus { border-color: $accent; background: $surface; }
QLineEdit#UrlInput {
    background: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: 11px;
    padding: 12px 14px;
    font-size: 14px;
}
QLineEdit#UrlInput:focus { border-color: $accent; }
QLineEdit::placeholder { color: $dim; }

QComboBox {
    background: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 7px 30px 7px 11px;
    min-height: 18px;
    color: $text;
}
QComboBox:hover { border-color: $accent; }
QComboBox::drop-down { border: none; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow { image: url($chevron); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 5px;
    color: $text;
    selection-background-color: $accent_soft2;
    selection-color: $text;
    outline: none;
}

QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }

QCheckBox { spacing: 8px; color: $text_soft; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 5px;
    border: 1px solid $border_strong;
    background: $surface_alt;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked {
    background: $accent;
    border-color: $accent;
    image: url($check);
}

QRadioButton { spacing: 8px; color: $text_soft; }
QRadioButton::indicator {
    width: 16px; height: 16px; border-radius: 8px;
    border: 1px solid $border_strong; background: $surface_alt;
}
QRadioButton::indicator:checked { background: $accent; border-color: $accent; image: url($radio); }

/* ---------------- progress ---------------- */
QProgressBar {
    background: $surface_hover;
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 #9B6CFF);
}

/* ---------------- scroll ---------------- */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $scroll_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ---------------- misc ---------------- */
QSplitter::handle { background: $border; width: 1px; }
QFrame#HLine { background: $border; max-height: 1px; border: none; }
QMenu {
    background: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 5px;
    color: $text;
}
QMenu::item { padding: 7px 22px 7px 12px; border-radius: 6px; }
QMenu::item:selected { background: $accent_soft2; }
QScrollArea#PageScroll > QWidget > QWidget { background: transparent; }
""")


def apply_theme(app, mode: str = "dark") -> None:
    tokens = DARK if mode != "light" else LIGHT
    assets = _ensure_assets(tokens, "light" if mode == "light" else "dark")
    stylesheet = QSS.safe_substitute(**tokens, **assets)
    app.setStyleSheet(stylesheet)

    if sys.platform == "darwin":
        families = ["PingFang SC", "Helvetica Neue", "Arial"]
    elif sys.platform.startswith("win"):
        families = ["Microsoft YaHei UI", "Segoe UI", "Arial"]
    else:
        families = ["Noto Sans CJK SC", "DejaVu Sans", "Arial"]
    font = QFont()
    font.setFamilies(families)
    font.setPointSize(10)
    app.setFont(font)


def tokens(mode: str = "dark") -> dict[str, str]:
    return DARK if mode != "light" else LIGHT
