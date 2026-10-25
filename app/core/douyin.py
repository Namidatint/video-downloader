"""Native Douyin resolver and downloader.

Why: yt-dlp's Douyin extractor currently needs signature cookies (``s_v_web_id``
plus a signed ``aweme/detail`` request) and fails with "Fresh cookies ... are
needed". Instead of shipping a browser engine, GlowDL drives the user's own
Edge/Chrome once through the Chrome DevTools Protocol: it opens the video page
headlessly, waits for the signed ``aweme/detail`` response, and reads the
watermark-free play URLs from it. No third-party parsing service is involved and
the video bytes never leave the machine.

The browser is a local executable only; this module adds one small dependency
(``websocket-client``) and works on Windows/macOS/Linux when Edge/Chrome exists.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from app.core import paths

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REFERER = "https://www.douyin.com/"


class DouyinError(Exception):
    """Resolution failed; the message is user-facing."""


class DouyinCancelled(Exception):
    """Download cancelled by user; partial file is kept."""


@dataclass
class DouyinVariant:
    gear: str
    height: int | None
    width: int | None
    bitrate: int
    urls: list[str] = field(default_factory=list)


@dataclass
class DouyinInfo:
    video_id: str
    title: str
    uploader: str
    duration: float | None
    thumbnail: str
    width: int | None
    height: int | None
    variants: list[DouyinVariant]
    webpage_url: str

    @property
    def best(self) -> DouyinVariant:
        return max(self.variants, key=lambda v: v.bitrate)


_CACHE: dict[str, tuple[float, DouyinInfo]] = {}
_CACHE_TTL = 600


# ---------------------------------------------------------------------------
# URL + browser discovery
# ---------------------------------------------------------------------------
def is_douyin_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host == "douyin.com" or host.endswith(".douyin.com")


def find_browser() -> tuple[str, str] | None:
    """Return (executable, kind) for Edge/Chrome, or None."""
    import sys

    candidates: list[tuple[str, str]] = []
    if sys.platform == "darwin":
        candidates = [
            ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "edge"),
            ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "chrome"),
            (str(Path.home() / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"), "edge"),
            (str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), "chrome"),
        ]
    elif sys.platform.startswith("win"):
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            (rf"{pf86}\Microsoft\Edge\Application\msedge.exe", "edge"),
            (rf"{pf}\Microsoft\Edge\Application\msedge.exe", "edge"),
            (rf"{pf}\Google\Chrome\Application\chrome.exe", "chrome"),
            (rf"{pf86}\Google\Chrome\Application\chrome.exe", "chrome"),
            (rf"{local}\Google\Chrome\Application\chrome.exe", "chrome"),
        ]
    else:
        for name, kind in (("microsoft-edge", "edge"), ("google-chrome", "chrome"),
                           ("chromium", "chromium"), ("chromium-browser", "chromium")):
            found = shutil.which(name)
            if found:
                candidates.append((found, kind))
    for exe, kind in candidates:
        if exe and Path(exe).is_file():
            return exe, kind
    return None


# ---------------------------------------------------------------------------
# CDP client (minimal)
# ---------------------------------------------------------------------------
def _recv_json(ws, timeout: float = 1.0) -> dict | None:
    ws.settimeout(timeout)
    try:
        raw = ws.recv()
    except Exception:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _cdp_resolve(url: str, timeout: float = 45.0) -> dict[str, Any]:
    """Launch a headless browser and return the signed aweme/detail JSON."""
    from websocket import create_connection  # websocket-client

    browser = find_browser()
    if not browser:
        raise DouyinError(
            "解析抖音需要一个本机浏览器：请安装 Microsoft Edge 或 Google Chrome 后重试。"
        )
    exe, _kind = browser
    profile = tempfile.mkdtemp(prefix="glowdl-douyin-")
    args = [
        exe,
        "--headless=new",
        "--remote-debugging-port=0",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--mute-audio",
        "--disable-blink-features=AutomationControlled",
        "--window-size=1280,800",
        "about:blank",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        port_file = Path(profile) / "DevToolsActivePort"
        deadline = time.time() + 20
        port = ""
        while time.time() < deadline:
            if port_file.is_file():
                try:
                    port = port_file.read_text().splitlines()[0].strip()
                except OSError:
                    port = ""
                if port:
                    break
            time.sleep(0.2)
        if not port:
            raise DouyinError("抖音解析浏览器启动失败，请检查 Edge/Chrome 是否可正常打开。")

        page = None
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as resp:
                    targets = json.loads(resp.read().decode("utf-8"))
                page = next((t for t in targets if t.get("type") == "page"), None)
                if page:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not page:
            raise DouyinError("抖音解析浏览器没有响应，请重试。")

        ws = create_connection(page["webSocketDebuggerUrl"], timeout=10)
        message_id = 0
        pending: dict[int, str] = {}

        def send(method: str, params: dict | None = None) -> int:
            nonlocal message_id
            message_id += 1
            ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
            return message_id

        send("Network.enable")
        send("Page.enable")
        send("Page.navigate", {"url": url})

        detail: dict[str, Any] | None = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = _recv_json(ws)
            if not msg:
                continue
            method = msg.get("method")
            params = msg.get("params") or {}
            if method == "Network.responseReceived":
                response = params.get("response") or {}
                request_uri = response.get("url") or ""
                if "/aweme/v1/web/aweme/detail/" in request_uri and response.get("status") == 200:
                    req_id = params.get("requestId")
                    if req_id:
                        pending[send("Network.getResponseBody", {"requestId": req_id})] = req_id
            elif "id" in msg and msg["id"] in pending and isinstance(msg.get("result"), dict):
                result = msg["result"]
                body = result.get("body") or ""
                if result.get("base64Encoded"):
                    import base64

                    try:
                        body = base64.b64decode(body).decode("utf-8", "replace")
                    except Exception:
                        body = ""
                if body.strip().startswith("{"):
                    try:
                        candidate = json.loads(body)
                    except ValueError:
                        candidate = None
                    if candidate and candidate.get("aweme_detail"):
                        detail = candidate
                        break
        if not detail:
            raise DouyinError(
                "抖音页面没有返回视频数据。请先在浏览器打开该链接确认能播放，或稍后重试。"
            )
        return detail
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        shutil.rmtree(profile, ignore_errors=True)


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def _first_url(value: Any) -> str:
    if isinstance(value, dict):
        urls = value.get("url_list") or []
    elif isinstance(value, list):
        urls = value
    else:
        urls = []
    return str(urls[0]) if urls else ""


def _height_from_gear(gear: str | None) -> int | None:
    if not gear:
        return None
    import re

    match = re.search(r"(?:normal|adapt)_(\d{3,4})_", gear)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def parse_detail(payload: dict[str, Any], webpage_url: str = "") -> DouyinInfo:
    aweme = payload.get("aweme_detail") or {}
    if not aweme:
        raise DouyinError("抖音返回的数据为空，可能视频已删除或需要登录。")
    video = aweme.get("video") or {}
    title = (aweme.get("desc") or "").strip() or str(aweme.get("aweme_id") or "抖音视频")
    author = aweme.get("author") or {}
    uploader = str(author.get("nickname") or "")
    duration_ms = video.get("duration") or aweme.get("duration") or 0
    try:
        duration = float(duration_ms) / 1000.0 if duration_ms else None
    except (TypeError, ValueError):
        duration = None

    width = video.get("width")
    height = video.get("height")
    try:
        aspect = float(width) / float(height) if width and height else 16 / 9
    except (TypeError, ValueError):
        aspect = 16 / 9
    variants: list[DouyinVariant] = []
    for item in video.get("bit_rate") or []:
        if not isinstance(item, dict):
            continue
        if item.get("format") not in (None, "mp4"):
            continue  # "dash" entries are video-only; skip to keep a muxed file
        play = item.get("play_addr") or {}
        urls = [str(u) for u in (play.get("url_list") or []) if u]
        if not urls:
            continue
        gear = str(item.get("gear_name") or "")
        try:
            bitrate = int(item.get("bit_rate") or 0)
        except (TypeError, ValueError):
            bitrate = 0
        variant_height = _height_from_gear(gear)
        variant_width = round(variant_height * aspect) if variant_height else None
        variants.append(DouyinVariant(gear=gear, height=variant_height, width=variant_width,
                                     bitrate=bitrate, urls=urls))

    if not variants:
        urls = [str(u) for u in ((video.get("play_addr") or {}).get("url_list") or []) if u]
        if urls:
            variants.append(DouyinVariant(gear="default", height=height, width=width,
                                         bitrate=1, urls=urls))
    if not variants:
        raise DouyinError("抖音没有返回可下载的视频地址，可能视频受地区/登录限制。")

    # Keep only the highest-bitrate entry per height, best first.
    by_height: dict[int | None, DouyinVariant] = {}
    for variant in variants:
        current = by_height.get(variant.height)
        if current is None or variant.bitrate > current.bitrate:
            by_height[variant.height] = variant
    ordered = sorted(by_height.values(), key=lambda v: v.bitrate, reverse=True)

    return DouyinInfo(
        video_id=str(aweme.get("aweme_id") or ""),
        title=title,
        uploader=uploader,
        duration=duration,
        thumbnail=_first_url(video.get("cover")) or _first_url(video.get("origin_cover")),
        width=int(width) if width else None,
        height=int(height) if height else None,
        variants=ordered,
        webpage_url=webpage_url,
    )


def resolve(url: str, timeout: float = 60.0, attempts: int = 3) -> DouyinInfo:
    cached = _CACHE.get(url)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    if not find_browser():
        raise DouyinError("解析抖音需要一个本机浏览器：请安装 Microsoft Edge 或 Google Chrome 后重试。")
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            payload = _cdp_resolve(url, timeout=timeout)
            info = parse_detail(payload, webpage_url=url)
            _CACHE[url] = (time.time(), info)
            return info
        except DouyinError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise DouyinError(str(last_error))


# ---------------------------------------------------------------------------
# yt-dlp compatible info
# ---------------------------------------------------------------------------
def to_info_dict(info: DouyinInfo) -> dict[str, Any]:
    formats = []
    for index, variant in enumerate(info.variants):
        filesize = int(variant.bitrate * info.duration / 8) if info.duration else None
        formats.append({
            "format_id": f"douyin-{index}",
            "ext": "mp4",
            "height": variant.height or info.height,
            "width": variant.width or info.width,
            "fps": 30,
            "vcodec": "h264",
            "acodec": "aac",
            "tbr": round(variant.bitrate / 1000, 1) if variant.bitrate else None,
            "filesize": filesize,
            "format_note": variant.gear,
        })
    return {
        "id": info.video_id,
        "title": info.title,
        "uploader": info.uploader,
        "channel": info.uploader,
        "duration": info.duration,
        "thumbnail": info.thumbnail,
        "extractor_key": "Douyin",
        "extractor": "Douyin",
        "webpage_url": info.webpage_url,
        "formats": formats,
        "_type": "video",
        "_glowdl_douyin": True,
    }


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------
def _pick_variant(info: DouyinInfo, preset_key: str) -> DouyinVariant:
    from app.core import formats as formats_mod

    preset = formats_mod.get_preset(preset_key)
    if preset.height:
        eligible = [v for v in info.variants if (v.height or info.height or 0) <= preset.height]
        if eligible:
            return max(eligible, key=lambda v: v.bitrate)
    return info.best


def render_filename(template: str, info: DouyinInfo) -> str:
    title = paths.sanitize_filename(info.title)
    uploader = paths.sanitize_filename(info.uploader or "抖音")
    video_id = paths.sanitize_filename(info.video_id or "video")
    rendered = (template or "%(title)s [%(id)s].%(ext)s")
    rendered = (rendered.replace("%(title)s", title)
                        .replace("%(id)s", video_id)
                        .replace("%(uploader)s", uploader)
                        .replace("%(ext)s", "mp4")
                        .replace("%(duration)s", str(int(info.duration or 0))))
    return paths.sanitize_filename(rendered, max_length=150)


def _http_headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Referer": REFERER, "Accept": "*/*"}


def _download_http(url: str, target: Path, progress, cancel_event) -> None:
    part = target.with_suffix(target.suffix + ".part")
    existing = part.stat().st_size if part.is_file() else 0
    headers = _http_headers()
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as exc:
        if existing and exc.code == 416:
            part.replace(target)
            return
        raise
    total = int(response.headers.get("Content-Length") or 0)
    if existing and response.status != 206:
        existing = 0
    total = total + existing if total else 0
    downloaded = existing
    started = time.time()
    mode = "ab" if existing else "wb"
    with open(part, mode) as handle:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise DouyinCancelled()
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            elapsed = max(0.001, time.time() - started)
            speed = (downloaded - existing) / elapsed
            if progress:
                progress({
                    "status": "downloading",
                    "downloaded_bytes": downloaded,
                    "total_bytes": total or None,
                    "speed": speed,
                    "eta": ((total - downloaded) / speed) if (total and speed) else None,
                    "filename": str(target),
                })
    if target.exists():
        target.unlink()
    part.replace(target)
    if progress:
        progress({"status": "finished", "downloaded_bytes": downloaded,
                  "total_bytes": total or downloaded, "filename": str(target)})


def _run_ffmpeg(args: list[str]) -> bool:
    from app.core.ffmpeg_tools import find_ffmpeg

    ffmpeg = find_ffmpeg()
    if not ffmpeg.available:
        return False
    try:
        subprocess.run([ffmpeg.path, "-y", "-hide_banner", "-loglevel", "error", *args],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=180)
        return True
    except Exception:
        return False


def _postprocess(video: Path, info: DouyinInfo, settings, preset_key: str) -> Path:
    """Embed cover/metadata or extract audio. Best effort; never destroys the file."""
    from app.core import formats as formats_mod

    preset = formats_mod.get_preset(preset_key)
    if preset.kind == "audio":
        codec = preset.audio_codec or "mp3"
        audio = video.with_suffix("." + codec)
        args = ["-i", str(video), "-vn"]
        if codec == "mp3":
            args += ["-c:a", "libmp3lame", "-q:a", "0"]
        else:
            args += ["-c:a", "copy"]
        args.append(str(audio))
        if _run_ffmpeg(args) and audio.is_file():
            video.unlink(missing_ok=True)
            return audio
        return video

    if not (settings.embed_thumbnail or settings.embed_metadata):
        return video
    temp = video.with_name(video.stem + ".glowdl-tmp.mp4")
    args = ["-i", str(video)]
    cover_path: Path | None = None
    if settings.embed_thumbnail and info.thumbnail:
        try:
            cover_path = video.with_name(".glowdl-cover.jpg")
            request = urllib.request.Request(info.thumbnail, headers=_http_headers())
            with urllib.request.urlopen(request, timeout=20) as resp, open(cover_path, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            if cover_path.stat().st_size < 100:
                cover_path.unlink(missing_ok=True)
                cover_path = None
        except Exception:
            cover_path = None
    if cover_path:
        args += ["-i", str(cover_path), "-map", "0", "-map", "1", "-c", "copy",
                 "-disposition:v:1", "attached_pic"]
    else:
        args += ["-map", "0", "-c", "copy"]
    if settings.embed_metadata:
        args += ["-metadata", f"title={info.title}",
                 "-metadata", f"artist={info.uploader or '抖音'}"]
    args.append(str(temp))
    ok = _run_ffmpeg(args)
    if cover_path:
        cover_path.unlink(missing_ok=True)
    if ok and temp.is_file() and temp.stat().st_size > 0:
        video.unlink(missing_ok=True)
        temp.replace(video)
    else:
        temp.unlink(missing_ok=True)
    return video


def download(
    url: str,
    settings,
    preset_key: str = "best",
    progress: Callable[[dict[str, Any]], None] | None = None,
    cancel_event=None,
    outdir: str | Path | None = None,
) -> tuple[Path, DouyinInfo]:
    info = resolve(url)
    variant = _pick_variant(info, preset_key)
    target_dir = Path(outdir) if outdir else settings.output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = render_filename(settings.filename_template, info)
    target = target_dir / filename
    target = paths.unique_path(target)
    last_error: Exception | None = None
    for candidate in variant.urls:
        try:
            _download_http(candidate, target, progress, cancel_event)
            last_error = None
            break
        except DouyinCancelled:
            raise
        except Exception as exc:  # try the next CDN line
            last_error = exc
            target.with_suffix(target.suffix + ".part").unlink(missing_ok=True)
            continue
    if last_error is not None:
        raise DouyinError(f"抖音视频下载失败：{last_error}")
    return _postprocess(target, info, settings, preset_key), info
