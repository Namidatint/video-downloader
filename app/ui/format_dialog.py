"""Dialog listing every raw format yt-dlp discovered."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.core import formats as fmt
from app.core import paths
from app.ui import widgets


class FormatsDialog(QDialog):
    def __init__(self, info: dict[str, Any] | None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("全部可用格式")
        self.resize(780, 520)
        self._rows = fmt.classify_formats(info)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel(f"共 {len(self._rows)} 个格式（按清晰度排序）")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        hint = QLabel("双击任意行可复制 format id，粘贴到设置页的“自定义格式”配合使用，例如 137+140。")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        table = QTableWidget(len(self._rows), 7)
        table.setHorizontalHeaderLabels(["类型", "分辨率", "帧率", "视频编码", "音频编码", "大小", "format id"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)

        for row_index, row in enumerate(self._rows):
            values = [
                "音频" if row.is_audio else "视频",
                row.resolution,
                f"{row.fps:.0f}" if row.fps else "—",
                row.vcodec if not row.is_audio else "—",
                row.acodec,
                paths.human_size(row.filesize),
                row.format_id,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row_index, col, item)

        def copy_id() -> None:
            row = table.currentRow()
            if 0 <= row < len(self._rows):
                QGuiApplication.clipboard().setText(self._rows[row].format_id)

        table.cellDoubleClicked.connect(lambda *_: copy_id())
        layout.addWidget(table, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = widgets.make_button("关闭", "primary", on_click=self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)
