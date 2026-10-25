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
    "bg": "#202020",
    "bg_soft": "#1A1A1A",
    "surface": "#2B2B2B",
    "surface_alt": "#323232",
    "surface_hover": "#3A3A3A",
    "sidebar": "#1F1F1F",
    "border": "#3D3D3D",
    "border_strong": "#5C5C5C",
    "text": "#FFFFFF",
    "text_soft": "#E4E4E4",
    "muted": "#BDBDBD",
    "dim": "#9A9A9A",
    "accent": "#4CC2FF",
    "accent_hover": "#6FD0FF",
    "accent_pressed": "#3AA9E0",
    "accent_text": "#0A0A0A",
    "accent_soft": "#1E3542",
    "accent_soft2": "#294A5C",
    "success": "#6CCB5F",
    "success_soft": "#1E3A1B",
    "warn": "#FCE100",
    "warn_soft": "#3A3310",
    "danger": "#FF99A4",
    "danger_soft": "#442726",
    "scroll": "#4A4A4A",
    "scroll_hover": "#6B6B6B",
}

LIGHT = {
    "bg": "#F3F3F3",
    "bg_soft": "#EAEAEA",
    "surface": "#FFFFFF",
    "surface_alt": "#FAFAFA",
    "surface_hover": "#E9E9E9",
    "sidebar": "#E6E6E6",
    "border": "#E1E1E1",
    "border_strong": "#ADADAD",
    "text": "#1B1B1B",
    "text_soft": "#3B3B3B",
    "muted": "#5F5F5F",
    "dim": "#767676",
    "accent": "#0078D7",
    "accent_hover": "#106EBE",
    "accent_pressed": "#005A9E",
    "accent_text": "#FFFFFF",
    "accent_soft": "#E5F1FB",
    "accent_soft2": "#CCE4F7",
    "success": "#107C10",
    "success_soft": "#DFF6DD",
    "warn": "#9D5D00",
    "warn_soft": "#FFF4CE",
    "danger": "#C42B1C",
    "danger_soft": "#FDE7E9",
    "scroll": "#C8C8C8",
    "scroll_hover": "#A6A6A6",
}

# The palette currently applied; widgets read this when they build pixmaps/icons.
active: dict[str, str] = LIGHT


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
    font-family: "Segoe UI Variable Text", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", sans-serif;
}
QMainWindow, #RootSurface { background: $bg; }

QToolTip {
    background: $surface;
    color: $text;
    border: 1px solid $border_strong;
    padding: 6px 8px;
}

/* ---------------- Windows 10 style left pane ---------------- */
#Sidebar { background: $sidebar; border-right: 1px solid $border; }
#SidebarTitle { font-size: 15px; font-weight: 600; color: $text; }
#SidebarHeaderButton {
    background: transparent;
    border: none;
    padding: 6px;
}
#SidebarHeaderButton:hover { background: $surface_hover; }
QPushButton#NavButton {
    text-align: left;
    padding: 9px 12px 9px 10px;
    border: none;
    border-left: 3px solid transparent;
    color: $text;
    font-size: 13.5px;
    font-weight: 400;
    background: transparent;
}
QPushButton#NavButton:hover { background: $surface_hover; }
QPushButton#NavButton:checked {
    background: $accent_soft;
    border-left: 3px solid $accent;
    font-weight: 600;
}
#NavSection { color: $muted; font-size: 11px; font-weight: 600; padding: 10px 12px 4px 12px; }

/* ---------------- page / cards ---------------- */
#PageScroll, QScrollArea { border: none; background: transparent; }
#Card {
    background: $surface;
    border: 1px solid $border;
    border-radius: 4px;
}
#CardSoft { background: $surface_alt; border: 1px solid $border; border-radius: 4px; }
#HeroCard { background: $surface; border: 1px solid $border; border-radius: 4px; }
#SectionHeader { font-size: 14px; font-weight: 600; color: $text; }
#SectionHint { color: $muted; font-size: 12px; }
#PageTitle { font-size: 28px; font-weight: 600; color: $text; }
#PageSub { color: $muted; font-size: 12.5px; }
#CardTitle { font-size: 15px; font-weight: 600; color: $text; }
#MediaTitle { font-size: 18px; font-weight: 600; color: $text; }
#Muted { color: $muted; }
#Dim { color: $dim; font-size: 11.5px; }
#Value { font-size: 15px; font-weight: 600; color: $text; }
#Mono { font-size: 12px; color: $text; }
#MonoDim { font-size: 11.5px; color: $muted; }

#Badge {
    background: $surface_alt;
    color: $text_soft;
    border: 1px solid $border;
    border-radius: 2px;
    padding: 1px 7px;
    font-size: 11px;
}
#PillOk, #PillWarn, #PillErr, #PillInfo {
    background: transparent;
    border: 1px solid $border_strong;
    border-radius: 2px;
    padding: 1px 7px;
    font-size: 11px;
    color: $text_soft;
}
#PillOk { color: $success; border-color: $success; }
#PillWarn { color: $warn; border-color: $warn; }
#PillErr { color: $danger; border-color: $danger; }

/* ---------------- buttons ---------------- */
QPushButton {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 7px 14px;
    font-size: 13px;
}
QPushButton:hover { background: $surface_hover; }
QPushButton:pressed { background: $bg_soft; }
QPushButton:disabled { color: $dim; border-color: $border; background: transparent; }
QPushButton[role="primary"] {
    background: $accent;
    color: $accent_text;
    border: 1px solid $accent;
    font-weight: 600;
}
QPushButton[role="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[role="primary"]:pressed { background: $accent_pressed; }
QPushButton[role="primary"]:disabled { background: $border; color: $dim; border-color: $border; }
QPushButton[role="ghost"] { background: transparent; border: 1px solid $border_strong; }
QPushButton[role="ghost"]:hover { background: $surface_hover; }
QPushButton[role="quiet"] { background: transparent; border: 1px solid transparent; color: $accent; padding: 5px 6px; }
QPushButton[role="quiet"]:hover { background: $surface_hover; }
QPushButton[role="danger"] { background: transparent; color: $danger; border: 1px solid $danger; }
QPushButton[role="danger"]:hover { background: $danger_soft; }
QPushButton[role="chip"] { background: transparent; border: 1px solid $border_strong; border-radius: 2px; padding: 3px 9px; color: $muted; font-size: 12px; }
QPushButton[role="chip"]:hover { color: $text; }
QPushButton#IconButton { background: transparent; border: 1px solid transparent; padding: 4px; border-radius: 2px; }
QPushButton#IconButton:hover { background: $surface_hover; }

/* ---------------- inputs ---------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: 2px;
    padding: 7px 10px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus { border: 2px solid $accent; padding: 6px 9px; }
QLineEdit#UrlInput { background: $surface; border: 1px solid $border_strong; border-radius: 2px; padding: 10px 12px; font-size: 14px; }
QLineEdit#UrlInput:focus { border: 2px solid $accent; padding: 9px 11px; }
QLineEdit::placeholder { color: $dim; }

QComboBox {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: 2px;
    padding: 7px 26px 7px 10px;
    min-height: 18px;
    color: $text;
}
QComboBox:hover { border-color: $text_soft; }
QComboBox::drop-down { border: none; width: 24px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow { image: url($chevron); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border_strong;
    padding: 2px;
    color: $text;
    selection-background-color: $accent_soft2;
    selection-color: $text;
    outline: none;
}
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }

QCheckBox { spacing: 8px; color: $text; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border: 1px solid $border_strong;
    border-radius: 2px;
    background: $surface;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($check); }

QRadioButton { spacing: 8px; color: $text; }
QRadioButton::indicator { width: 18px; height: 18px; border: 1px solid $border_strong; border-radius: 9px; background: $surface; }
QRadioButton::indicator:checked { background: $accent; border-color: $accent; image: url($radio); }

/* ---------------- progress ---------------- */
QProgressBar { background: $bg_soft; border: none; border-radius: 2px; height: 4px; text-align: center; color: transparent; }
QProgressBar::chunk { background: $accent; border-radius: 2px; }

/* ---------------- scrollbars ---------------- */
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $scroll_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 3px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---------------- data / misc ---------------- */
QTableWidget, QTableView {
    background: $surface;
    alternate-background-color: $surface_alt;
    border: 1px solid $border;
    gridline-color: $border;
    color: $text;
    selection-background-color: $accent_soft2;
    selection-color: $text;
}
QHeaderView::section { background: $surface_alt; color: $text_soft; border: none; border-bottom: 1px solid $border; padding: 7px; font-size: 12px; }
QDialog { background: $bg; }
QMenu { background: $surface; border: 1px solid $border_strong; padding: 3px; color: $text; }
QMenu::item { padding: 6px 20px 6px 10px; }
QMenu::item:selected { background: $accent_soft2; }
QFrame#HLine { background: $border; max-height: 1px; border: none; }
QSplitter::handle { background: $border; width: 1px; }
""")


def apply_theme(app, mode: str = "light") -> None:
    global active
    tokens = LIGHT if mode != "dark" else DARK
    active = tokens
    assets = _ensure_assets(tokens, "dark" if mode == "dark" else "light")
    app.setStyleSheet(QSS.safe_substitute(**tokens, **assets))

    if sys.platform.startswith("win"):
        families = ["Segoe UI", "Microsoft YaHei UI", "Arial"]
    elif sys.platform == "darwin":
        families = ["Segoe UI", "PingFang SC", "Helvetica Neue", "Arial"]
    else:
        families = ["Segoe UI", "Noto Sans CJK SC", "DejaVu Sans", "Arial"]
    font = QFont()
    font.setFamilies(families)
    font.setPointSize(10)
    app.setFont(font)


def tokens(mode: str = "light") -> dict[str, str]:
    return LIGHT if mode != "dark" else DARK
