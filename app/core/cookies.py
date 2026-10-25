"""Cookie helpers: browser auto-read, cookies.txt validation, JSON conversion."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrowserOption:
    key: str
    label: str
    platforms: tuple[str, ...] = ("darwin", "win32", "linux")

    def available(self) -> bool:
        return sys.platform.startswith(self.platforms) if self.platforms else True


BROWSERS: tuple[BrowserOption, ...] = (
    BrowserOption("chrome", "Google Chrome"),
    BrowserOption("edge", "Microsoft Edge"),
    BrowserOption("firefox", "Mozilla Firefox"),
    BrowserOption("brave", "Brave"),
    BrowserOption("chromium", "Chromium"),
    BrowserOption("opera", "Opera"),
    BrowserOption("vivaldi", "Vivaldi"),
    BrowserOption("safari", "Safari", ("darwin",)),
)


def browser_options(include_none: bool = True, lang: str = "zh") -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    if include_none:
        options.append(("", "不使用 Cookie（免登录内容）" if lang != "en" else "No cookies"))
    for browser in BROWSERS:
        if browser.available():
            options.append((browser.key, browser.label))
    return options


def cookiesfrombrowser(key: str) -> tuple[str, None, None, None] | None:
    """yt-dlp's ``cookiesfrombrowser`` tuple, or None."""
    key = (key or "").strip().lower()
    if not key:
        return None
    valid = {b.key for b in BROWSERS}
    if key not in valid:
        return None
    return (key, None, None, None)


# --- cookies.txt ------------------------------------------------------------
_NETSCAPE_HEADER = "# Netscape HTTP Cookie File"


def validate_cookiefile(path: str | Path) -> tuple[bool, str]:
    """Check a cookies.txt-style file; returns (ok, human message)."""
    if not path:
        return False, "未选择 Cookie 文件" if True else "No cookie file selected"
    p = Path(path).expanduser()
    if not p.is_file():
        return False, f"文件不存在：{p}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"无法读取文件：{exc}"
    if not text.strip():
        return False, "Cookie 文件为空"
    if text.lstrip().startswith("["):
        # JSON export (EditThisCookie / Cookie-Editor)
        try:
            data = json.loads(text)
            if isinstance(data, list) and data:
                return True, "检测到 JSON 格式 Cookie，将在使用时自动转换"
        except ValueError:
            return False, "JSON 格式无法解析"
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if not lines:
        return False, "Cookie 文件中没有有效条目"
    fields = lines[0].split("\t")
    if len(fields) < 6:
        return False, "不是标准的 Netscape cookies.txt 格式（至少需要 6 个制表符分隔字段）"
    return True, f"有效，共 {len(lines)} 条 Cookie"


def convert_json_cookies(json_path: str | Path) -> Path:
    """Convert a JSON cookie export into Netscape cookies.txt next to it."""
    src = Path(json_path).expanduser()
    data = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("cookies", [])
    lines = ["# Netscape HTTP Cookie File", "# Converted by 视频下载器", ""]
    now = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "")
        if not domain:
            continue
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        path = str(item.get("path") or "/")
        secure = "TRUE" if item.get("secure") else "FALSE"
        expires = item.get("expirationDate") or item.get("expires") or item.get("expiry") or 0
        try:
            expires = int(float(expires))
        except (TypeError, ValueError):
            expires = 0
        if expires and expires < now:
            continue
        name = str(item.get("name") or "")
        value = str(item.get("value") or "")
        if not name:
            continue
        lines.append("\t".join([domain, include_sub, path, secure, str(expires), name, value]))
    out = src.with_name(src.stem + ".cookies.txt")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def prepare_cookiefile(path: str | Path) -> str:
    """Return a path yt-dlp can consume, converting JSON exports on the fly."""
    if not path:
        return ""
    p = Path(path).expanduser()
    if p.suffix.lower() == ".json":
        try:
            return str(convert_json_cookies(p))
        except Exception:
            return str(p)
    return str(p)


def guess_installed_browsers() -> list[tuple[str, str]]:
    """Best-effort detection of which browsers exist on this machine."""
    found: list[tuple[str, str]] = []
    if sys.platform == "darwin":
        checks = {
            "chrome": "/Applications/Google Chrome.app",
            "edge": "/Applications/Microsoft Edge.app",
            "brave": "/Applications/Brave Browser.app",
            "firefox": "/Applications/Firefox.app",
            "safari": "/Applications/Safari.app",
            "opera": "/Applications/Opera.app",
            "vivaldi": "/Applications/Vivaldi.app",
        }
        for key, app in checks.items():
            if os.path.exists(app):
                found.append((key, key.title()))
    elif os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        program = os.environ.get("ProgramFiles", "")
        program86 = os.environ.get("ProgramFiles(x86)", "")
        checks = {
            "chrome": [rf"{local}\Google\Chrome\Application\chrome.exe",
                       rf"{program}\Google\Chrome\Application\chrome.exe"],
            "edge": [rf"{program86}\Microsoft\Edge\Application\msedge.exe",
                     rf"{program}\Microsoft\Edge\Application\msedge.exe"],
            "brave": [rf"{program}\BraveSoftware\Brave-Browser\Application\brave.exe"],
            "firefox": [rf"{program}\Mozilla Firefox\firefox.exe"],
        }
        for key, candidates in checks.items():
            if any(os.path.exists(c) for c in candidates):
                found.append((key, key.title()))
    else:
        for key in ("chrome", "chromium", "firefox", "brave"):
            for name in (key, f"{key}-browser"):
                from shutil import which

                if which(name):
                    found.append((key, key.title()))
                    break
    return found


def cookie_hint(lang: str = "zh") -> str:
    if lang == "en":
        return ("Sign in with your browser first, then choose that browser here. "
                "视频下载器 only reads cookies locally; nothing is uploaded.")
    return ("请先在浏览器里登录目标网站，再在这里选择对应的浏览器。"
            "视频下载器 只在本机读取 Cookie，不会上传任何数据。")
