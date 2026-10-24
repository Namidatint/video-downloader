"""Reusable widgets: cards, thumbnails, pills, toasts, empty states."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (QByteArray, QObject, QPropertyAnimation,
                            QRectF, QSize, Qt, QTimer, QUrl, Signal)
from PySide6.QtGui import (QColor, QFontMetrics, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from app.ui import icons
from app.ui.theme import DARK


# ---------------------------------------------------------------------------
# basic building blocks
# ---------------------------------------------------------------------------
class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, *, soft: bool = False,
                 object_name: str | None = None):
        super().__init__(parent)
        self.setObjectName(object_name or ("CardSoft" if soft else "Card"))


def hline(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setObjectName("HLine")
    line.setFixedHeight(1)
    line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return line


class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str = "", size: int = 18,
                 color: str = DARK["muted"], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setIcon(icons.icon(icon_name, color, size))
        self.setIconSize(QSize(size, size))
        self.setFixedSize(size + 14, size + 14)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)


class ElidedLabel(QLabel):
    """A label that ellipsizes instead of forcing the layout wider."""

    def __init__(self, text: str = "", parent: QWidget | None = None, mode=Qt.ElideRight):
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt API)
        self._full = text or ""
        self.setToolTip(self._full if len(self._full) > 40 else "")
        super().setText(self._full)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        metrics = QFontMetrics(self.font())
        text = metrics.elidedText(self._full, self._mode, self.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.rect(), int(self.alignment()), text)
        painter.end()


class Thumbnail(QWidget):
    """Rounded thumbnail with gradient placeholder and loading animation."""

    def __init__(self, width: int = 260, height: int = 146, radius: int = 10,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._radius = radius
        self._pixmap: QPixmap | None = None
        self._placeholder_text = ""

    def set_thumbnail(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def set_placeholder(self, text: str = "") -> None:
        self._placeholder_text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.setClipPath(path)
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                                         Qt.SmoothTransformation)
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor("#1E2740"))
            gradient.setColorAt(1.0, QColor("#141A28"))
            painter.fillPath(path, gradient)
            painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
            painter.drawPath(path)
            arrow = icons.pixmap("movie", "#4B5A78", 34)
            painter.drawPixmap((self.width() - 34) // 2, (self.height() - 34) // 2 - 6, arrow)
        painter.end()


class StatusPill(QLabel):
    def __init__(self, text: str = "", kind: str = "info", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        names = {"ok": "PillOk", "warn": "PillWarn", "error": "PillErr", "info": "PillInfo"}
        self.setObjectName(names.get(kind, "PillInfo"))
        self.style().unpolish(self)
        self.style().polish(self)


class EmptyState(QWidget):
    def __init__(self, icon_name: str, title: str, subtitle: str = "",
                 action: tuple[str, Callable[[], None]] | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 40, 0, 40)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        badge = QLabel()
        badge.setPixmap(icons.pixmap(icon_name, DARK["dim"], 44))
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Muted")
            sub.setAlignment(Qt.AlignCenter)
            sub.setWordWrap(True)
            sub.setFixedWidth(470)
            sub.setMinimumHeight(54)
            layout.addWidget(sub, alignment=Qt.AlignHCenter)

        if action:
            text, callback = action
            button = QPushButton(text)
            button.setProperty("role", "ghost")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(callback)
            layout.addWidget(button, alignment=Qt.AlignCenter)


# ---------------------------------------------------------------------------
# toast notifications
# ---------------------------------------------------------------------------
class Toast(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._label = QLabel(self)
        self._label.setContentsMargins(16, 10, 16, 10)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_animated)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self.hide()

    def show_message(self, text: str, kind: str = "info", duration: int = 2600) -> None:
        colors = {
            "info": ("#151B28", DARK["text"], DARK["border_strong"]),
            "ok": (DARK["success_soft"], DARK["success"], DARK["success"]),
            "warn": (DARK["warn_soft"], DARK["warn"], DARK["warn"]),
            "error": (DARK["danger_soft"], DARK["danger"], DARK["danger"]),
        }
        bg, fg, border = colors.get(kind, colors["info"])
        self._label.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border};"
            f"border-radius: 10px; font-size: 13px;"
        )
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._effect.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(160)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(duration)

    def hide_animated(self) -> None:
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def reposition(self) -> None:
        if not self.parent():
            return
        parent = self.parentWidget()
        self.adjustSize()
        x = max(12, (parent.width() - self.width()) // 2)
        y = parent.height() - self.height() - 26
        self.move(x, y)


# ---------------------------------------------------------------------------
# thumbnail downloading
# ---------------------------------------------------------------------------
class ImageLoader(QObject):
    pixmap_ready = Signal(str, QPixmap)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._cache: dict[str, QPixmap] = {}
        self._pending: set[str] = set()

    def load(self, url: str) -> QPixmap | None:
        if not url:
            return None
        if url in self._cache:
            return self._cache[url]
        if url in self._pending:
            return None
        self._pending.add(url)
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.UserAgentHeader,
                          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        request.setRawHeader(QByteArray(b"Referer"), QByteArray(b"https://www.bilibili.com/"))
        request.setTransferTimeout(9000)
        reply = self._manager.get(request)
        reply.finished.connect(lambda: self._on_finished(url, reply))
        return None

    def _on_finished(self, url: str, reply: QNetworkReply) -> None:
        self._pending.discard(url)
        try:
            if reply.error() == QNetworkReply.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(bytes(data)):
                    self._cache[url] = pixmap
                    self.pixmap_ready.emit(url, pixmap)
        finally:
            reply.deleteLater()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def make_button(text: str, role: str = "", icon_name: str = "", *,
                parent: QWidget | None = None, on_click: Callable | None = None,
                height: int = 0) -> QPushButton:
    button = QPushButton(text, parent)
    button.setProperty("role", role)
    button.setCursor(Qt.PointingHandCursor)
    if icon_name:
        button.setIcon(icons.icon(icon_name, "#FFFFFF" if role == "primary" else DARK["muted"], 16))
        button.setIconSize(QSize(16, 16))
    if on_click:
        button.clicked.connect(on_click)
    if height:
        button.setFixedHeight(height)
    return button


def set_role(widget: QWidget, role: str) -> None:
    widget.setProperty("role", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
