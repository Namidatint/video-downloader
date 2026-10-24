"""Task model shared by the queue manager and the UI."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import Problem

QUEUED = "queued"
RUNNING = "running"
POSTPROCESS = "postprocess"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

STATUS_LABELS = {
    QUEUED: ("排队中", "Queued"),
    RUNNING: ("下载中", "Downloading"),
    POSTPROCESS: ("处理中", "Processing"),
    DONE: ("已完成", "Completed"),
    FAILED: ("失败", "Failed"),
    CANCELLED: ("已取消", "Cancelled"),
}


@dataclass
class DownloadTask:
    url: str
    title: str = ""
    site: str = ""
    preset: str = "best"
    custom_format: str = ""
    thumbnail: str = ""
    duration: float | None = None
    playlist: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = QUEUED
    progress: float = 0.0
    downloaded: int = 0
    total: int = 0
    speed: float = 0.0
    eta: float | None = None
    filename: str = ""
    filepaths: list[str] = field(default_factory=list)
    problem: Problem | None = None
    raw_error: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------- helpers
    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, (self.status, self.status))[0]

    @property
    def is_active(self) -> bool:
        return self.status in (RUNNING, POSTPROCESS)

    @property
    def is_finished(self) -> bool:
        return self.status in (DONE, FAILED, CANCELLED)

    @property
    def display_title(self) -> str:
        return self.title or self.url

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def update_from_progress(self, data: dict[str, Any]) -> None:
        from app.core.engine import normalize_progress

        info = normalize_progress(data)
        self.progress = info["percent"]
        self.downloaded = info["downloaded"]
        self.total = info["total"]
        self.speed = info["speed"]
        self.eta = info["eta"]
        if info["filename"]:
            self.filename = info["filename"]
        if info["title"] and not self.title:
            self.title = info["title"]
        if info["status"] == "finished":
            self.status = POSTPROCESS
            self.progress = 100.0

    def mark_running(self) -> None:
        self.status = RUNNING
        self.started_at = time.time()

    def mark_done(self) -> None:
        self.status = DONE
        self.progress = 100.0
        self.finished_at = time.time()

    def mark_failed(self, problem: Problem, raw: str = "") -> None:
        self.status = FAILED
        self.problem = problem
        self.raw_error = raw or problem.raw
        self.finished_at = time.time()

    def mark_cancelled(self) -> None:
        self.status = CANCELLED
        self.finished_at = time.time()


@dataclass
class DownloadRequest:
    """Everything needed to run one download, captured from the UI."""

    task: DownloadTask
    outdir: str
    playlist: bool = False
