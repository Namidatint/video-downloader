"""Background workers: probing, downloading, updating the core."""

from __future__ import annotations

import threading
import time
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.core import engine
from app.core.errors import translate
from app.core.settings import Settings
from app.core.tasks import DownloadTask


class ProbeWorker(QThread):
    ok = Signal(object)
    failed = Signal(object)

    def __init__(self, url: str, settings: Settings, playlist: bool = False,
                 parent=None):
        super().__init__(parent)
        self.url = url
        self.settings = settings
        self.playlist = playlist

    def run(self) -> None:  # noqa: D401
        try:
            info = engine.probe(self.url, self.settings, playlist=self.playlist)
        except engine.DownloadError as exc:
            self.failed.emit(exc.problem)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(translate(exc))
        else:
            self.ok.emit(info)


class DownloadWorker(QThread):
    progress = Signal(str, dict)
    log = Signal(str, str)
    completed = Signal(str, object)
    failed = Signal(str, object, str)
    cancelled = Signal(str)

    def __init__(self, task: DownloadTask, settings: Settings, parent=None):
        super().__init__(parent)
        self.task = task
        self.settings = settings
        self._last_emit = 0.0

    def _on_progress(self, data: dict[str, Any]) -> None:
        now = time.monotonic()
        status = data.get("status")
        if status == "finished" or now - self._last_emit >= 0.12:
            self._last_emit = now
            self.progress.emit(self.task.id, data)

    def _log(self, message: str) -> None:
        self.log.emit(self.task.id, message)

    def run(self) -> None:  # noqa: D401
        task = self.task
        cancel_event: threading.Event = task.cancel_event
        try:
            result = engine.download(
                task.url,
                self.settings,
                preset_key=task.preset,
                custom_format=task.custom_format,
                outdir=self.settings.output_dir,
                progress=self._on_progress,
                log=self._log,
                cancel_event=cancel_event,
                playlist=task.playlist,
            )
        except engine.DownloadCancelled:
            self.cancelled.emit(task.id)
        except engine.DownloadError as exc:
            self.failed.emit(task.id, exc.problem, exc.raw)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(task.id, translate(exc), str(exc))
        else:
            self.completed.emit(task.id, result)


class UpdateWorker(QThread):
    message = Signal(str)
    ok = Signal(str)
    failed = Signal(str)

    def run(self) -> None:  # noqa: D401
        from app.core import updater

        try:
            version = updater.update_core(progress=self.message.emit)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        else:
            self.ok.emit(version)


class DiagnosticsWorker(QThread):
    done = Signal(object)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:  # noqa: D401
        from app.core import diagnostics

        try:
            checks = diagnostics.run_all(self.settings)
        except Exception as exc:  # noqa: BLE001
            checks = [diagnostics.CheckResult(
                "internal", "自检程序", diagnostics.FAIL, f"自检异常：{exc}")]
        self.done.emit(checks)


class VersionCheckWorker(QThread):
    result = Signal(bool, str, str)

    def run(self) -> None:  # noqa: D401
        from app.core import updater

        try:
            available, current, latest = updater.update_available()
        except Exception:
            available, current, latest = False, updater.current_version(), ""
        self.result.emit(available, current, latest)
