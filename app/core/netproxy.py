"""System proxy detection and connectivity checks.

Why this exists: on macOS/Windows a desktop app inherits the OS proxy. If the
user turns off Clash/Surge/V2Ray but leaves the system proxy enabled, every
request fails with ``Connection refused`` to a local port — which reads like a
GlowDL bug. The app now has an explicit network mode and names this failure.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from urllib.parse import urlparse


def _normalize(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = "http://" + value
    return value


def system_proxy() -> str:
    """Best-effort read of the OS/environment proxy. Empty string = none."""
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
                "ALL_PROXY", "all_proxy"):
        value = os.environ.get(key)
        if value:
            return _normalize(value)
    try:
        if sys.platform == "darwin":
            return _macos_proxy()
        if sys.platform.startswith("win"):
            return _windows_proxy()
    except Exception:
        return ""
    return ""


def _macos_proxy() -> str:
    output = subprocess.run(
        ["scutil", "--proxy"], capture_output=True, text=True, timeout=2
    ).stdout
    for scheme, prefix in (("https", "HTTPS"), ("http", "HTTP")):
        if re.search(rf"{prefix}Enable\s*:\s*1", output):
            host = re.search(rf"{prefix}Proxy\s*:\s*(\S+)", output)
            port = re.search(rf"{prefix}Port\s*:\s*(\d+)", output)
            if host and port:
                return _normalize(f"{scheme}://{host.group(1)}:{port.group(1)}")
    return ""


def _windows_proxy() -> str:
    import winreg  # type: ignore[import-not-found]

    path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if not enabled:
            return ""
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
    if not server:
        return ""
    if "=" in server:  # "http=host:port;https=host:port"
        parts = dict(item.split("=", 1) for item in server.split(";") if "=" in item)
        server = parts.get("https") or parts.get("http") or next(iter(parts.values()))
    return _normalize(server)


def host_port(proxy: str) -> tuple[str, int]:
    parsed = urlparse(proxy)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname or "", int(port)


def probe(proxy: str, timeout: float = 3.0) -> tuple[bool, str]:
    """TCP-level check that the proxy port is accepting connections."""
    if not proxy:
        return True, "未配置代理"
    host, port = host_port(proxy)
    if not host:
        return False, "代理地址无效"
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} 可连接"
    except OSError as exc:
        return False, f"无法连接 {host}:{port}（{exc.strerror or exc}）"


def is_loopback(proxy: str) -> bool:
    host, _ = host_port(proxy)
    return host in ("127.0.0.1", "localhost", "::1")
