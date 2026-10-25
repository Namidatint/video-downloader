"""Main window: sidebar navigation, page wiring, queue scheduler, tray."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

from app import __version__ as app_version
from app.core import diagnostics, engine, paths
from app.core.errors import (ACTION_COOKIES, ACTION_COPY, ACTION_DIAGNOSTICS, ACTION_FFMPEG,
                             ACTION_LOGIN, ACTION_OPEN_DIR, ACTION_OPEN_URL, ACTION_PROXY,
                             ACTION_RETRY, ACTION_SETTINGS, ACTION_UPDATE, Problem)
from app.core.history import HistoryEntry, HistoryStore
from app.core.settings import Settings
from app.core.tasks import CANCELLED, FAILED, QUEUED, DownloadTask
from app.ui import icons, theme, widgets
from app.ui.pages.clinic_page import ClinicPage
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.home_page import HomePage, site_label
from app.ui.pages.queue_page import QueuePage
from app.ui.pages.settings_page import SettingsPage
from app.ui.workers import (DiagnosticsWorker, DownloadWorker, ProbeWorker, UpdateWorker,
                            VersionCheckWorker)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.lang = settings.effective_language()
        self.setWindowTitle("GlowDL · 拾光下载器")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(1080, 700)
        self.resize(1240, 820)
        self.setAcceptDrops(True)

        self.image_loader = widgets.ImageLoader(self)
        self.history = HistoryStore(limit=settings.max_history)
        self._tasks: dict[str, DownloadTask] = {}
        self._workers: dict[str, DownloadWorker] = {}
        self._probe: ProbeWorker | None = None
        self._diag_worker: DiagnosticsWorker | None = None
        self._version_worker: VersionCheckWorker | None = None
        self._update_worker: UpdateWorker | None = None
        self._checks: list[diagnostics.CheckResult] = []
        self._paused_all = False
        self._applied_theme = settings.theme

        self._build_ui()
        self._connect_signals()
        self._setup_tray()
        self._refresh_history()
        self.toast = widgets.Toast(self)

        QTimer.singleShot(400, lambda: self._run_diagnostics(silent=True))
        QTimer.singleShot(1500, self._check_updates_quietly)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("RootSurface")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.home_page = HomePage(self.settings, self.image_loader)
        self.queue_page = QueuePage()
        self.history_page = HistoryPage()
        self.clinic_page = ClinicPage(self.settings)
        self.settings_page = SettingsPage(self.settings)
        for page in (self.home_page, self.queue_page, self.history_page,
                     self.clinic_page, self.settings_page):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(226)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(36))
        logo.setFixedSize(38, 38)
        brand.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel("GlowDL")
        name.setObjectName("BrandName")
        sub = QLabel("拾光下载器")
        sub.setObjectName("BrandSub")
        brand_text.addWidget(name)
        brand_text.addWidget(sub)
        brand.addLayout(brand_text)
        brand.addStretch(1)
        layout.addLayout(brand)
        layout.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        self._nav_icon_names = ["download", "list", "clock", "pulse", "gear"]
        for index, (icon_name, label) in enumerate((
            ("download", "下载"),
            ("list", "队列"),
            ("clock", "历史"),
            ("pulse", "问题诊所"),
            ("gear", "设置"),
        )):
            button = QPushButton("  " + label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setIcon(icons.icon(icon_name, theme.active["muted"], 18))
            button.setIconSize(QSize(18, 18))
            button.setMinimumHeight(40)
            button.clicked.connect(lambda _=False, i=index: self._go(i))
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            layout.addWidget(button)
        self.nav_buttons[0].setChecked(True)
        self._refresh_nav_icons()

        layout.addStretch(1)

        self.core_label = QLabel(f"yt-dlp {engine.ytdlp_version()}")
        self.core_label.setObjectName("Dim")
        self.core_label.setWordWrap(True)
        layout.addWidget(self.core_label)

        self.selfcheck_btn = QPushButton("运行环境自检")
        self.selfcheck_btn.setObjectName("NavButton")
        self.selfcheck_btn.setCursor(Qt.PointingHandCursor)
        self.selfcheck_btn.setIcon(icons.icon("pulse", theme.active["muted"], 16))
        self.selfcheck_btn.clicked.connect(self._selfcheck_clicked)
        layout.addWidget(self.selfcheck_btn)

        version = QLabel(f"v{app_version} · Windows / macOS")
        version.setObjectName("Dim")
        layout.addWidget(version)
        return sidebar

    def _connect_signals(self) -> None:
        home = self.home_page
        home.parse_requested.connect(self._start_probe)
        home.download_requested.connect(self._enqueue)
        home.fix_requested.connect(self._handle_fix)
        home.settings_page_requested.connect(lambda: self._go(4))
        home.history_requested.connect(lambda: self._go(2))
        home.open_path_requested.connect(paths.open_in_file_manager)

        q = self.queue_page
        q.cancel_requested.connect(self._cancel_task)
        q.retry_requested.connect(self._retry_task)
        q.folder_requested.connect(self._open_task_folder)
        q.clear_finished_requested.connect(self._clear_finished)
        q.pause_all_requested.connect(self._pause_all)
        q.retry_failed_requested.connect(self._retry_all_failed)

        h = self.history_page
        h.redownload_requested.connect(self._redownload)
        h.clear_requested.connect(self._clear_history)
        h.entry_deleted.connect(self._delete_history_entry)

        c = self.clinic_page
        c.rerun_requested.connect(self._run_diagnostics)
        c.fix_requested.connect(self._handle_fix)

        s = self.settings_page
        s.settings_changed.connect(self._on_settings_changed)
        s.update_requested.connect(self._run_update)
        s.toast_requested.connect(lambda text, kind: self.toast.show_message(text, kind))

    # ------------------------------------------------------------- helpers
    def _refresh_nav_icons(self) -> None:
        current = self.stack.currentIndex() if hasattr(self, "stack") else 0
        for index, button in enumerate(self.nav_buttons):
            name = self._nav_icon_names[index]
            color = theme.active["accent_text"] if index == current else theme.active["muted"]
            button.setIcon(icons.icon(name, color, 18))
        if hasattr(self, "selfcheck_btn"):
            self.selfcheck_btn.setIcon(icons.icon("pulse", theme.active["muted"], 16))

    def _go(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
            self.nav_buttons[index].setChecked(True)
            self._refresh_nav_icons()
        if index == 2:
            self._refresh_history()
        elif index == 3 and not self._checks:
            self._run_diagnostics()

    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icons.app_icon(), self)
            self.tray.setToolTip("GlowDL · 拾光下载器")
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _notify(self, title: str, message: str, kind: str = "info") -> None:
        self.toast.show_message(message, kind)
        if self.tray and self.settings.notify_on_finish and self.tray.supportsMessages():
            icon_type = QSystemTrayIcon.Information if kind != "error" else QSystemTrayIcon.Warning
            self.tray.showMessage(title, message, icon_type, 4000)

    # ------------------------------------------------------------- probing
    def _start_probe(self, url: str, playlist: bool) -> None:
        if self._probe is not None and self._probe.isRunning():
            return
        self.home_page.set_loading(True)
        worker = ProbeWorker(url, self.settings, playlist, self)
        worker.ok.connect(self._on_probe_ok)
        worker.failed.connect(self._on_probe_failed)
        worker.finished.connect(self._on_probe_finished)
        self._probe = worker
        worker.start()

    def _on_probe_finished(self) -> None:
        if self._probe is not None:
            self._probe.deleteLater()
            self._probe = None

    def _on_probe_ok(self, info: dict) -> None:
        self.home_page.set_loading(False)
        entries = info.get("entries") if isinstance(info, dict) else None
        if entries:
            count = 0
            for entry in entries:
                if not entry:
                    continue
                url = entry.get("webpage_url") or entry.get("url") or ""
                if not url:
                    continue
                task = DownloadTask(
                    url=url,
                    title=str(entry.get("title") or ""),
                    site=site_label(str(entry.get("extractor_key") or entry.get("extractor") or "")),
                    preset=self.settings.last_preset,
                    thumbnail=str(entry.get("thumbnail") or ""),
                    duration=entry.get("duration"),
                    playlist=False,
                )
                self._enqueue(task, notify=False)
                count += 1
            self._notify("播放列表已加入队列", f"共 {count} 个视频开始排队下载", "ok")
            self._go(1)
            return
        self.home_page.show_media(info)

    def _on_probe_failed(self, problem: Problem) -> None:
        self.home_page.set_loading(False)
        self.home_page.show_error(problem)

    # ------------------------------------------------------------ queue
    def _enqueue(self, task: DownloadTask, notify: bool = True) -> None:
        self._paused_all = False
        self._tasks[task.id] = task
        self.queue_page.add_task(task)
        if notify:
            self.toast.show_message(f"已加入队列：{task.display_title[:46]}", "ok")
        self._start_pending()

    def _start_pending(self) -> None:
        if self._paused_all:
            self._refresh_queue_state()
            return
        while True:
            active = sum(1 for t in self._tasks.values() if t.is_active)
            if active >= self.settings.max_concurrent:
                break
            pending = [t for t in self._tasks.values() if t.status == QUEUED]
            if not pending:
                break
            self._start_task(pending[0])
        self._refresh_queue_state()

    def _start_task(self, task: DownloadTask) -> None:
        task.mark_running()
        self.queue_page.update_task(task)
        worker = DownloadWorker(task, self.settings, self)
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._on_log)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(lambda tid=task.id: self._on_worker_finished(tid))
        self._workers[task.id] = worker
        worker.start()
        self._refresh_queue_state()

    def _on_worker_finished(self, task_id: str) -> None:
        worker = self._workers.pop(task_id, None)
        if worker:
            worker.deleteLater()
        self._start_pending()

    def _on_progress(self, task_id: str, data: dict) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.update_from_progress(data)
        self.queue_page.update_task(task)

    def _on_log(self, task_id: str, message: str) -> None:
        # Reserved for a future log panel; keep the message available for debugging.
        task = self._tasks.get(task_id)
        if task is not None:
            task.extra.setdefault("log", []).append(message)
            if len(task.extra["log"]) > 200:
                task.extra["log"] = task.extra["log"][-200:]

    def _on_completed(self, task_id: str, result) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.filepaths = list(result.filepaths)
        task.title = task.title or result.title
        task.mark_done()
        self.queue_page.update_task(task)

        filepath = task.filepaths[0] if task.filepaths else ""
        size = 0
        if filepath:
            try:
                size = os.path.getsize(filepath)
            except OSError:
                size = 0
        self.history.add(HistoryEntry(
            url=task.url,
            title=task.title or result.title,
            site=task.site,
            preset=task.preset,
            filepath=filepath,
            filesize=size,
            duration=task.duration,
        ))
        self._refresh_history()
        self._notify("下载完成", f"{Path(filepath).name if filepath else task.title}", "ok")
        if self.settings.open_folder_when_done and filepath:
            paths.open_in_file_manager(filepath)

    def _on_failed(self, task_id: str, problem: Problem, raw: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.mark_failed(problem, raw)
        self.queue_page.update_task(task)
        self._notify("下载失败", problem.title, "error")
        if self.stack.currentIndex() == 0:
            if task.url:
                self.home_page.url_input.setText(task.url)
            self.home_page.show_error(problem)
        self._refresh_queue_state()

    def _on_cancelled(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.extra["user_paused"] = True
        task.mark_cancelled()
        self.queue_page.update_task(task)
        self._refresh_queue_state()

    def _cancel_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task and task.is_active:
            task.request_cancel()
            self.toast.show_message("正在停止下载…", "info")

    def _retry_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task or task.is_active:
            return
        self._paused_all = False
        self._reset_task(task)
        self.queue_page.update_task(task)
        self._start_pending()

    def _reset_task(self, task: DownloadTask) -> None:
        import threading

        task.status = QUEUED
        task.progress = 0.0
        task.downloaded = 0
        task.total = 0
        task.speed = 0.0
        task.eta = None
        task.filename = ""
        task.filepaths = []
        task.problem = None
        task.raw_error = ""
        task.cancel_event = threading.Event()
        task.extra.pop("user_paused", None)
        task.finished_at = None

    def _pause_all(self) -> None:
        if self._paused_all:
            self._paused_all = False
            self.queue_page.pause_all_btn.setText("全部暂停")
            self._start_pending()
            self.toast.show_message("已恢复队列调度", "ok")
            return
        self._paused_all = True
        self.queue_page.pause_all_btn.setText("继续全部")
        for task in self._tasks.values():
            if task.is_active:
                task.request_cancel()
        self.toast.show_message("已暂停全部任务，点击“继续全部”恢复", "info")

    def _retry_all_failed(self) -> None:
        self._paused_all = False
        self.queue_page.pause_all_btn.setText("全部暂停")
        for task in list(self._tasks.values()):
            if task.status in (FAILED, CANCELLED):
                self._reset_task(task)
                self.queue_page.update_task(task)
        self._start_pending()

    def _clear_finished(self) -> None:
        self.queue_page.clear_finished()
        for task_id in [tid for tid, t in self._tasks.items() if t.is_finished]:
            self._tasks.pop(task_id, None)
        self._refresh_queue_state()

    def _open_task_folder(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task and task.filepaths:
            paths.open_in_file_manager(task.filepaths[0])

    def _refresh_queue_state(self) -> None:
        active = sum(1 for t in self._tasks.values() if t.is_active)
        pending = sum(1 for t in self._tasks.values() if t.status == QUEUED)
        self.queue_page.set_concurrency(self.settings.max_concurrent, active, pending)
        failed = sum(1 for t in self._tasks.values() if t.status in (FAILED, CANCELLED))
        label = "队列" if not (active or pending or failed) else f"队列 · {active + pending + failed}"
        self.nav_buttons[1].setText("  " + label)

    # ------------------------------------------------------------ history
    def _refresh_history(self) -> None:
        self.history.limit = self.settings.max_history
        entries = self.history.entries
        self.history_page.set_entries(entries)
        self.home_page.set_recent(entries[:3])

    def _redownload(self, url: str, title: str, preset: str) -> None:
        task = DownloadTask(url=url, title=title, preset=preset or "best", site="视频")
        self._enqueue(task)
        self._go(1)

    def _clear_history(self) -> None:
        if not self.history.entries:
            return
        answer = QMessageBox.question(self, "清空历史", "只清空记录，不会删除已下载的文件。确定吗？")
        if answer == QMessageBox.Yes:
            self.history.clear()
            self._refresh_history()

    def _delete_history_entry(self, entry: HistoryEntry) -> None:
        self.history.remove(entry)
        self._refresh_history()

    # ---------------------------------------------------------- diagnostics
    def _selfcheck_clicked(self) -> None:
        self._go(3)
        self._run_diagnostics()

    def _run_diagnostics(self, silent: bool = False) -> None:
        if self._diag_worker is not None and self._diag_worker.isRunning():
            return
        self.clinic_page.set_running(True)
        worker = DiagnosticsWorker(self.settings, self)
        worker.done.connect(self._on_diagnostics_done)
        worker.finished.connect(lambda: setattr(self, "_diag_worker", None))
        self._diag_worker = worker
        worker.start()

    def _on_diagnostics_done(self, checks: list[diagnostics.CheckResult]) -> None:
        self._checks = checks
        self.clinic_page.set_running(False)
        self.clinic_page.set_checks(checks)
        overall = diagnostics.overall_status(checks)
        if overall == diagnostics.PASS:
            self.selfcheck_btn.setText("环境正常")
        elif overall == diagnostics.WARN:
            self.selfcheck_btn.setText("自检 · 有建议")
        else:
            fails = sum(1 for c in checks if c.status == diagnostics.FAIL)
            self.selfcheck_btn.setText(f"自检 · {fails} 项待修复")

    def _check_updates_quietly(self) -> None:
        worker = VersionCheckWorker(self)
        worker.result.connect(self._on_version_checked)
        worker.finished.connect(worker.deleteLater)
        self._version_worker = worker
        worker.start()
        self.settings_page.set_core_status("已内置最新版内核；可随时手动检查更新", "ok",
                                           engine.ytdlp_version())

    def _on_version_checked(self, available: bool, current: str, latest: str) -> None:
        if available and latest:
            self.settings_page.set_core_status(
                f"发现新版本 {latest}（当前 {current}），建议更新以获得最新站点支持。",
                "warn", current)
            self.toast.show_message(f"yt-dlp {latest} 可用，可在设置页更新", "warn")
        else:
            self.settings_page.set_core_status(
                f"已是最新版本（{current}）。", "ok", current)

    def _run_update(self) -> None:
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        self.settings_page.update_btn.setEnabled(False)
        self.settings_page.update_btn.setText("更新中…")
        self.settings_page.set_core_status("正在检查并下载最新内核…", "info")
        worker = UpdateWorker(self)
        worker.message.connect(lambda text: self.settings_page.set_core_status(text, "info"))
        worker.ok.connect(self._on_update_ok)
        worker.failed.connect(self._on_update_failed)
        worker.finished.connect(worker.deleteLater)
        self._update_worker = worker
        worker.start()

    def _on_update_ok(self, version: str) -> None:
        self.settings_page.update_btn.setEnabled(True)
        self.settings_page.update_btn.setText("检查更新")
        self.settings_page.set_core_status(f"内核已更新到 {version}，重启应用后生效。", "ok", version)
        self._notify("内核已更新", f"yt-dlp {version}，重启后生效", "ok")

    def _on_update_failed(self, message: str) -> None:
        self.settings_page.update_btn.setEnabled(True)
        self.settings_page.update_btn.setText("检查更新")
        self.settings_page.set_core_status(f"更新失败：{message}", "error")
        self.toast.show_message("内核更新失败，可稍后重试", "error")

    # --------------------------------------------------------------- fixes
    def _handle_fix(self, action: str, problem: Problem | None, source_url: str = "") -> None:
        if action == ACTION_RETRY:
            url = source_url or self.home_page.url_input.text().strip()
            if url:
                self._go(0)
                self.home_page.url_input.setText(url)
                self._start_probe(url, self.settings.playlist)
            else:
                self._go(1)
        elif action in (ACTION_SETTINGS, ACTION_PROXY):
            self._go(4)
        elif action == ACTION_DIRECT:
            self.settings.proxy_mode = "direct"
            self.settings.validate()
            self.settings.save()
            self.settings_page.load_from_settings()
            self.toast.show_message("已切换为直连模式，正在重试…", "ok")
            url = source_url or self.home_page.url_input.text().strip()
            if url:
                self._go(0)
                self.home_page.url_input.setText(url)
                self._start_probe(url, self.settings.playlist)
        elif action == ACTION_COOKIES:
            self._go(4)
            self.toast.show_message("在「登录态 Cookie」中选择你已登录的浏览器", "info")
        elif action == ACTION_LOGIN:
            target = source_url or "https://www.bilibili.com"
            QDesktopServices.openUrl(QUrl(target))
            self.toast.show_message("请在浏览器登录后，回到设置页读取 Cookie", "info")
        elif action == ACTION_DIAGNOSTICS:
            self._go(3)
            self._run_diagnostics()
        elif action == ACTION_FFMPEG:
            self._go(3)
            self._run_diagnostics()
            self.toast.show_message("已重新检测 ffmpeg；内置版本通常无需手动安装", "info")
        elif action == ACTION_UPDATE:
            self._go(4)
            self._run_update()
        elif action == ACTION_OPEN_DIR:
            paths.open_in_file_manager(self.settings.output_dir)
        elif action == ACTION_OPEN_URL:
            if source_url:
                QDesktopServices.openUrl(QUrl(source_url))
        elif action == ACTION_COPY:
            if problem:
                QApplication.clipboard().setText(problem.raw or problem.title)
                self.toast.show_message("已复制原始错误信息", "ok")

    # ------------------------------------------------------------ settings
    def _on_settings_changed(self) -> None:
        self.lang = self.settings.effective_language()
        if self.settings.theme != self._applied_theme:
            self._applied_theme = self.settings.theme
            self.toast.show_message("主题已保存，重启应用后生效", "info")
        self.home_page.refresh_manifest()
        self.clinic_page.reload_handbook()
        self._refresh_history()
        self._refresh_queue_state()
        self.settings_page.core_version.setText(f"yt-dlp {engine.ytdlp_version()}")
        self.core_label.setText(f"yt-dlp {engine.ytdlp_version()}")
        self._start_pending()

    # --------------------------------------------------------------- drag
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        url = ""
        if mime.hasUrls():
            url = mime.urls()[0].toString()
        elif mime.hasText():
            url = mime.text().strip().splitlines()[0]
        if url:
            self._go(0)
            self.home_page.url_input.setText(url)
            self._start_probe(url, self.settings.playlist)
        event.acceptProposedAction()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast.reposition()

    # --------------------------------------------------------------- close
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        active = [w for w in self._workers.values() if w.isRunning()]
        if active:
            answer = QMessageBox.question(
                self, "还有下载在进行",
                "关闭会中断正在进行的下载（已下载的分片会保留，下次可续传）。仍要关闭吗？",
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            for worker in active:
                worker.task.request_cancel()
            for worker in active:
                worker.wait(1500)
        for worker in list(self._workers.values()):
            worker.wait(200)
        for attr in ("_diag_worker", "_version_worker", "_update_worker", "_probe"):
            worker = getattr(self, attr, None)
            if worker is not None and hasattr(worker, "isRunning") and worker.isRunning():
                try:
                    worker.requestInterruption()
                except Exception:
                    pass
                worker.wait(2500)
        self.settings.save()
        if self.tray:
            self.tray.hide()
        event.accept()
