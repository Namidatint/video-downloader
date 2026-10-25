"""Environment self-check ("问题诊所" / problem clinic) — no Qt, no side effects.

Runs a list of cheap checks and returns structured results with the same Fix
actions used by error translation, so the UI can render one-click repairs.
"""

from __future__ import annotations

import os
import shutil
import socket
import ssl
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field

from app.core import cookies as cookies_mod
from app.core.errors import (ACTION_COOKIES, ACTION_DIRECT, ACTION_FFMPEG, ACTION_PROXY,
                             ACTION_SETTINGS, ACTION_UPDATE, Fix)
from app.core import netproxy
from app.core.ffmpeg_tools import find_ffmpeg
from app.core.settings import Settings

PASS = "pass"
WARN = "warn"
FAIL = "fail"


@dataclass
class CheckResult:
    key: str
    title: str
    status: str
    detail: str
    fix: Fix | None = None
    extra: dict = field(default_factory=dict)


def _python_check() -> CheckResult:
    version = ".".join(str(x) for x in sys.version_info[:3])
    ok = sys.version_info >= (3, 9)
    return CheckResult(
        "python", "运行环境 Python", PASS if ok else FAIL,
        f"Python {version}（{sys.platform}）",
    )


def _ytdlp_check(settings: Settings) -> CheckResult:
    try:
        import yt_dlp

        version = getattr(yt_dlp.version, "__version__", "unknown")
    except Exception as exc:  # pragma: no cover - broken install
        return CheckResult("yt_dlp", "解析组件", FAIL,
                           f"未安装或无法导入：{exc}",
                           fix=Fix(ACTION_UPDATE, "安装/更新组件", "Install component"))
    return CheckResult(
        "yt_dlp", "解析组件", PASS, "已内置，无需安装",
        extra={"version": version},
    )


def _ffmpeg_check(settings: Settings) -> CheckResult:
    status = find_ffmpeg(settings.custom_ffmpeg)
    if status.available:
        return CheckResult("ffmpeg", "音视频合并", PASS, "已就绪",
                           extra={"path": status.path})
    return CheckResult("ffmpeg", "音视频合并", FAIL,
                       "音视频组件缺失，高清视频将无法合并音轨",
                       fix=Fix(ACTION_FFMPEG, "自动修复组件", "Fix component"))


def _postprocess_check() -> CheckResult:
    try:
        import mutagen  # noqa: F401

        return CheckResult("postprocess", "封面 / 元数据嵌入", PASS, "已就绪")
    except Exception:
        return CheckResult("postprocess", "封面 / 元数据嵌入", WARN,
                           "封面嵌入组件缺失，将跳过封面嵌入")


def _douyin_check() -> CheckResult:
    try:
        from app.core import douyin

        browser = douyin.find_browser()
    except Exception as exc:  # noqa: BLE001
        return CheckResult("douyin", "抖音原生解析", WARN, f"检查失败：{exc}")
    if browser:
        from pathlib import Path as _Path

        return CheckResult("douyin", "抖音原生解析", PASS,
                           f"使用本机 {_Path(browser[0]).stem} 解析（无需第三方接口）")
    return CheckResult("douyin", "抖音原生解析", WARN,
                       "未找到 Edge/Chrome；安装其中一个浏览器即可解析抖音链接")


def _output_dir_check(settings: Settings) -> CheckResult:
    try:
        folder = settings.output_dir
        with tempfile.NamedTemporaryFile(dir=str(folder), prefix=".glowdl-write-", delete=True):
            pass
        return CheckResult("output_dir", "下载目录可写", PASS, str(folder))
    except Exception as exc:
        return CheckResult("output_dir", "下载目录可写", FAIL,
                           f"目录不可写：{exc}",
                           fix=Fix(ACTION_SETTINGS, "更换下载目录", "Change folder"))


def _disk_check(settings: Settings, minimum_gb: float = 2.0) -> CheckResult:
    try:
        usage = shutil.disk_usage(str(settings.output_dir))
        free_gb = usage.free / (1024 ** 3)
        ok = free_gb >= minimum_gb
        return CheckResult("disk", "磁盘剩余空间", PASS if ok else WARN,
                           f"剩余 {free_gb:.1f} GB",
                           extra={"free_gb": round(free_gb, 2)})
    except Exception as exc:
        return CheckResult("disk", "磁盘剩余空间", WARN, f"无法读取：{exc}")


def _ssl_check() -> CheckResult:
    context = ssl.create_default_context()
    try:
        with socket.create_connection(("pypi.org", 443), timeout=6) as sock:
            with context.wrap_socket(sock, server_hostname="pypi.org") as tls:
                proto = tls.version() or "TLS"
        return CheckResult("ssl", "HTTPS 证书", PASS, f"证书校验正常（{proto}）")
    except ssl.SSLCertVerificationError as exc:
        return CheckResult("ssl", "HTTPS 证书链", FAIL, f"证书校验失败：{exc}")
    except OSError as exc:
        return CheckResult("ssl", "HTTPS 证书链", WARN, f"无法连接测试站点：{exc}")


def _site_probe(host: str, timeout: float = 6.0) -> tuple[bool, str]:
    try:
        request = urllib.request.Request(
            f"https://{host}/",
            headers={"User-Agent": "Mozilla/5.0 (GlowDL diagnostics)"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except Exception as exc:
        return False, str(exc)[:160]


def _network_check(settings: Settings) -> CheckResult:
    notes: list[str] = []
    ok_count = 0
    for host, label in (("www.bilibili.com", "B站"), ("www.youtube.com", "YouTube")):
        ok, detail = _site_probe(host)
        notes.append(f"{label}: {'可访问' if ok else '不可访问'}")
        ok_count += 1 if ok else 0
    if ok_count == 2:
        status = PASS
    elif ok_count == 1:
        status = WARN
    else:
        status = FAIL
    detail = "；".join(notes)
    fix = None
    if status != PASS:
        fix = Fix(ACTION_PROXY, "配置代理", "Configure proxy")
    return CheckResult("network", "站点连通性", status, detail, fix=fix)


def _proxy_check(settings: Settings) -> CheckResult:
    mode = getattr(settings, "proxy_mode", "system")
    if mode == "direct":
        return CheckResult("proxy", "网络模式 / 代理", PASS, "直连模式：不经过任何代理")

    if mode == "custom":
        proxy = settings.proxy
        if not proxy:
            return CheckResult("proxy", "网络模式 / 代理", WARN,
                               "自定义代理模式下地址为空，将按直连处理",
                               fix=Fix(ACTION_PROXY, "填写代理地址", "Set proxy"))
        ok, detail = netproxy.probe(proxy)
        if ok:
            return CheckResult("proxy", "网络模式 / 代理", PASS, f"自定义代理 {proxy}：{detail}")
        return CheckResult("proxy", "网络模式 / 代理", FAIL,
                           f"自定义代理不可用：{detail}",
                           fix=Fix(ACTION_DIRECT, "改为直连并重试", "Switch to direct"))

    # Follow the OS proxy.
    proxy = netproxy.system_proxy()
    if not proxy:
        return CheckResult("proxy", "网络模式 / 代理", PASS, "跟随系统：系统未启用代理")
    ok, detail = netproxy.probe(proxy)
    if ok:
        return CheckResult("proxy", "网络模式 / 代理", PASS, f"跟随系统：{proxy}（{detail}）")
    hint = "。如果只是下载国内站点，建议改为直连" if netproxy.is_loopback(proxy) else ""
    return CheckResult("proxy", "网络模式 / 代理", FAIL,
                       f"系统代理 {proxy} 不可用：{detail}{hint}",
                       fix=Fix(ACTION_DIRECT, "改为直连并重试", "Switch to direct"))


def _cookies_check(settings: Settings) -> CheckResult:
    if settings.cookies_file:
        ok, message = cookies_mod.validate_cookiefile(settings.cookies_file)
        return CheckResult("cookies", "登录 Cookie", PASS if ok else FAIL,
                           message,
                           fix=None if ok else Fix(ACTION_COOKIES, "重新导入 Cookie", "Import cookies"))
    if settings.cookies_browser:
        labels = dict(cookies_mod.browser_options(False))
        return CheckResult("cookies", "登录 Cookie", PASS,
                           f"从 {labels.get(settings.cookies_browser, settings.cookies_browser)} 读取")
    installed = cookies_mod.guess_installed_browsers()
    if installed:
        names = "、".join(label for _, label in installed)
        return CheckResult("cookies", "登录 Cookie", WARN,
                           f"未启用（检测到浏览器：{names}）。需要 1080P+/会员内容时再开启即可",
                           fix=Fix(ACTION_COOKIES, "读取浏览器 Cookie", "Use browser cookies"))
    return CheckResult("cookies", "登录 Cookie", WARN, "未启用（免登录内容可正常下载）")


def _platform_check() -> CheckResult:
    label = {"darwin": "macOS", "win32": "Windows"}.get(sys.platform, sys.platform)
    return CheckResult("platform", "运行平台", PASS, f"{label} · {os.path.abspath(os.sep)}")


def _safe(fn) -> CheckResult:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a broken check must not break the page
        return CheckResult("internal", "自检项目", WARN, f"检查时出现异常：{exc}")


def run_all(settings: Settings) -> list[CheckResult]:
    """Run every check concurrently (network probes are the slow part)."""
    from concurrent.futures import ThreadPoolExecutor

    probes = [
        lambda: _python_check(),
        lambda: _platform_check(),
        lambda: _ytdlp_check(settings),
        lambda: _ffmpeg_check(settings),
        lambda: _postprocess_check(),
        lambda: _douyin_check(),
        lambda: _output_dir_check(settings),
        lambda: _disk_check(settings),
        lambda: _proxy_check(settings),
        lambda: _network_check(settings),
        lambda: _ssl_check(),
        lambda: _cookies_check(settings),
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(_safe, probes))


def overall_status(checks: list[CheckResult]) -> str:
    if any(c.status == FAIL for c in checks):
        return FAIL
    if any(c.status == WARN for c in checks):
        return WARN
    return PASS


def fix_target(action: str, lang: str = "zh") -> str:
    """Human description of what a fix will do (used in the clinic page)."""
    mapping = {
        ACTION_FFMPEG: "重新定位/启用音视频组件",
        ACTION_SETTINGS: "打开设置页调整下载目录",
        ACTION_PROXY: "打开设置页配置代理",
        ACTION_COOKIES: "打开设置页选择浏览器 Cookie",
        ACTION_UPDATE: "检查并更新解析组件",
    }
    return mapping.get(action, "")
