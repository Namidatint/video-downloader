"""Download history persisted as JSON."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.core import paths

HISTORY_FILE = "history.json"


@dataclass
class HistoryEntry:
    url: str
    title: str = ""
    site: str = ""
    preset: str = "best"
    filepath: str = ""
    filesize: int = 0
    duration: float | None = None
    finished_at: float = field(default_factory=time.time)

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.finished_at))


class HistoryStore:
    def __init__(self, path: Path | None = None, limit: int = 500):
        self.path = path or (paths.app_data_dir() / HISTORY_FILE)
        self.limit = limit
        self._entries: list[HistoryEntry] = []
        self.load()

    def load(self) -> list[HistoryEntry]:
        self._entries = []
        if self.path.is_file():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    for item in raw:
                        if not isinstance(item, dict):
                            continue
                        known = {f.name for f in HistoryEntry.__dataclass_fields__.values()}
                        clean = {k: v for k, v in item.items() if k in known}
                        if clean.get("url"):
                            self._entries.append(HistoryEntry(**clean))
            except (OSError, ValueError, TypeError):
                self._entries = []
        return self._entries

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([asdict(e) for e in self._entries], ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".history-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def add(self, entry: HistoryEntry) -> None:
        # De-duplicate identical url+filepath so re-downloads refresh the entry.
        self._entries = [
            e for e in self._entries
            if not (e.url == entry.url and e.filepath == entry.filepath)
        ]
        self._entries.insert(0, entry)
        if len(self._entries) > self.limit:
            self._entries = self._entries[: self.limit]
        self.save()

    def remove(self, entry: HistoryEntry) -> None:
        self._entries = [e for e in self._entries if e is not entry and e != entry]
        self.save()

    def clear(self) -> None:
        self._entries = []
        self.save()

    @property
    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
