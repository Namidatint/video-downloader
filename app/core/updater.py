"""In-app updater for the yt-dlp core.

Two modes:
* Development / pip install: runs ``python -m pip install -U yt-dlp``.
* Frozen (PyInstaller) build: downloads the pure-Python wheel from PyPI,
  unpacks the ``yt_dlp`` package into the per-user app-data directory and
  prepends it to ``sys.path`` on the next launch. This keeps the app updatable
  without shipping a new 200 MB installer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

PYPI_JSON = "https://pypi.org/pypi/yt-dlp/json"
USER_CORE_DIRNAME = "core"


class UpdateError(Exception):
    pass


def _http_json(url: str, timeout: float = 15.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "VideoDownloader-Updater/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def user_core_dir(version: str | None = None) -> Path:
    from app.core.paths import app_data_dir

    base = app_data_dir() / USER_CORE_DIRNAME
    return base / version if version else base


def active_user_core() -> Path | None:
    """The newest unpacked user core, if any."""
    base = user_core_dir()
    if not base.is_dir():
        return None
    candidates = [p for p in base.iterdir() if (p / "yt_dlp" / "__init__.py").is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.name, reverse=True)
    return candidates[0]


def activate_user_core() -> Path | None:
    """Put a downloaded core ahead of the bundled one. Call before importing yt_dlp."""
    core = active_user_core()
    if core is None:
        return None
    path = str(core)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
    return core


def current_version() -> str:
    try:
        import yt_dlp

        return str(getattr(yt_dlp.version, "__version__", "unknown"))
    except Exception:
        return "unknown"


def latest_version(timeout: float = 12.0) -> str | None:
    try:
        data = _http_json(PYPI_JSON, timeout=timeout)
        return str(data.get("info", {}).get("version") or "") or None
    except Exception:
        return None


def update_available() -> tuple[bool, str, str]:
    """Return (available, current, latest)."""
    current = current_version()
    latest = latest_version()
    if not latest:
        return False, current, ""
    return _is_newer(latest, current), current, latest


def _is_newer(latest: str, current: str) -> bool:
    def parse(value: str):
        parts = []
        for chunk in str(value).replace("-", ".").split("."):
            digits = "".join(ch for ch in chunk if ch.isdigit())
            parts.append(int(digits) if digits else 0)
        return parts

    a, b = parse(latest), parse(current)
    length = max(len(a), len(b))
    a += [0] * (length - len(a))
    b += [0] * (length - len(b))
    return a > b


def _wheel_url(version: str) -> str:
    data = _http_json(PYPI_JSON)
    if str(data.get("info", {}).get("version")) != version:
        # The index moved on; use whatever it reports now.
        version = str(data.get("info", {}).get("version") or version)
    for item in data.get("urls", []):
        if item.get("packagetype") == "bdist_wheel" and item.get("filename", "").startswith("yt_dlp-"):
            return str(item["url"])
    raise UpdateError("PyPI 上没有找到可用的 yt-dlp wheel 包")


def update_core(progress: Callable[[str], None] | None = None) -> str:
    """Update yt-dlp. Returns the version now installed."""

    def report(message: str) -> None:
        if progress:
            progress(message)

    if not is_frozen():
        report("正在通过 pip 更新 yt-dlp …")
        env = dict(os.environ)
        env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            capture_output=True, text=True, env=env, timeout=300,
        )
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
            raise UpdateError("pip 更新失败：" + " | ".join(tail))
        # Force a fresh import in this process.
        for name in list(sys.modules):
            if name == "yt_dlp" or name.startswith("yt_dlp."):
                del sys.modules[name]
        report(f"已更新到 {current_version()}")
        return current_version()

    report("正在获取最新版本信息 …")
    latest = latest_version()
    if not latest:
        raise UpdateError("无法连接 PyPI，请检查网络或代理")

    report(f"正在下载 yt-dlp {latest} …")
    url = _wheel_url(latest)
    target_root = user_core_dir(latest)
    if (target_root / "yt_dlp" / "__init__.py").is_file():
        report("该版本已下载过，直接启用")
        activate_user_core()
        return latest

    with tempfile.TemporaryDirectory(prefix="glowdl-core-") as tmp:
        wheel_path = Path(tmp) / "yt_dlp.whl"
        request = urllib.request.Request(url, headers={"User-Agent": "VideoDownloader-Updater/1.0"})
        with urllib.request.urlopen(request, timeout=120) as resp, open(wheel_path, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        report("正在解包内核 …")
        target_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel_path) as zf:
            for member in zf.namelist():
                if member.startswith("yt_dlp/"):
                    zf.extract(member, target_root)
    activate_user_core()
    report(f"内核已更新到 {latest}，重启应用后生效")
    return latest


def cleanup_old_cores(keep: int = 2) -> None:
    base = user_core_dir()
    if not base.is_dir():
        return
    cores = sorted(
        [p for p in base.iterdir() if (p / "yt_dlp").is_dir()],
        key=lambda p: p.name, reverse=True,
    )
    for stale in cores[keep:]:
        shutil.rmtree(stale, ignore_errors=True)
