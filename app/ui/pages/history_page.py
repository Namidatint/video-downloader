"""History page: everything downloaded, with reveal and re-download actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget)

from app.core import paths
from app.core.history import HistoryEntry
from app.ui import icons, widgets
from app.ui.theme import DARK


class HistoryRow(QFrame):
    reveal_requested = Signal(object)
    redownload_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, entry: HistoryEntry, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.entry = entry
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        badge = QLabel()
        badge.setPixmap(icons.pixmap("movie", DARK["accent"], 20))
        badge.setFixedWidth(24)
        layout.addWidget(badge, alignment=Qt.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        title = widgets.ElidedLabel(entry.title or entry.url)
        title.setObjectName("CardTitle")
        text_box.addWidget(title)
        meta = f"{entry.site or '视频'} · {entry.when}"
        if entry.filesize:
            meta += f" · {paths.human_size(entry.filesize)}"
        sub = widgets.ElidedLabel(meta)
        sub.setObjectName("Dim")
        text_box.addWidget(sub)
        layout.addLayout(text_box, 1)

        folder_btn = widgets.IconButton("folder", "在文件夹中显示", 17, DARK["muted"])
        folder_btn.clicked.connect(lambda: self.reveal_requested.emit(entry))
        layout.addWidget(folder_btn)

        again = widgets.make_button("重新下载", "ghost", "download")
        again.clicked.connect(lambda: self.redownload_requested.emit(entry))
        layout.addWidget(again)

        delete = widgets.IconButton("trash", "从历史中移除", 16, DARK["dim"])
        delete.clicked.connect(lambda: self.delete_requested.emit(entry))
        layout.addWidget(delete)


class HistoryPage(QWidget):
    redownload_requested = Signal(str, str, str)  # url, title, preset
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._entries: list[HistoryEntry] = []
        self._filter = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("下载历史")
        title.setObjectName("PageTitle")
        self.sub = QLabel("完成的任务会记录在这里")
        self.sub.setObjectName("PageSub")
        box.addWidget(title)
        box.addWidget(self.sub)
        header.addLayout(box)
        header.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索标题或站点…")
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(self._on_search)
        header.addWidget(self.search)

        self.clear_btn = widgets.make_button("清空历史", "ghost", "trash")
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        header.addWidget(self.clear_btn)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(container)
        root.addWidget(self.scroll, 1)
        self._container = container

        self.empty = widgets.EmptyState("clock", "还没有下载记录",
                                        "完成第一个下载后，这里会保存标题、站点、画质与文件位置。")
        root.addWidget(self.empty, 1)

    def set_entries(self, entries: list[HistoryEntry]) -> None:
        self._entries = entries
        self._rebuild()

    def _on_search(self, text: str) -> None:
        self._filter = text.strip().lower()
        self._rebuild()

    def _rebuild(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        entries = [
            e for e in self._entries
            if not self._filter
            or self._filter in (e.title or "").lower()
            or self._filter in (e.site or "").lower()
        ]
        for entry in entries:
            row = HistoryRow(entry, self._container)
            row.reveal_requested.connect(self._reveal)
            row.delete_requested.connect(self._delete)
            row.redownload_requested.connect(self._redownload)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)

        has = bool(entries)
        self.scroll.setVisible(has)
        self.empty.setVisible(not has)
        if not self._entries:
            self.empty.setVisible(True)
        self.sub.setText(f"共 {len(self._entries)} 条记录" if self._entries else "完成的任务会记录在这里")
        self.clear_btn.setEnabled(bool(self._entries))

    def _reveal(self, entry: HistoryEntry) -> None:
        if entry.filepath:
            paths.open_in_file_manager(entry.filepath)

    def _redownload(self, entry: HistoryEntry) -> None:
        self.redownload_requested.emit(entry.url, entry.title, entry.preset)

    def _delete(self, entry: HistoryEntry) -> None:
        self._entries = [e for e in self._entries if e is not entry]
        self._rebuild()
        # The store is owned by MainWindow; tell it by re-emitting a deleted signal.
        self.entry_deleted.emit(entry)

    entry_deleted = Signal(object)
