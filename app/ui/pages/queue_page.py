"""Queue page: live task cards with progress, pause, retry and reveal."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
                               QVBoxLayout, QWidget)

from app.core import formats as fmt
from app.core import paths
from app.core.tasks import (CANCELLED, DONE, FAILED, POSTPROCESS, QUEUED, RUNNING,
                            DownloadTask)
from app.ui import theme, widgets


class TaskCard(QFrame):
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    folder_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, task: DownloadTask, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.task_id = task.id
        self._build_ui()
        self.update_task(task)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.thumb = widgets.Thumbnail(112, 63, 0)
        top.addWidget(self.thumb, alignment=Qt.AlignTop)

        middle = QVBoxLayout()
        middle.setSpacing(5)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.title_label = widgets.ElidedLabel("")
        self.title_label.setObjectName("CardTitle")
        title_row.addWidget(self.title_label, 1)
        self.pill = widgets.StatusPill("排队中", "info")
        title_row.addWidget(self.pill, alignment=Qt.AlignTop)
        middle.addLayout(title_row)

        self.meta_label = widgets.ElidedLabel("")
        self.meta_label.setObjectName("Dim")
        middle.addWidget(self.meta_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(7)
        middle.addWidget(self.progress)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        self.stat_label = QLabel("")
        self.stat_label.setObjectName("Dim")
        bottom.addWidget(self.stat_label, 1)

        self.pause_btn = widgets.make_button("暂停", "quiet", "pause")
        self.pause_btn.clicked.connect(lambda: self.cancel_requested.emit(self.task_id))
        bottom.addWidget(self.pause_btn)

        self.retry_btn = widgets.make_button("重试", "ghost", "refresh")
        self.retry_btn.clicked.connect(lambda: self.retry_requested.emit(self.task_id))
        bottom.addWidget(self.retry_btn)

        self.folder_btn = widgets.make_button("打开文件夹", "ghost", "folder")
        self.folder_btn.clicked.connect(lambda: self.folder_requested.emit(self.task_id))
        bottom.addWidget(self.folder_btn)

        self.remove_btn = widgets.IconButton("close", "移除", 14, theme.active["dim"])
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.task_id))
        bottom.addWidget(self.remove_btn)

        middle.addLayout(bottom)
        top.addLayout(middle, 1)
        root.addLayout(top)

    # ------------------------------------------------------------- update
    def _style_progress(self, status: str) -> None:
        chunk = {
            FAILED: theme.active["danger"],
            CANCELLED: theme.active["warn"],
            DONE: theme.active["success"],
        }.get(status, theme.active["accent"])
        self.progress.setStyleSheet(
            "QProgressBar { background: %s; border: none; }"
            "QProgressBar::chunk { background: %s; }" % (theme.active["surface_hover"], chunk)
        )

    def update_task(self, task: DownloadTask) -> None:
        self.title_label.setText(task.display_title)
        self.thumb.set_placeholder("")
        meta_bits = [task.site or "视频", fmt.get_preset(task.preset).label]
        if task.playlist:
            meta_bits.append("播放列表")
        self.meta_label.setText(" · ".join(meta_bits))

        if task.status in (RUNNING, POSTPROCESS, DONE, FAILED, CANCELLED):
            self.progress.setValue(int(task.progress))
        else:
            self.progress.setValue(0)
        self._style_progress(task.status)

        if task.status == RUNNING:
            self.pill.setText(task.status_label)
            self.pill.set_kind("info")
            progress_text = f"{task.progress:.1f}%"
            if task.total:
                progress_text += f" · {paths.human_size(task.downloaded)} / {paths.human_size(task.total)}"
            if task.speed:
                progress_text += f" · {paths.human_speed(task.speed)}"
            if task.eta:
                progress_text += f" · 剩余 {paths.human_eta(task.eta)}"
            self.stat_label.setText(progress_text)
        elif task.status == POSTPROCESS:
            self.pill.setText("处理中")
            self.pill.set_kind("info")
            self.stat_label.setText("正在合并音视频 / 写入元数据…")
        elif task.status == DONE:
            self.pill.setText("已完成")
            self.pill.set_kind("ok")
            size = ""
            if task.filepaths:
                try:
                    import os

                    size = " · " + paths.human_size(os.path.getsize(task.filepaths[0]))
                except OSError:
                    size = ""
            self.stat_label.setText(f"已保存{size}")
        elif task.status == FAILED:
            self.pill.setText("失败")
            self.pill.set_kind("error")
            detail = task.problem.title if task.problem else "下载失败"
            self.stat_label.setText(detail)
        elif task.status == CANCELLED:
            self.pill.setText("已暂停" if task.extra.get("user_paused") else "已取消")
            self.pill.set_kind("warn")
            self.stat_label.setText("已下载的分片会保留，点击重试可续传")
        else:
            self.pill.setText("排队中")
            self.pill.set_kind("info")
            self.stat_label.setText("等待空闲下载位…")

        active = task.status in (QUEUED, RUNNING, POSTPROCESS)
        self.pause_btn.setVisible(active)
        self.pause_btn.setEnabled(task.status == RUNNING)
        self.retry_btn.setVisible(task.status in (FAILED, CANCELLED, DONE))
        self.retry_btn.setText("重新下载" if task.status == DONE else "重试")
        self.folder_btn.setVisible(task.status == DONE and bool(task.filepaths))
        self.remove_btn.setVisible(task.status in (DONE, FAILED, CANCELLED))


class QueuePage(QWidget):
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    folder_requested = Signal(str)
    clear_finished_requested = Signal()
    pause_all_requested = Signal()
    retry_failed_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cards: dict[str, TaskCard] = {}
        self._tasks: dict[str, DownloadTask] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("队列")
        title.setObjectName("PageTitle")
        self.sub_label = QLabel("同时下载 2 个任务")
        self.sub_label.setObjectName("PageSub")
        box.addWidget(title)
        box.addWidget(self.sub_label)
        header.addLayout(box)
        header.addStretch(1)

        self.pause_all_btn = widgets.make_button("全部暂停", "ghost", "pause")
        self.pause_all_btn.clicked.connect(self.pause_all_requested.emit)
        header.addWidget(self.pause_all_btn)
        self.retry_failed_btn = widgets.make_button("重试失败", "ghost", "refresh")
        self.retry_failed_btn.clicked.connect(self.retry_failed_requested.emit)
        header.addWidget(self.retry_failed_btn)
        self.clear_btn = widgets.make_button("清除已完成", "ghost", "trash")
        self.clear_btn.clicked.connect(self.clear_finished_requested.emit)
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

        self.empty = widgets.EmptyState(
            "list", "队列是空的",
            "在「下载」页粘贴链接并点击“开始下载”，任务会出现在这里。",
        )
        root.addWidget(self.empty, 1)
        self._container = container
        self._refresh_state()

    # ------------------------------------------------------------- helpers
    def add_task(self, task: DownloadTask) -> TaskCard:
        card = TaskCard(task, self._container)
        card.cancel_requested.connect(self.cancel_requested.emit)
        card.retry_requested.connect(self.retry_requested.emit)
        card.folder_requested.connect(self.folder_requested.emit)
        card.remove_requested.connect(self.remove_task)
        self._cards[task.id] = card
        self._tasks[task.id] = task
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)
        self._refresh_state()
        return card

    def update_task(self, task: DownloadTask) -> None:
        self._tasks[task.id] = task
        card = self._cards.get(task.id)
        if card:
            card.update_task(task)
        self._refresh_state()

    def remove_task(self, task_id: str) -> None:
        card = self._cards.pop(task_id, None)
        self._tasks.pop(task_id, None)
        if card:
            card.setParent(None)
            card.deleteLater()
        self._refresh_state()

    def clear_finished(self) -> None:
        for task_id, task in list(self._tasks.items()):
            if task.is_finished:
                self.remove_task(task_id)

    def set_concurrency(self, workers: int, active: int, pending: int) -> None:
        self.sub_label.setText(f"同时下载 {workers} 个任务 · 进行中 {active} · 等待 {pending}")
        self.pause_all_btn.setEnabled(active > 0)
        self.retry_failed_btn.setEnabled(
            any(t.status in (FAILED, CANCELLED) for t in self._tasks.values())
        )
        self.clear_btn.setEnabled(any(t.is_finished for t in self._tasks.values()))

    def task(self, task_id: str) -> DownloadTask | None:
        return self._tasks.get(task_id)

    def tasks(self) -> list[DownloadTask]:
        return list(self._tasks.values())

    def _refresh_state(self) -> None:
        has_cards = bool(self._cards)
        self.scroll.setVisible(has_cards)
        self.empty.setVisible(not has_cards)
        self.retry_failed_btn.setEnabled(
            any(t.status in (FAILED, CANCELLED) for t in self._tasks.values())
        )
        self.clear_btn.setEnabled(any(t.is_finished for t in self._tasks.values()))
