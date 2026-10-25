"""ffmpeg discovery and self-healing.

The single most common yt-dlp support question is “why does it say ffmpeg is
missing, and how do I install it?”. GlowDL ships ffmpeg through
``imageio-ffmpeg`` so the answer becomes “you don't have to”.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _bundled_candidates() -> list[str]:
    paths: list[str] = []
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            paths.append(str(exe))
    except Exception:
        pass
    # PyInstaller adds binaries next to the frozen executable.
    import sys

    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    for name in ("ffmpeg", "ffmpeg.exe"):
        candidate = base / name
        if candidate.is_file():
            paths.append(str(candidate))
        candidate = base / "ffmpeg" / name
        if candidate.is_file():
            paths.append(str(candidate))
    return paths


def _well_known_paths() -> list[str]:
    candidates = [
        Path(__file__).resolve().parents[2] / "vendor" / "ffmpeg",
        Path.home() / "ffmpeg",
        Path("/opt/homebrew/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path("/usr/bin/ffmpeg"),
    ]
    if os.name == "nt":
        candidates += [
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "ffmpeg/bin/ffmpeg.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "视频下载器/ffmpeg/ffmpeg.exe",
        ]
    out = []
    for path in candidates:
        if path.is_dir():
            for name in ("ffmpeg", "ffmpeg.exe"):
                if (path / name).is_file():
                    out.append(str(path / name))
        elif path.is_file():
            out.append(str(path))
    return out


@dataclass(frozen=True)
class FFmpegStatus:
    available: bool
    path: str
    source: str  # bundled | custom | path | missing
    detail: str


def find_ffmpeg(custom: str = "") -> FFmpegStatus:
    if custom and Path(custom).expanduser().is_file():
        return FFmpegStatus(True, str(Path(custom).expanduser()), "custom", "使用自定义路径")
    env = os.environ.get("GLOWDL_FFMPEG") or os.environ.get("FFMPEG_BINARY") or ""
    if env and Path(env).is_file():
        return FFmpegStatus(True, env, "custom", "来自环境变量")

    for path in _bundled_candidates():
        return FFmpegStatus(True, path, "bundled", "已内置音视频组件")

    which = shutil.which("ffmpeg")
    if which:
        return FFmpegStatus(True, which, "path", "系统 PATH 中的 ffmpeg")

    for path in _well_known_paths():
        return FFmpegStatus(True, path, "path", "常见安装位置")

    return FFmpegStatus(False, "", "missing", "未找到 ffmpeg")


def ffmpeg_location(settings=None) -> str | None:
    custom = getattr(settings, "custom_ffmpeg", "") if settings else ""
    status = find_ffmpeg(custom)
    return status.path if status.available else None
