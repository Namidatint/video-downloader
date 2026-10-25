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
import re
import shutil
import signal
import ssl
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


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


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
    images: list[str] = field(default_factory=list)
    motion: str = ""

    @property
    def best(self) -> DouyinVariant:
        return max(self.variants, key=lambda v: v.bitrate)

    @property
    def is_images(self) -> bool:
        return not self.variants and bool(self.images)


_CACHE: dict[str, tuple[float, DouyinInfo]] = {}
_CACHE_TTL = 600

_URL_RE = re.compile(r"https?://[^\s<>\"'，。；、）】》」』]+", re.IGNORECASE)
_BARE_RE = re.compile(r"(?:https?://)?(?:v\.)?douyin\.com/[^\s<>\"'，。；、）】》」』]+",
                      re.IGNORECASE)


def extract_url(text: str) -> str:
    """Pull the first Douyin URL out of a share message.

    Douyin's share sheet pastes text like ``5.38 复制打开抖音... https://v.douyin.com/xxx/``;
    the previous input validation treated the whole sentence as a URL and failed.
    """
    text = (text or "").strip()
    if not text:
        return ""
    match = _URL_RE.search(text)
    if not match:
        match = _BARE_RE.search(text)
        if not match:
            return ""
        candidate = match.group(0)
        if not candidate.lower().startswith(("http://", "https://")):
            candidate = "https://" + candidate
    else:
        candidate = match.group(0)
    return candidate.rstrip(".,!?;:，。！？；：、）】》」』\"'")


def _expand_url(url: str, timeout: float = 8.0) -> str:
    """Follow a v.douyin.com short link to its canonical /video/ or /note/ URL."""
    host = (urlparse(url).hostname or "").lower()
    if host != "v.douyin.com":
        return url
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": REFERER,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    context = _ssl_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.geturl() or url
    except Exception:
        return url


def _canonical_id(url: str) -> str:
    match = re.search(r"/(?:video|note)/(\d+)", url)
    return match.group(1) if match else url


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


def _kill_browser(proc: subprocess.Popen, profile: str) -> None:
    """Kill the whole browser process group, not just the launcher."""
    if proc.poll() is None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=8)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
            except Exception:
                pass
    shutil.rmtree(profile, ignore_errors=True)


def _cdp_resolve(url: str, timeout: float = 25.0) -> dict[str, Any]:
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
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--disable-extensions",
        "--disable-default-apps",
        "--disable-features=Translate,MediaRouter,OptimizationHints",
        "--metrics-recording-only",
        "--no-pings",
        "--disable-blink-features=AutomationControlled",
        "--window-size=1280,800",
        "about:blank",
    ]
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, **kwargs)
    ws = None
    try:
        port_file = Path(profile) / "DevToolsActivePort"
        deadline = time.time() + 15
        port = ""
        while time.time() < deadline:
            if port_file.is_file():
                try:
                    port = port_file.read_text().splitlines()[0].strip()
                except OSError:
                    port = ""
                if port:
                    break
            time.sleep(0.15)
        if not port:
            raise DouyinError("抖音解析浏览器启动失败，请检查 Edge/Chrome 是否可正常打开。")

        page = None
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as resp:
                    targets = json.loads(resp.read().decode("utf-8"))
                page = next((t for t in targets if t.get("type") == "page"), None)
                if page:
                    break
            except Exception:
                pass
            time.sleep(0.15)
        if not page:
            raise DouyinError("抖音解析浏览器没有响应，请重试。")

        ws = create_connection(page["webSocketDebuggerUrl"], timeout=10,
                               max_size=16 * 1024 * 1024)
        message_id = 0
        pending: dict[int, str] = {}
        detail_request: str | None = None
        body_error: str | None = None

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
            msg = _recv_json(ws, 1.0)
            if not msg:
                continue
            method = msg.get("method")
            params = msg.get("params") or {}
            if method == "Network.responseReceived":
                response = params.get("response") or {}
                request_uri = response.get("url") or ""
                if "/aweme/v1/web/aweme/detail/" in request_uri and response.get("status") == 200:
                    detail_request = params.get("requestId")
            elif method == "Network.loadingFinished":
                if detail_request and params.get("requestId") == detail_request:
                    pending[send("Network.getResponseBody", {"requestId": detail_request})] = detail_request
            elif method == "Network.loadingFailed":
                if detail_request and params.get("requestId") == detail_request:
                    body_error = str(params.get("errorText") or "network error")
            elif "id" in msg and msg["id"] in pending and isinstance(msg.get("result"), dict):
                body = msg["result"].get("body") or ""
                if msg["result"].get("base64Encoded"):
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
                if not body:
                    body_error = "empty response"
        if not detail:
            if body_error:
                raise DouyinError(f"抖音页面数据读取失败（{body_error}），请重试。")
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
        _kill_browser(proc, profile)


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
        images = aweme.get("images") or []
        if images:
            raise DouyinError(f"这是抖音图文作品（{len(images)} 张图片），当前版本只支持视频下载。")
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


def _cdp_note(url: str, timeout: float = 25.0) -> dict[str, Any]:
    """Open a Douyin note page and read its rendered image URLs."""
    from websocket import create_connection

    browser = find_browser()
    if not browser:
        raise DouyinError(
            "解析抖音需要一个本机浏览器：请安装 Microsoft Edge 或 Google Chrome 后重试。"
        )
    exe, _kind = browser
    profile = tempfile.mkdtemp(prefix="glowdl-douyin-")
    args = [
        exe, "--headless=new", "--remote-debugging-port=0",
        f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
        "--disable-gpu", "--mute-audio", "--disable-background-networking",
        "--disable-component-update", "--disable-sync", "--disable-extensions",
        "--disable-default-apps", "--disable-features=Translate,MediaRouter",
        "--metrics-recording-only", "--no-pings",
        "--disable-blink-features=AutomationControlled", "--window-size=1280,800",
        "about:blank",
    ]
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, **kwargs)
    ws = None
    try:
        port_file = Path(profile) / "DevToolsActivePort"
        deadline = time.time() + 15
        port = ""
        while time.time() < deadline:
            if port_file.is_file():
                try:
                    port = port_file.read_text().splitlines()[0].strip()
                except OSError:
                    port = ""
                if port:
                    break
            time.sleep(0.15)
        if not port:
            raise DouyinError("抖音解析浏览器启动失败，请检查 Edge/Chrome 是否可正常打开。")

        page = None
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as resp:
                    targets = json.loads(resp.read().decode("utf-8"))
                page = next((t for t in targets if t.get("type") == "page"), None)
                if page:
                    break
            except Exception:
                pass
            time.sleep(0.15)
        if not page:
            raise DouyinError("抖音解析浏览器没有响应，请重试。")

        ws = create_connection(page["webSocketDebuggerUrl"], timeout=10,
                               max_size=16 * 1024 * 1024)
        message_id = 0

        def send(method: str, params: dict | None = None) -> int:
            nonlocal message_id
            message_id += 1
            ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
            return message_id

        send("Page.enable")
        send("Runtime.enable")
        send("Page.navigate", {"url": url})
        expression = """(() => {
          const urls = Array.from(new Set(Array.from(document.images)
            .map(img => img.src)
            .filter(src => src.includes('biz_tag=aweme_images'))));
          const videos = Array.from(document.querySelectorAll('video'))
            .map(video => ({src: video.currentSrc || video.src, duration: video.duration || 0}))
            .filter(item => item.src && item.duration > 0 &&
              (item.src.includes('douyinvod') || item.src.includes('video_mp4')));
          return JSON.stringify({title: document.title || '', images: urls,
                                 motion: videos.length ? videos[0].src : ''});
        })()"""

        deadline = time.time() + timeout
        still_payload: dict[str, Any] | None = None
        still_deadline = 0.0
        while time.time() < deadline:
            request_id = send("Runtime.evaluate",
                              {"expression": expression, "returnByValue": True})
            while time.time() < deadline:
                msg = _recv_json(ws, 1.0)
                if not msg:
                    break
                if msg.get("id") == request_id and isinstance(msg.get("result"), dict):
                    value = (msg["result"].get("result") or {}).get("value")
                    if value:
                        try:
                            payload = json.loads(value)
                        except ValueError:
                            payload = {}
                        if payload.get("images"):
                            # The still image renders before the Live Photo clip;
                            # give the <video> element a short window to appear.
                            if payload.get("motion"):
                                return payload
                            if still_payload is None:
                                still_payload = payload
                                still_deadline = time.time() + 2.5
                            elif time.time() >= still_deadline:
                                return still_payload
                    break
            time.sleep(0.5)
        if still_payload is not None:
            return still_payload
        raise DouyinError("抖音图文页面没有返回图片，请稍后重试。")
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        _kill_browser(proc, profile)


def parse_note(payload: dict[str, Any], webpage_url: str = "") -> DouyinInfo:
    """Build a gallery result from the note page's rendered DOM."""
    images = [str(u) for u in (payload.get("images") or []) if str(u).startswith("http")]
    motion = str(payload.get("motion") or "")
    if not motion.startswith("http"):
        motion = ""
    if not images:
        raise DouyinError("抖音图文页面没有返回图片，请稍后重试。")
    title = str(payload.get("title") or "").strip()
    if title.endswith(" - 抖音"):
        title = title.removesuffix(" - 抖音").strip()
    match = re.search(r"/(?:note|video)/(\d+)", webpage_url)
    video_id = match.group(1) if match else str(payload.get("id") or "")
    return DouyinInfo(
        video_id=video_id,
        title=title or "抖音图文",
        uploader=str(payload.get("uploader") or "抖音"),
        duration=None,
        thumbnail=images[0],
        width=None,
        height=None,
        variants=[],
        webpage_url=webpage_url,
        images=images,
        motion=motion,
    )


def resolve(url: str, timeout: float = 25.0, attempts: int = 2) -> DouyinInfo:
    url = extract_url(url) or (url or "").strip()
    if not url:
        raise DouyinError("没有在这段文字里找到抖音链接。")
    if not is_douyin_url(url):
        raise DouyinError("这不是抖音链接。")
    canonical = _expand_url(url)
    key = _canonical_id(canonical)
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    is_note = "/note/" in canonical
    if not find_browser():
        raise DouyinError("解析抖音需要一个本机浏览器：请安装 Microsoft Edge 或 Google Chrome 后重试。")
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            if is_note:
                info = parse_note(_cdp_note(canonical, timeout=timeout), webpage_url=canonical)
            else:
                payload = _cdp_resolve(canonical, timeout=timeout)
                info = parse_detail(payload, webpage_url=canonical)
            _CACHE[key] = (time.time(), info)
            return info
        except DouyinError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.0)
    assert last_error is not None
    raise DouyinError(str(last_error))


# ---------------------------------------------------------------------------
# yt-dlp compatible info
# ---------------------------------------------------------------------------
def to_info_dict(info: DouyinInfo) -> dict[str, Any]:
    if info.is_images:
        return {
            "id": info.video_id,
            "title": info.title,
            "uploader": info.uploader,
            "channel": info.uploader,
            "duration": None,
            "thumbnail": info.thumbnail,
            "extractor_key": "Douyin",
            "extractor": "Douyin",
            "webpage_url": info.webpage_url,
            "formats": [{
                "format_id": "douyin-images",
                "ext": "zip",
                "height": None,
                "width": None,
                "format_note": (f"实况 · {len(info.images)} 张 + 动态"
                                if info.motion else f"图文 · {len(info.images)} 张"),
                "filesize": None,
            }],
            "image_count": len(info.images),
            "live_photo": bool(info.motion),
            "_type": "images",
            "_glowdl_douyin": True,
        }
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


def render_filename(template: str, info: DouyinInfo, ext: str = "mp4") -> str:
    title = paths.sanitize_filename(info.title)
    uploader = paths.sanitize_filename(info.uploader or "抖音")
    video_id = paths.sanitize_filename(info.video_id or "video")
    rendered = (template or "%(title)s [%(id)s].%(ext)s")
    rendered = (rendered.replace("%(title)s", title)
                        .replace("%(id)s", video_id)
                        .replace("%(uploader)s", uploader)
                        .replace("%(ext)s", ext)
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
        response = urllib.request.urlopen(request, timeout=30, context=_ssl_context())
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
            with urllib.request.urlopen(request, timeout=20, context=_ssl_context()) as resp, open(cover_path, "wb") as fh:
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


def _download_images(info: DouyinInfo, settings, progress, cancel_event,
                     outdir: str | Path | None) -> tuple[Path, DouyinInfo]:
    target_dir = Path(outdir) if outdir else settings.output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / render_filename(settings.filename_template, info, ext="zip")
    target = paths.unique_path(target)
    work = Path(tempfile.mkdtemp(prefix="glowdl-douyin-images-"))
    try:
        files: list[Path] = []
        for index, url in enumerate(info.images):
            if cancel_event is not None and cancel_event.is_set():
                raise DouyinCancelled()
            suffix = Path(urlparse(url).path).suffix.lower()
            if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
                suffix = ".webp"
            item = work / f"{index + 1:02d}{suffix}"
            _download_http(url, item, None, cancel_event)
            files.append(item)
        motion_file: Path | None = None
        if info.motion:
            motion_file = work / "motion.mp4"
            _download_http(info.motion, motion_file, None, cancel_event)

        import zipfile

        if motion_file is not None:
            pack = work / "live"
            try:
                from app.core import livephoto

                livephoto.build_live_pack(files[0], motion_file, pack, info.video_id or "Live")
                entries = sorted(path for path in pack.rglob("*") if path.is_file())
                with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
                    for entry in entries:
                        archive.write(entry, arcname=str(entry.relative_to(pack)))
            except Exception:  # noqa: BLE001 - keep the raw components rather than fail
                with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
                    for item in files:
                        archive.write(item, arcname=item.name)
                    archive.write(motion_file, arcname="motion.mp4")
                    archive.writestr("说明.txt", "实况转换所需的 ffmpeg / piexif 不可用，已保留原始图片和动态视频。\n")
        else:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
                for index, item in enumerate(files):
                    archive.write(item, arcname=f"{index + 1:02d}{item.suffix}")
        if progress:
            progress({"status": "finished", "downloaded_bytes": target.stat().st_size,
                      "total_bytes": target.stat().st_size, "filename": str(target)})
        return target, info
    finally:
        shutil.rmtree(work, ignore_errors=True)


def download(
    url: str,
    settings,
    preset_key: str = "best",
    progress: Callable[[dict[str, Any]], None] | None = None,
    cancel_event=None,
    outdir: str | Path | None = None,
) -> tuple[Path, DouyinInfo]:
    info = resolve(url)
    if info.is_images:
        try:
            return _download_images(info, settings, progress, cancel_event, outdir)
        except DouyinCancelled:
            raise
        except DouyinError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DouyinError(f"抖音图文下载失败：{exc}") from exc
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
