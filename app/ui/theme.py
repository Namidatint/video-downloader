"""Application theme: colour tokens, runtime icon assets and the QSS system.

Design world: "reverse contact sheet / asset manifest" — warm-black ground,
paper-white ink, hairline rules, zero radius, square cells, tabular numerals.
No gradients, no shadows, no blur, no opacity animation: flat fills only, so the
UI stays cheap to repaint on low-end machines.
"""

from __future__ import annotations

import sys
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

DARK = {
    "bg": "#0B0A09",
    "bg_soft": "#080706",
    "surface": "#131110",
    "surface_alt": "#191614",
    "surface_hover": "#221F1B",
    "sidebar": "#0D0C0B",
    "border": "#2E2A25",
    "border_strong": "#4B453C",
    "text": "#F7F4ED",
    "text_soft": "#D8D2C6",
    "muted": "#A9A29A",
    "dim": "#817A70",
    "accent": "#F7F4ED",
    "accent_hover": "#FFFFFF",
    "accent_pressed": "#DCD5C8",
    "accent_text": "#0B0A09",
    "accent_soft": "#26221D",
    "accent_soft2": "#332D25",
    "success": "#4CD98C",
    "success_soft": "#11251A",
    "warn": "#F2B24A",
    "warn_soft": "#2A1F0D",
    "danger": "#FF6E60",
    "danger_soft": "#2C1411",
    "scroll": "#3A352D",
    "scroll_hover": "#544C41",
}

LIGHT = {
    "bg": "#F0ECE3",
    "bg_soft": "#E7E1D5",
    "surface": "#FAF7F0",
    "surface_alt": "#F2EDE3",
    "surface_hover": "#E7E0D3",
    "sidebar": "#EDE8DE",
    "border": "#D3CBBB",
    "border_strong": "#A79D8D",
    "text": "#141210",
    "text_soft": "#3A352E",
    "muted": "#5F584E",
    "dim": "#867E72",
    "accent": "#141210",
    "accent_hover": "#2C2722",
    "accent_pressed": "#000000",
    "accent_text": "#FAF7F0",
    "accent_soft": "#E4DCCD",
    "accent_soft2": "#D6CCBA",
    "success": "#0E7A4A",
    "success_soft": "#DCEEE3",
    "warn": "#8F5400",
    "warn_soft": "#F4E6CE",
    "danger": "#B42318",
    "danger_soft": "#F6DCD8",
    "scroll": "#C2B8A6",
    "scroll_hover": "#A79C8A",
}

# The palette currently applied; widgets read this when they build pixmaps/icons.
active: dict[str, str] = DARK


def color(key: str) -> str:
    return active.get(key, DARK.get(key, "#F7F4ED"))


def _assets_dir(mode: str) -> Path:
    from app.core.paths import cache_dir

    # Versioned so stale assets from the previous rounded design are never reused.
    path = cache_dir() / "ui-assets-v2" / mode
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
    mark = QColor(tokens["accent_text"])

    chevron = base / "chevron.png"
    if not chevron.is_file():
        def draw_chevron(p: QPainter, r: QRectF) -> None:
            pen = QPen(muted, 1.5)
            pen.setCapStyle(Qt.FlatCap)
            pen.setJoinStyle(Qt.MiterJoin)
            p.setPen(pen)
            path = QPainterPath()
            path.moveTo(r.width() * 0.24, r.height() * 0.38)
            path.lineTo(r.width() * 0.5, r.height() * 0.64)
            path.lineTo(r.width() * 0.76, r.height() * 0.38)
            p.drawPath(path)

        _make_png(chevron, 12, draw_chevron)

    check = base / "check.png"
    if not check.is_file():
        def draw_check(p: QPainter, r: QRectF) -> None:
            pen = QPen(mark, 1.8)
            pen.setCapStyle(Qt.SquareCap)
            pen.setJoinStyle(Qt.MiterJoin)
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
            p.setBrush(mark)
            # A small square, not a dot: the whole system has no curves.
            p.drawRect(QRectF(r.width() * 0.30, r.height() * 0.30,
                              r.width() * 0.40, r.height() * 0.40))

        _make_png(radio, 12, draw_radio)

    close = base / "close.png"
    if not close.is_file():
        def draw_close(p: QPainter, r: QRectF) -> None:
            pen = QPen(muted, 1.5)
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            p.drawLine(QPointF(r.width() * 0.30, r.height() * 0.30),
                       QPointF(r.width() * 0.70, r.height() * 0.70))
            p.drawLine(QPointF(r.width() * 0.70, r.height() * 0.30),
                       QPointF(r.width() * 0.30, r.height() * 0.70))

        _make_png(close, 12, draw_close)

    return {
        "chevron": chevron.as_posix(),
        "check": check.as_posix(),
        "radio": radio.as_posix(),
        "close": close.as_posix(),
    }


QSS = Template("""
* { outline: none; }
QWidget {
    background: transparent;
    color: $text;
    font-size: 13px;
    font-family: "PingFang SC", "Microsoft YaHei UI", "Segoe UI", "Helvetica Neue", sans-serif;
}
QMainWindow, #RootSurface { background: $bg; }

QToolTip {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border_strong;
    padding: 5px 8px;
}

/* ---------------- rail ---------------- */
#Sidebar { background: $sidebar; border-right: 1px solid $border; }
#BrandName { font-size: 17px; font-weight: 700; color: $text; }
#BrandSub { color: $muted; font-size: 11px; }
QPushButton#NavButton {
    text-align: left;
    padding: 9px 12px;
    border: 1px solid transparent;
    color: $muted;
    font-size: 13.5px;
    font-weight: 500;
    background: transparent;
}
QPushButton#NavButton:hover { background: $surface_hover; color: $text; }
QPushButton#NavButton:checked {
    background: $accent;
    border: 1px solid $accent;
    color: $accent_text;
    font-weight: 600;
}

/* ---------------- panels ---------------- */
#Card { background: $surface; border: 1px solid $border; }
#CardSoft { background: transparent; border: 1px solid $border; }
#HeroCard { background: $surface; border: 1px solid $border_strong; }

QLabel#PageTitle { font-size: 26px; font-weight: 700; color: $text; }
QLabel#PageSub { color: $muted; font-size: 12.5px; }
QLabel#SectionTitle { font-size: 13px; font-weight: 600; color: $text; }
QLabel#SectionHint { color: $muted; font-size: 12px; }
QLabel#Muted { color: $muted; }
QLabel#Dim { color: $dim; font-size: 11.5px; }
QLabel#CardTitle { font-size: 15px; font-weight: 600; color: $text; }
QLabel#MediaTitle { font-size: 17px; font-weight: 600; color: $text; }
QLabel#Mono {
    font-family: monospace;
    font-size: 12px;
    color: $text;
}
QLabel#MonoDim {
    font-family: monospace;
    font-size: 11.5px;
    color: $muted;
}
QLabel#Value { font-size: 15px; font-weight: 600; color: $text; }

QLabel#Badge {
    background: transparent;
    color: $text_soft;
    border: 1px solid $border_strong;
    padding: 1px 7px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#PillOk, QLabel#PillWarn, QLabel#PillErr, QLabel#PillInfo {
    background: transparent;
    padding: 1px 7px;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid $border_strong;
    color: $muted;
}
QLabel#PillOk { color: $success; border-color: $success; }
QLabel#PillWarn { color: $warn; border-color: $warn; }
QLabel#PillErr { color: $danger; border-color: $danger; }

/* ---------------- buttons ---------------- */
QPushButton {
    background: transparent;
    color: $text_soft;
    border: 1px solid $border_strong;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover { background: $surface_hover; color: $text; }
QPushButton:pressed { background: $surface_alt; }
QPushButton:disabled { color: $dim; border-color: $border; }
QPushButton[role="primary"] {
    background: $accent;
    color: $accent_text;
    border: 1px solid $accent;
    font-weight: 600;
}
QPushButton[role="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[role="primary"]:pressed { background: $accent_pressed; }
QPushButton[role="primary"]:disabled { background: $surface_alt; color: $dim; border-color: $border; }
QPushButton[role="ghost"] { background: transparent; border: 1px solid $border_strong; color: $text_soft; }
QPushButton[role="ghost"]:hover { background: $surface_hover; color: $text; }
QPushButton[role="quiet"] {
    background: transparent;
    border: 1px solid transparent;
    color: $muted;
    padding: 6px 8px;
}
QPushButton[role="quiet"]:hover { background: $surface_hover; color: $text; }
QPushButton[role="danger"] {
    background: transparent;
    color: $danger;
    border: 1px solid $danger;
}
QPushButton[role="danger"]:hover { background: $danger_soft; }
QPushButton[role="chip"] {
    background: transparent;
    border: 1px solid $border_strong;
    padding: 4px 9px;
    color: $muted;
    font-size: 12px;
}
QPushButton[role="chip"]:hover { color: $text; border-color: $text_soft; }
QPushButton#IconButton {
    background: transparent;
    border: 1px solid transparent;
    padding: 4px;
}
QPushButton#IconButton:hover { background: $surface_hover; }

/* ---------------- inputs ---------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background: $surface_alt;
    border: 1px solid $border_strong;
    padding: 8px 10px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus { border-color: $accent; background: $surface; }
QLineEdit:disabled { color: $dim; }
QLineEdit#UrlInput {
    background: $bg_soft;
    border: 1px solid $border_strong;
    padding: 11px 12px;
    font-size: 14px;
}
QLineEdit#UrlInput:focus { border-color: $accent; }
QLineEdit::placeholder { color: $dim; }

QComboBox {
    background: $surface_alt;
    border: 1px solid $border_strong;
    padding: 7px 26px 7px 10px;
    min-height: 18px;
    color: $text;
}
QComboBox:hover { border-color: $text_soft; }
QComboBox::drop-down { border: none; width: 24px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow { image: url($chevron); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $surface_alt;
    border: 1px solid $border_strong;
    padding: 2px;
    color: $text;
    selection-background-color: $accent_soft2;
    selection-color: $text;
    outline: none;
}

QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }

QCheckBox { spacing: 8px; color: $text_soft; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid $border_strong;
    background: $surface_alt;
}
QCheckBox::indicator:hover { border-color: $text_soft; }
QCheckBox::indicator:checked {
    background: $accent;
    border-color: $accent;
    image: url($check);
}

QRadioButton { spacing: 8px; color: $text_soft; }
QRadioButton::indicator {
    width: 15px; height: 15px;
    border: 1px solid $border_strong;
    background: $surface_alt;
}
QRadioButton::indicator:checked { background: $accent; border-color: $accent; image: url($radio); }

/* ---------------- progress ---------------- */
QProgressBar {
    background: $surface_hover;
    border: none;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background: $accent; }

/* ---------------- scroll ---------------- */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $scroll_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: $scroll; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---------------- data ---------------- */
QTableWidget, QTableView {
    background: $surface;
    alternate-background-color: $surface_alt;
    border: 1px solid $border;
    gridline-color: $border;
    color: $text;
    selection-background-color: $accent_soft2;
    selection-color: $text;
}
QTableWidget::item { padding: 5px 7px; border-bottom: 1px solid $border; }
QHeaderView::section {
    background: $surface_alt;
    color: $muted;
    border: none;
    border-bottom: 1px solid $border;
    padding: 7px;
    font-size: 11px;
    font-weight: 600;
}
QTableCornerButton::section { background: $surface_alt; border: none; }

/* ---------------- misc ---------------- */
QSplitter::handle { background: $border; width: 1px; }
QFrame#HLine { background: $border; max-height: 1px; border: none; }
QMenu { background: $surface_alt; border: 1px solid $border_strong; padding: 3px; color: $text; }
QMenu::item { padding: 6px 20px 6px 10px; }
QMenu::item:selected { background: $accent_soft2; }
QDialog { background: $bg; }
""")


def apply_theme(app, mode: str = "dark") -> None:
    global active
    tokens = LIGHT if mode == "light" else DARK
    active = tokens
    assets = _ensure_assets(tokens, "light" if mode == "light" else "dark")
    app.setStyleSheet(QSS.safe_substitute(**tokens, **assets))

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
    return LIGHT if mode == "light" else DARK
