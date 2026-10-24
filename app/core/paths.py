"""Cross-platform filesystem helpers: app data dirs, filename safety, formatting."""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path

APP_DIR_NAME = "GlowDL"

# Characters that are illegal on Windows (and hostile everywhere).
_ILLEGAL = {
    "<": "＜",
    ">": "＞",
    ":": "：",
    '"': "＂",
    "/": "／",
    "\\": "＼",
    "|": "｜",
    "?": "？",
    "*": "＊",
}
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_macos() -> bool:
    return sys.platform == "darwin"


def app_data_dir() -> Path:
    """Per-user writable directory for config/history/logs."""
    if is_windows():
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = Path(base) / APP_DIR_NAME
    elif is_macos():
        path = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    if is_windows():
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        path = Path(base) / APP_DIR_NAME / "cache"
    elif is_macos():
        path = Path.home() / "Library" / "Caches" / APP_DIR_NAME
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> Path:
    downloads = Path.home() / "Downloads"
    path = downloads / "GlowDL" if downloads.is_dir() else Path.home() / "GlowDL"
    return path


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """Make an arbitrary title safe for NTFS/APFS/HFS+ and for shell use."""
    if not name:
        return "untitled"
    name = unicodedata.normalize("NFC", name)
    for bad, good in _ILLEGAL.items():
        name = name.replace(bad, good)
    name = "".join(ch for ch in name if ch.isprintable() and ch not in "\r\n\t")
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        return "untitled"
    stem = name.split(".")[0].upper()
    if stem in _WINDOWS_RESERVED:
        name = f"_{name}"
    if len(name) > max_length:
        name = name[:max_length].rstrip(" .")
    return name or "untitled"


def safe_template(template: str) -> str:
    """Keep yt-dlp fields intact but neutralize path separators in the template."""
    template = (template or "").strip() or "%(title)s.%(ext)s"
    # Only the filename part must be sanitized; yt-dlp does that itself when
    # `windowsfilenames` is set, but we also guard against absolute paths.
    template = template.replace("../", "").replace("..\\", "")
    if template.startswith(("/", "\\")):
        template = template.lstrip("/\\")
    return template


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for i in range(2, 1000):
        candidate = path.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{stem} ({os.getpid()}){suffix}")


def human_size(num: float | None) -> str:
    if not num or num <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def human_speed(num: float | None) -> str:
    if not num or num <= 0:
        return "—"
    return f"{human_size(num)}/s"


def human_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def human_eta(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "—"
    return human_duration(seconds)


def open_in_file_manager(path: str | Path) -> None:
    """Reveal a file/folder using the platform file manager (best effort)."""
    import subprocess

    path = Path(path)
    target = path if path.exists() else path.parent
    try:
        if is_windows():
            if path.is_file():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                os.startfile(str(target))  # type: ignore[attr-defined]
        elif is_macos():
            if path.is_file():
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except Exception:
        pass
