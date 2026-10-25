"""yt-dlp engine wrapper: probing, downloading, progress and cancellation.

This module never imports Qt. The UI runs :func:`probe` and :func:`download`
inside worker threads and forwards callbacks through Qt signals.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.core import formats as formats_mod
from app.core import paths
from app.core.errors import Problem, translate
from app.core.ffmpeg_tools import ffmpeg_location
from app.core.settings import Settings

ProgressCallback = Callable[[dict[str, Any]], None]
LogCallback = Callable[[str], None]

_MEDIA_EXTENSIONS = {
    "mp4", "mkv", "webm", "mov", "avi", "flv", "ts", "m4v", "mpg", "mpeg",
    "mp3", "m4a", "aac", "opus", "flac", "wav", "ogg", "vorbis",
}


class DownloadCancelled(Exception):
    """Raised from a progress hook to abort a download while keeping .part files."""


class DownloadError(Exception):
    """A download failure carrying a translated, user-facing Problem."""

    def __init__(self, problem: Problem, raw: str = ""):
        super().__init__(problem.title)
        self.problem = problem
        self.raw = raw or problem.raw


@dataclass
class DownloadResult:
    url: str
    title: str
    filepaths: list[str] = field(default_factory=list)
    duration: float | None = None
    site: str = ""
    preset: str = "best"
    elapsed: float = 0.0
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def filepath(self) -> str:
        return self.filepaths[0] if self.filepaths else ""

    @property
    def display_name(self) -> str:
        return Path(self.filepath).name if self.filepath else self.title


class _Logger:
    """Adapter from yt-dlp's logger protocol to a simple callback."""

    def __init__(self, log: LogCallback | None = None, verbose: bool = False):
        self._log = log
        self._verbose = verbose

    def _emit(self, message: str) -> None:
        if not self._log or not message:
            return
        message = str(message).strip()
        if not message:
            return
        if message.startswith("[debug]") and not self._verbose:
            return
        try:
            self._log(message)
        except Exception:
            pass

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            msg = msg[8:]
        self._emit(msg)

    def info(self, msg: str) -> None:
        self._emit(msg)

    def warning(self, msg: str) -> None:
        self._emit("警告 · " + str(msg))

    def error(self, msg: str) -> None:
        self._emit(str(msg))


def ytdlp_version() -> str:
    try:
        import yt_dlp

        return str(getattr(yt_dlp.version, "__version__", "unknown"))
    except Exception:
        return "未安装"


def _apply_network_options(opts: dict[str, Any], settings: Settings) -> None:
    mode = getattr(settings, "proxy_mode", "system")
    if mode == "direct":
        # Explicit empty string tells yt-dlp to bypass the OS/environment proxy.
        opts["proxy"] = ""
    elif mode == "custom" and settings.proxy:
        opts["proxy"] = settings.proxy
    if settings.rate_limit_bytes:
        opts["ratelimit"] = settings.rate_limit_bytes
    if settings.user_agent:
        opts.setdefault("http_headers", {})["User-Agent"] = settings.user_agent
    if settings.referer:
        opts.setdefault("http_headers", {})["Referer"] = settings.referer


def _apply_cookies(opts: dict[str, Any], settings: Settings) -> None:
    from app.core import cookies as cookies_mod

    browser = cookies_mod.cookiesfrombrowser(settings.cookies_browser)
    if browser:
        opts["cookiesfrombrowser"] = browser
    if settings.cookies_file:
        ready = cookies_mod.prepare_cookiefile(settings.cookies_file)
        if ready and Path(ready).is_file():
            opts["cookiefile"] = ready


def _base_options(settings: Settings, logger: _Logger) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "ignoreerrors": False,
        "ignore_no_formats_error": False,
        "socket_timeout": settings.socket_timeout,
        "retries": settings.retries,
        "fragment_retries": settings.retries,
        "concurrent_fragment_downloads": settings.fragment_concurrency,
        "continuedl": True,
        "overwrites": False,
        "windowsfilenames": paths.is_windows(),
        "trim_file_name": 120,
        "prefer_ffmpeg": True,
        "nocheckcertificate": False,
        "cachedir": str(paths.cache_dir() / "yt-dlp"),
        "logger": logger,
    }
    ffmpeg = ffmpeg_location(settings)
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    _apply_network_options(opts, settings)
    _apply_cookies(opts, settings)
    return opts


# ---------------------------------------------------------------------------
# probing
# ---------------------------------------------------------------------------
def probe(url: str, settings: Settings, playlist: bool = False,
          log: LogCallback | None = None) -> dict[str, Any]:
    """Fetch metadata without downloading. Returns yt-dlp's info dict."""
    import yt_dlp

    url = (url or "").strip()
    if not url:
        raise DownloadError(translate("Unsupported URL: empty"))
    logger = _Logger(log)
    opts = _base_options(settings, logger)
    opts.update({
        "skip_download": True,
        "noplaylist": not playlist,
        "extract_flat": False,
    })
    if playlist:
        opts["playlistend"] = 200
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise DownloadError(translate("Unable to extract video info"))
            return info
    except DownloadError:
        raise
    except Exception as exc:  # noqa: BLE001 - translated at the boundary
        raise DownloadError(translate(exc), raw=str(exc)) from exc


# ---------------------------------------------------------------------------
# downloading
# ---------------------------------------------------------------------------
def _postprocessors(settings: Settings, preset_key: str) -> list[dict[str, Any]]:
    preset = formats_mod.get_preset(preset_key)
    processors: list[dict[str, Any]] = []
    audio = formats_mod.audio_postprocessor(preset_key)
    if audio:
        processors.append(audio)
    if settings.embed_metadata:
        processors.append({"key": "FFmpegMetadata", "add_metadata": True})
    if settings.embed_thumbnail:
        processors.append({"key": "EmbedThumbnail"})
    if settings.write_subs and settings.embed_subs:
        processors.append({"key": "FFmpegEmbedSubtitle"})
    if settings.sponsorblock:
        processors.append({"key": "SponsorBlock", "categories": ["sponsor", "selfpromo"]})
        processors.append({"key": "ModifyChapters",
                           "remove_sponsor_segments": ["sponsor", "selfpromo"]})
    # Audio-only downloads should not carry an embedded thumbnail by default.
    if preset.kind == "audio":
        processors = [p for p in processors if p.get("key") != "EmbedThumbnail"]
    return processors


def build_download_options(
    settings: Settings,
    preset_key: str = "best",
    custom_format: str = "",
    outdir: str | Path | None = None,
    progress: ProgressCallback | None = None,
    log: LogCallback | None = None,
    cancel_event: threading.Event | None = None,
    playlist: bool = False,
) -> dict[str, Any]:
    """Build the yt-dlp options dict used by both GUI and CLI.

    Exposed separately so tests can assert on the exact options without any
    network access.
    """
    logger = _Logger(log)
    opts = _base_options(settings, logger)

    target = Path(outdir) if outdir else settings.output_dir
    target.mkdir(parents=True, exist_ok=True)
    template = paths.safe_template(settings.filename_template)
    opts["outtmpl"] = {"default": str(target / template)}
    opts["paths"] = {"home": str(target)}

    preset = formats_mod.get_preset(preset_key)
    opts["format"] = formats_mod.build_format_selector(preset_key, custom_format)
    if preset.kind == "video" and settings.prefer_mp4:
        opts["merge_output_format"] = "mp4"

    if preset.kind == "audio":
        opts["postprocessors"] = _postprocessors(settings, preset_key)
        opts["writethumbnail"] = False
    else:
        opts["postprocessors"] = _postprocessors(settings, preset_key)
        opts["writethumbnail"] = bool(settings.embed_thumbnail)

    if settings.write_subs and preset.kind != "audio":
        langs = [x.strip() for x in settings.sub_langs.split(",") if x.strip()]
        opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": langs or ["zh-Hans", "zh", "en"],
            "subtitlesformat": "srt/best",
        })

    if playlist:
        opts["noplaylist"] = False
        opts["ignoreerrors"] = True

    hooks: list[Callable[[dict[str, Any]], None]] = []

    def _hook(data: dict[str, Any]) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise _cancel_exception()
        if progress:
            try:
                progress(data)
            except Exception:
                pass

    hooks.append(_hook)
    opts["progress_hooks"] = hooks
    return opts


def _cancel_exception() -> BaseException:
    """Use yt-dlp's own cancellation type when available (clean abort, keeps .part)."""
    try:
        from yt_dlp.utils import DownloadCancelled as YtDlpCancelled

        return YtDlpCancelled()
    except Exception:
        return DownloadCancelled()


def download(
    url: str,
    settings: Settings,
    preset_key: str = "best",
    custom_format: str = "",
    outdir: str | Path | None = None,
    progress: ProgressCallback | None = None,
    log: LogCallback | None = None,
    cancel_event: threading.Event | None = None,
    playlist: bool = False,
) -> DownloadResult:
    """Download one URL (or playlist) and return the produced file paths."""
    import yt_dlp

    started = time.time()
    opts = build_download_options(
        settings, preset_key, custom_format, outdir, progress, log, cancel_event, playlist
    )
    finished_hooks: list[dict[str, Any]] = []

    def _record_finish(data: dict[str, Any]) -> None:
        if data.get("status") == "finished":
            finished_hooks.append(data)

    opts["progress_hooks"].append(_record_finish)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError:
        raise
    except BaseException as exc:  # noqa: BLE001
        name = exc.__class__.__name__
        if name in ("DownloadCancelled", "CancelledError") or isinstance(exc, DownloadCancelled):
            raise DownloadCancelled() from exc
        raise DownloadError(translate(exc), raw=str(exc)) from exc

    info = info or {}
    entries = info.get("entries")
    collected: list[dict[str, Any]] = []
    if entries:
        for entry in entries:
            if entry:
                collected.append(entry)
    else:
        collected = [info]

    filepaths: list[str] = []
    for entry in collected:
        path = _resolve_output_file(ydl, entry, finished_hooks, opts)
        if path:
            filepaths.append(path)

    if not filepaths:
        # Last resort: newest media file in the output dir created after start.
        filepaths = _newest_files(Path(opts["paths"]["home"]), started)

    title = formats_mod.guess_title(info)
    duration = info.get("duration")
    site = str(info.get("extractor_key") or info.get("extractor") or "")
    return DownloadResult(
        url=url,
        title=title,
        filepaths=filepaths,
        duration=float(duration) if isinstance(duration, (int, float)) else None,
        site=site,
        preset=preset_key,
        elapsed=time.time() - started,
        info=info,
    )


def _resolve_output_file(ydl, entry: dict[str, Any], finished: list[dict[str, Any]],
                         opts: dict[str, Any]) -> str:
    candidates: list[str] = []
    requested = entry.get("requested_downloads") or []
    for item in requested:
        for key in ("filepath", "_filename", "filename"):
            value = item.get(key)
            if value:
                candidates.append(str(value))
    if entry.get("filepath"):
        candidates.append(str(entry["filepath"]))
    for data in reversed(finished):
        if data.get("filename"):
            candidates.append(str(data["filename"]))

    checked: set[str] = set()
    for raw in candidates:
        if raw in checked:
            continue
        checked.add(raw)
        path = Path(raw)
        if path.is_file():
            return str(path)
        # Post-processing may have changed the extension (mp4 / mp3 / mkv).
        for ext in _MEDIA_EXTENSIONS:
            alt = path.with_suffix("." + ext)
            if alt.is_file():
                return str(alt)
    # Try a title-based lookup in the output folder.
    home = Path(opts.get("paths", {}).get("home", "."))
    title = formats_mod.guess_title(entry)
    safe = paths.sanitize_filename(title)
    if home.is_dir():
        matches = sorted(
            (p for p in home.iterdir()
             if p.is_file() and p.suffix.lstrip(".").lower() in _MEDIA_EXTENSIONS
             and safe[:20] in p.stem),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return str(matches[0])
    return ""


def _newest_files(folder: Path, since: float) -> list[str]:
    if not folder.is_dir():
        return []
    files = [
        p for p in folder.iterdir()
        if p.is_file()
        and p.suffix.lstrip(".").lower() in _MEDIA_EXTENSIONS
        and p.stat().st_mtime >= since - 5
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in files]


# ---------------------------------------------------------------------------
# progress helpers (used by the UI and by tests)
# ---------------------------------------------------------------------------
def normalize_progress(data: dict[str, Any]) -> dict[str, Any]:
    """Extract percent/speed/eta from a raw yt-dlp progress dict."""
    status = data.get("status", "")
    downloaded = data.get("downloaded_bytes") or 0
    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
    percent = (downloaded / total * 100.0) if total else 0.0
    if status == "finished":
        percent = 100.0
    info = data.get("info_dict") or {}
    return {
        "status": status,
        "percent": max(0.0, min(100.0, float(percent))),
        "downloaded": int(downloaded),
        "total": int(total),
        "speed": data.get("speed") or 0,
        "eta": data.get("eta"),
        "title": str(info.get("title") or ""),
        "filename": str(data.get("filename") or ""),
        "fragment": data.get("fragment_index"),
        "fragments": data.get("fragment_count"),
    }
