"""Vector icons drawn with QPainter — no external assets, crisp on Retina."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_ICONS = {
    "download", "list", "clock", "pulse", "gear", "play", "pause", "folder",
    "trash", "copy", "refresh", "search", "close", "check", "external", "link",
    "sparkle", "movie", "music", "subtitles", "info", "warn", "error", "plus",
}


def _draw(name: str, painter: QPainter, rect: QRectF, color: QColor) -> None:
    w, h = rect.width(), rect.height()
    pen = QPen(color, max(1.4, w * 0.085))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    path = QPainterPath()

    if name == "download":
        path.moveTo(w * 0.5, h * 0.14)
        path.lineTo(w * 0.5, h * 0.62)
        path.moveTo(w * 0.26, h * 0.40)
        path.lineTo(w * 0.5, h * 0.64)
        path.lineTo(w * 0.74, h * 0.40)
        painter.drawPath(path)
        path2 = QPainterPath()
        path2.moveTo(w * 0.18, h * 0.80)
        path2.lineTo(w * 0.82, h * 0.80)
        painter.drawPath(path2)
    elif name == "list":
        for y in (0.26, 0.50, 0.74):
            path = QPainterPath()
            path.moveTo(w * 0.16, h * y)
            path.lineTo(w * 0.84, h * y)
            painter.drawPath(path)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(w * 0.08, h * y), w * 0.03, w * 0.03)
            painter.setBrush(Qt.NoBrush)
    elif name == "clock":
        painter.drawEllipse(QRectF(w * 0.13, h * 0.13, w * 0.74, h * 0.74))
        path = QPainterPath()
        path.moveTo(w * 0.5, h * 0.30)
        path.lineTo(w * 0.5, h * 0.53)
        path.lineTo(w * 0.68, h * 0.64)
        painter.drawPath(path)
    elif name == "pulse":
        path = QPainterPath()
        path.moveTo(w * 0.08, h * 0.55)
        path.lineTo(w * 0.28, h * 0.55)
        path.lineTo(w * 0.40, h * 0.25)
        path.lineTo(w * 0.58, h * 0.78)
        path.lineTo(w * 0.70, h * 0.55)
        path.lineTo(w * 0.92, h * 0.55)
        painter.drawPath(path)
    elif name == "gear":
        painter.drawEllipse(QRectF(w * 0.30, h * 0.30, w * 0.40, h * 0.40))
        import math

        for i in range(8):
            angle = math.radians(i * 45)
            import math as _m

            x1 = w * 0.5 + _m.cos(angle) * w * 0.26
            y1 = h * 0.5 + _m.sin(angle) * h * 0.26
            x2 = w * 0.5 + _m.cos(angle) * w * 0.40
            y2 = h * 0.5 + _m.sin(angle) * h * 0.40
            path = QPainterPath()
            path.moveTo(x1, y1)
            path.lineTo(x2, y2)
            painter.drawPath(path)
    elif name == "play":
        path.moveTo(w * 0.32, h * 0.18)
        path.lineTo(w * 0.82, h * 0.50)
        path.lineTo(w * 0.32, h * 0.82)
        path.closeSubpath()
        painter.setBrush(color)
        painter.drawPath(path)
    elif name == "pause":
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(w * 0.26, h * 0.20, w * 0.16, h * 0.60), 2, 2)
        painter.drawRoundedRect(QRectF(w * 0.58, h * 0.20, w * 0.16, h * 0.60), 2, 2)
    elif name == "folder":
        path.moveTo(w * 0.10, h * 0.30)
        path.lineTo(w * 0.10, h * 0.78)
        path.lineTo(w * 0.90, h * 0.78)
        path.lineTo(w * 0.90, h * 0.34)
        path.lineTo(w * 0.48, h * 0.34)
        path.lineTo(w * 0.40, h * 0.22)
        path.lineTo(w * 0.10, h * 0.22)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "trash":
        path.moveTo(w * 0.16, h * 0.28)
        path.lineTo(w * 0.84, h * 0.28)
        path.moveTo(w * 0.30, h * 0.28)
        path.lineTo(w * 0.34, h * 0.14)
        path.lineTo(w * 0.66, h * 0.14)
        path.lineTo(w * 0.70, h * 0.28)
        path.moveTo(w * 0.24, h * 0.30)
        path.lineTo(w * 0.30, h * 0.88)
        path.lineTo(w * 0.70, h * 0.88)
        path.lineTo(w * 0.76, h * 0.30)
        painter.drawPath(path)
    elif name == "copy":
        painter.drawRoundedRect(QRectF(w * 0.30, h * 0.14, w * 0.46, h * 0.50), 3, 3)
        painter.drawRoundedRect(QRectF(w * 0.18, h * 0.32, w * 0.46, h * 0.52), 3, 3)
    elif name == "refresh":
        path.arcMoveTo(QRectF(w * 0.18, h * 0.18, w * 0.64, h * 0.64), 40)
        path.arcTo(QRectF(w * 0.18, h * 0.18, w * 0.64, h * 0.64), 40, -280)
        painter.drawPath(path)
        path2 = QPainterPath()
        path2.moveTo(w * 0.78, h * 0.16)
        path2.lineTo(w * 0.86, h * 0.40)
        path2.lineTo(w * 0.61, h * 0.36)
        painter.drawPath(path2)
    elif name == "search":
        painter.drawEllipse(QRectF(w * 0.14, h * 0.14, w * 0.50, h * 0.50))
        path.moveTo(w * 0.60, h * 0.60)
        path.lineTo(w * 0.86, h * 0.86)
        painter.drawPath(path)
    elif name == "close":
        path.moveTo(w * 0.24, h * 0.24)
        path.lineTo(w * 0.76, h * 0.76)
        path.moveTo(w * 0.76, h * 0.24)
        path.lineTo(w * 0.24, h * 0.76)
        painter.drawPath(path)
    elif name == "check":
        path.moveTo(w * 0.20, h * 0.52)
        path.lineTo(w * 0.42, h * 0.74)
        path.lineTo(w * 0.82, h * 0.26)
        painter.drawPath(path)
    elif name == "external":
        path.moveTo(w * 0.42, h * 0.24)
        path.lineTo(w * 0.20, h * 0.24)
        path.lineTo(w * 0.20, h * 0.80)
        path.lineTo(w * 0.76, h * 0.80)
        path.lineTo(w * 0.76, h * 0.58)
        painter.drawPath(path)
        path2 = QPainterPath()
        path2.moveTo(w * 0.52, h * 0.48)
        path2.lineTo(w * 0.86, h * 0.14)
        path2.moveTo(w * 0.62, h * 0.14)
        path2.lineTo(w * 0.86, h * 0.14)
        path2.lineTo(w * 0.86, h * 0.38)
        painter.drawPath(path2)
    elif name == "link":
        path.moveTo(w * 0.42, h * 0.58)
        path.lineTo(w * 0.58, h * 0.42)
        path.moveTo(w * 0.30, h * 0.50)
        path.arcTo(QRectF(w * 0.10, h * 0.36, w * 0.36, h * 0.36), 120, 240)
        path.moveTo(w * 0.70, h * 0.50)
        path.arcTo(QRectF(w * 0.54, h * 0.28, w * 0.36, h * 0.36), -60, 240)
        painter.drawPath(path)
    elif name == "sparkle":
        path.moveTo(w * 0.50, h * 0.10)
        path.lineTo(w * 0.60, h * 0.38)
        path.lineTo(w * 0.90, h * 0.50)
        path.lineTo(w * 0.60, h * 0.62)
        path.lineTo(w * 0.50, h * 0.90)
        path.lineTo(w * 0.40, h * 0.62)
        path.lineTo(w * 0.10, h * 0.50)
        path.lineTo(w * 0.40, h * 0.38)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "movie":
        painter.drawRoundedRect(QRectF(w * 0.12, h * 0.24, w * 0.76, h * 0.52), 4, 4)
        path.moveTo(w * 0.36, h * 0.38)
        path.lineTo(w * 0.36, h * 0.62)
        path.lineTo(w * 0.58, h * 0.50)
        path.closeSubpath()
        painter.setBrush(color)
        painter.drawPath(path)
    elif name == "music":
        path.moveTo(w * 0.40, h * 0.24)
        path.lineTo(w * 0.40, h * 0.68)
        path.moveTo(w * 0.40, h * 0.24)
        path.lineTo(w * 0.78, h * 0.16)
        path.lineTo(w * 0.78, h * 0.60)
        painter.drawPath(path)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(w * 0.32, h * 0.70), w * 0.10, h * 0.09)
        painter.drawEllipse(QPointF(w * 0.70, h * 0.62), w * 0.10, h * 0.09)
    elif name == "subtitles":
        painter.drawRoundedRect(QRectF(w * 0.12, h * 0.24, w * 0.76, h * 0.52), 4, 4)
        for x in (0.26, 0.50, 0.70):
            path = QPainterPath()
            path.moveTo(w * x, h * 0.44)
            path.lineTo(w * (x + 0.10), h * 0.44)
            painter.drawPath(path)
        for x in (0.26, 0.56):
            path = QPainterPath()
            path.moveTo(w * x, h * 0.58)
            path.lineTo(w * (x + 0.14), h * 0.58)
            painter.drawPath(path)
    elif name == "info":
        painter.drawEllipse(QRectF(w * 0.14, h * 0.14, w * 0.72, h * 0.72))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(w * 0.5, h * 0.32), w * 0.045, w * 0.045)
        path = QPainterPath()
        path.moveTo(w * 0.5, h * 0.44)
        path.lineTo(w * 0.5, h * 0.70)
        painter.drawPath(path)
    elif name == "warn":
        path.moveTo(w * 0.50, h * 0.12)
        path.lineTo(w * 0.92, h * 0.84)
        path.lineTo(w * 0.08, h * 0.84)
        path.closeSubpath()
        painter.drawPath(path)
        path2 = QPainterPath()
        path2.moveTo(w * 0.5, h * 0.38)
        path2.lineTo(w * 0.5, h * 0.58)
        painter.drawPath(path2)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(w * 0.5, h * 0.70), w * 0.04, w * 0.04)
    elif name == "error":
        painter.drawEllipse(QRectF(w * 0.14, h * 0.14, w * 0.72, h * 0.72))
        path.moveTo(w * 0.34, h * 0.34)
        path.lineTo(w * 0.66, h * 0.66)
        path.moveTo(w * 0.66, h * 0.34)
        path.lineTo(w * 0.34, h * 0.66)
        painter.drawPath(path)
    elif name == "plus":
        path.moveTo(w * 0.5, h * 0.18)
        path.lineTo(w * 0.5, h * 0.82)
        path.moveTo(w * 0.18, h * 0.5)
        path.lineTo(w * 0.82, h * 0.5)
        painter.drawPath(path)


def pixmap(name: str, color: str | QColor = "#E8EDF7", size: int = 20,
           dpr: float = 2.0) -> QPixmap:
    if name not in _ICONS:
        name = "info"
    qcolor = QColor(color) if isinstance(color, str) else color
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing, True)
    _draw(name, painter, QRectF(0, 0, size, size), qcolor)
    painter.end()
    return px


def icon(name: str, color: str | QColor = "#E8EDF7", size: int = 20) -> QIcon:
    return QIcon(pixmap(name, color, size))


def app_pixmap(size: int = 256) -> QPixmap:
    """The GlowDL mark: a square contact-sheet cell, paper ink on warm black."""
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing, False)
    rect = QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92)
    painter.fillRect(rect, QColor("#0B0A09"))
    painter.setPen(QPen(QColor("#4B453C").lighter(115), max(1.0, size * 0.012)))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(rect.adjusted(0, 0, -1, -1))

    # paper-white download glyph
    pen = QPen(QColor("#F7F4ED"), max(1.0, size * 0.072))
    pen.setCapStyle(Qt.FlatCap)
    pen.setJoinStyle(Qt.MiterJoin)
    painter.setPen(pen)
    cx = size * 0.5
    path = QPainterPath()
    path.moveTo(cx, size * 0.23)
    path.lineTo(cx, size * 0.56)
    path.moveTo(size * 0.35, size * 0.43)
    path.lineTo(cx, size * 0.58)
    path.lineTo(size * 0.65, size * 0.43)
    painter.drawPath(path)
    path2 = QPainterPath()
    path2.moveTo(size * 0.31, size * 0.72)
    path2.lineTo(size * 0.69, size * 0.72)
    painter.drawPath(path2)

    # one amber registration square — the only colour in the mark
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#F2B24A"))
    painter.drawRect(QRectF(size * 0.70, size * 0.14, size * 0.09, size * 0.09))

    painter.end()
    return px


def app_icon(size: int = 256) -> QIcon:
    icon_ = QIcon()
    for s in (16, 32, 64, 128, 256, 512):
        icon_.addPixmap(app_pixmap(s))
    return icon_
