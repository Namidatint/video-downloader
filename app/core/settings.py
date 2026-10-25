"""Persistent user settings (JSON in the per-user app data directory)."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from app.core import paths

CONFIG_FILE = "config.json"


@dataclass
class Settings:
    # --- where / how files are saved -------------------------------------
    download_dir: str = field(default_factory=lambda: str(paths.default_download_dir()))
    filename_template: str = "%(title)s [%(id)s].%(ext)s"
    prefer_mp4: bool = True
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    write_subs: bool = False
    embed_subs: bool = True
    sub_langs: str = "zh-Hans,zh,en"
    sponsorblock: bool = False
    playlist: bool = False

    # --- network ----------------------------------------------------------
    proxy_mode: str = "system"  # system | direct | custom
    proxy: str = ""  # e.g. http://127.0.0.1:7890 (custom mode only)
    rate_limit_kbps: int = 0  # 0 = unlimited
    retries: int = 10
    fragment_concurrency: int = 4
    socket_timeout: int = 20

    # --- identity ---------------------------------------------------------
    cookies_browser: str = ""  # "", chrome, edge, firefox, safari, brave, chromium...
    cookies_file: str = ""
    user_agent: str = ""
    referer: str = ""

    # --- behaviour --------------------------------------------------------
    max_concurrent: int = 50
    language: str = "zh"  # zh | en | auto
    theme: str = "light"  # light | dark
    notify_on_finish: bool = True
    open_folder_when_done: bool = False
    clipboard_watch: bool = True
    remember_last_preset: bool = True
    last_preset: str = "best"
    custom_format: str = ""
    custom_ffmpeg: str = ""
    max_history: int = 500

    # --- internal ---------------------------------------------------------
    schema_version: int = 2

    # ------------------------------------------------------------------ io
    @classmethod
    def config_path(cls) -> Path:
        return paths.app_data_dir() / CONFIG_FILE

    @classmethod
    def load(cls) -> "Settings":
        path = cls.config_path()
        data: dict[str, Any] = {}
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data = raw
            except (OSError, ValueError):
                data = {}
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        settings = cls(**clean)
        if int(data.get("schema_version", 1) or 1) < 2:
            # v2 redesign: Windows 10 Settings light theme by default.
            settings.theme = "light"
            settings.schema_version = 2
        # App rename: keep the old default download folder from sticking around.
        legacy_download = str(Path.home() / "Downloads" / "GlowDL")
        if str(settings.download_dir).rstrip("/\\") == legacy_download:
            settings.download_dir = str(paths.default_download_dir())
        settings.validate()
        return settings

    def save(self) -> None:
        self.validate()
        path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".config-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, path)  # atomic on NTFS/APFS
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def update(self, **kwargs: Any) -> "Settings":
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.validate()
        return self

    # -------------------------------------------------------------- sanity
    def validate(self) -> None:
        self.download_dir = self.download_dir or str(paths.default_download_dir())
        self.filename_template = (
            self.filename_template or "%(title)s [%(id)s].%(ext)s"
        ).strip()
        if self.max_concurrent < 50:
            self.max_concurrent = 50
        if self.max_concurrent > 200:
            self.max_concurrent = 200
        if self.retries < 0:
            self.retries = 0
        if self.retries > 50:
            self.retries = 50
        if self.fragment_concurrency < 1:
            self.fragment_concurrency = 1
        if self.fragment_concurrency > 16:
            self.fragment_concurrency = 16
        if self.rate_limit_kbps < 0:
            self.rate_limit_kbps = 0
        if self.socket_timeout < 5:
            self.socket_timeout = 5
        if self.proxy_mode not in ("system", "direct", "custom"):
            self.proxy_mode = "system"
        if self.proxy_mode != "custom":
            # Keep the typed value so switching back to custom is painless.
            pass
        if self.language not in ("auto", "zh", "en"):
            self.language = "auto"
        if self.theme not in ("dark", "light"):
            self.theme = "light"
        if self.max_history < 10:
            self.max_history = 10
        proxy = (self.proxy or "").strip()
        if proxy and "://" not in proxy:
            proxy = "http://" + proxy
        self.proxy = proxy

    @property
    def output_dir(self) -> Path:
        path = Path(self.download_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def effective_proxy(self) -> str:
        """The proxy URL requests should use; empty string forces direct."""
        from app.core import netproxy

        if self.proxy_mode == "direct":
            return ""
        if self.proxy_mode == "custom":
            return self.proxy
        return netproxy.system_proxy()

    @property
    def rate_limit_bytes(self) -> int:
        return int(self.rate_limit_kbps) * 1024 if self.rate_limit_kbps else 0

    def effective_language(self) -> str:
        if self.language in ("zh", "en"):
            return self.language
        import locale

        try:
            lang = locale.getlocale()[0] or ""
        except Exception:
            lang = ""
        return "zh" if str(lang).lower().startswith("zh") else "en"
