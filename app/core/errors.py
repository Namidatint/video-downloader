"""Turn raw yt-dlp failures into human problems with one-click fixes.

Design goals
------------
* Every known failure has a stable ``code`` so the UI can customise behaviour.
* Messages are bilingual (zh / en) and written for non-technical users.
* Each problem carries ``Fix`` actions the UI can render as buttons. The UI
  owns the actual behaviour (open settings, retry, open browser, ...); this
  module stays free of Qt and of side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- Fix action ids (also used by the UI) --------------------------------
ACTION_RETRY = "retry"
ACTION_SETTINGS = "open_settings"
ACTION_COOKIES = "open_cookies"
ACTION_LOGIN = "open_login"
ACTION_DIAGNOSTICS = "open_diagnostics"
ACTION_FFMPEG = "fix_ffmpeg"
ACTION_PROXY = "open_proxy"
ACTION_UPDATE = "update_core"
ACTION_OPEN_DIR = "open_output_dir"
ACTION_OPEN_URL = "open_url"
ACTION_COPY = "copy_raw"


@dataclass(frozen=True)
class Fix:
    action: str
    label: str
    label_en: str = ""
    url: str = ""

    def text(self, lang: str = "zh") -> str:
        return self.label_en if lang == "en" and self.label_en else self.label


@dataclass(frozen=True)
class Problem:
    code: str
    title: str
    detail: str
    fixes: tuple[Fix, ...] = ()
    raw: str = ""
    severity: str = "error"  # error | warning | info
    docs_url: str = ""

    def title_for(self, lang: str = "zh") -> str:
        return self.title

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "raw": self.raw,
            "severity": self.severity,
            "fixes": [
                {"action": f.action, "label": f.label, "label_en": f.label_en, "url": f.url}
                for f in self.fixes
            ],
        }


@dataclass(frozen=True)
class _Rule:
    code: str
    pattern: re.Pattern[str]
    zh: tuple[str, str]
    en: tuple[str, str]
    fixes: tuple[Fix, ...] = ()
    severity: str = "error"


def _rule(code: str, pattern: str, zh_title: str, zh_detail: str,
          en_title: str, en_detail: str, fixes=(), severity="error") -> _Rule:
    return _Rule(code, re.compile(pattern, re.I), (zh_title, zh_detail),
                 (en_title, en_detail), tuple(fixes), severity)


# Ordered: first match wins. Specific patterns must precede generic ones.
RULES: tuple[_Rule, ...] = (
    _rule(
        "cancelled", r"DownloadCancelled|download cancelled by user|interrupted by user",
        "下载已取消", "任务已停止，已下载的分片会保留，下次可断点续传。",
        "Download cancelled", "The task stopped; partial data is kept for resuming.",
        fixes=(Fix(ACTION_RETRY, "继续下载", "Resume"),),
        severity="info",
    ),
    _rule(
        "ffmpeg_missing",
        r"ffmpeg (?:is )?not (?:installed|found)|ffprobe.*not found|Postprocessing: ffmpeg|"
        r"requested merging of multiple formats but ffmpeg is not installed|"
        r"ffmpeg.*(?:unable|missing)|You have requested merging",
        "缺少 ffmpeg，无法合并音视频",
        "高清视频的画面和声音是分开的两条流，需要 ffmpeg 合并。GlowDL 自带 ffmpeg，"
        "通常一键修复即可；若你手动指定过 ffmpeg 路径，请检查该路径是否有效。",
        "ffmpeg is missing",
        "High-quality video and audio are separate streams and must be merged by ffmpeg. "
        "GlowDL bundles ffmpeg — run the fix; if you set a custom path, verify it.",
        fixes=(Fix(ACTION_FFMPEG, "自动修复 ffmpeg", "Fix ffmpeg automatically"),
               Fix(ACTION_DIAGNOSTICS, "运行环境自检", "Run diagnostics")),
    ),
    _rule(
        "bot_check",
        r"Sign in to confirm (?:you'?re|you are|that you are) not a bot|"
        r"confirm you'?re not a bot|Please sign in|This content isn'?t available.*bot|"
        r"unusual traffic",
        "站点要求验证真人身份",
        "YouTube 等站点判定当前网络异常，需要浏览器登录态。到「设置 → Cookie」选择你已登录的浏览器，"
        "或导入 cookies.txt 后重试。",
        "The site wants to verify you are human",
        "The site flagged this network. Pick a browser you are signed in to under "
        "Settings → Cookies, or import a cookies.txt file, then retry.",
        fixes=(Fix(ACTION_COOKIES, "读取浏览器 Cookie", "Use browser cookies"),
               Fix(ACTION_LOGIN, "打开登录页", "Open login page"),
               Fix(ACTION_RETRY, "重试", "Retry")),
    ),
    _rule(
        "login_required",
        r"login required|only available (?:for|to) (?:registered|logged.?in)|"
        r"requires? (?:authentication|login)|This video is only available for",
        "该内容需要登录后才能访问",
        "B 站高画质、会员内容或私密视频需要账号登录态。请先在浏览器登录，再让 GlowDL 读取该浏览器的 Cookie。",
        "Login required",
        "HD quality, member-only or private content needs a signed-in session. "
        "Sign in with your browser, then let GlowDL read that browser's cookies.",
        fixes=(Fix(ACTION_COOKIES, "读取浏览器 Cookie", "Use browser cookies"),
               Fix(ACTION_LOGIN, "打开站点登录", "Open site login"),
               Fix(ACTION_RETRY, "重试", "Retry")),
    ),
    _rule(
        "drm",
        r"DRM|digital rights management|protected by (?:DRM|widevine)|widevine",
        "该视频受 DRM 版权保护",
        "DRM 加密内容无法通过下载器获取，这是版权保护机制，GlowDL 不会也不应绕过。"
        "请通过官方客户端观看。",
        "DRM protected",
        "DRM-encrypted content cannot be downloaded; this is copy protection and GlowDL will "
        "not bypass it. Please use the official player.",
        severity="warning",
    ),
    _rule(
        "geo_blocked",
        r"not available in your country|geo.?restrict|blocked in your (?:country|region)|"
        r"video is not available in your location",
        "该视频在你所在地区不可用",
        "这是站点按地区限制内容，需要对应地区的网络出口。可在「设置 → 网络」配置代理后重试。",
        "Region blocked",
        "The site restricts this video by region. Configure a proxy under Settings → Network.",
        fixes=(Fix(ACTION_PROXY, "配置代理", "Configure proxy"),),
    ),
    _rule(
        "membership",
        r"members.?only|paid|purchase|rental|premium (?:only|required)|"
        r"This video requires payment",
        "该内容需要会员或购买",
        "付费/会员专享内容不会因为登录而解锁；GlowDL 不会绕过付费墙。",
        "Member-only content",
        "Paid or membership content is not unlocked by signing in; GlowDL does not bypass paywalls.",
        severity="warning",
    ),
    _rule(
        "private_video",
        r"private video|this video is private|video is private",
        "这是一个私享视频",
        "视频所有者设置了不公开，只有获得授权的账号才能访问。请确认账号有权限，并读取对应浏览器的 Cookie。",
        "Private video",
        "The owner restricted this video. Make sure your account has access, then use its cookies.",
        fixes=(Fix(ACTION_COOKIES, "读取浏览器 Cookie", "Use browser cookies"),),
    ),
    _rule(
        "unavailable",
        r"video unavailable|this video (?:is|has been) (?:removed|deleted)|"
        r"content is not available|no video formats found|does not exist|"
        r"no video could be found",
        "视频不存在或已下架",
        "链接可能失效、内容被删除，或页面需要登录/脚本才能解析。可尝试在浏览器打开原链接确认。",
        "Video unavailable",
        "The link may be dead, the video removed, or the page needs a signed-in session.",
        fixes=(Fix(ACTION_OPEN_URL, "在浏览器中打开", "Open in browser"),
               Fix(ACTION_RETRY, "重试", "Retry")),
    ),
    _rule(
        "unsupported_url",
        r"unsupported url|no suitable extractor|is not a valid URL|Invalid URL",
        "暂不支持这个链接",
        "请确认粘贴的是具体视频页链接（而不是搜索结果页/首页）。部分站点需要登录或已停止支持。",
        "Unsupported URL",
        "Paste a direct video page URL (not a search/home page). Some sites need login or "
        "are no longer supported.",
        fixes=(Fix(ACTION_RETRY, "重新解析", "Try another URL"),),
    ),
    _rule(
        "rate_limited",
        r"HTTP Error 429|Too Many Requests|rate.?limit",
        "请求过于频繁，被站点限流",
        "稍等几分钟再试，或在设置里降低并发数、开启限速。",
        "Rate limited (429)",
        "Wait a few minutes, lower concurrency, or enable a speed limit in Settings.",
        fixes=(Fix(ACTION_RETRY, "稍后重试", "Retry later"),
               Fix(ACTION_SETTINGS, "降低并发", "Lower concurrency")),
    ),
    _rule(
        "forbidden_403",
        r"HTTP Error 403|403 Forbidden|Access denied",
        "站点拒绝了本次请求（403）",
        "常见原因：需要登录 Cookie、需要正确的 User-Agent/Referer、或 IP 被风控。"
        "建议读取浏览器 Cookie 后重试；抖音/小红书等站点还需在浏览器里先能正常播放。",
        "Request forbidden (403)",
        "Usually missing cookies, wrong UA/Referer, or IP risk control. Use browser cookies; "
        "for Douyin/Xiaohongshu make sure playback works in the browser first.",
        fixes=(Fix(ACTION_COOKIES, "读取浏览器 Cookie", "Use browser cookies"),
               Fix(ACTION_RETRY, "重试", "Retry")),
    ),
    _rule(
        "http_404",
        r"HTTP Error 404|404 Not Found",
        "链接指向的页面不存在（404）",
        "请检查链接是否完整、视频是否已被删除。",
        "Not found (404)",
        "Check the URL is complete and the video still exists.",
    ),
    _rule(
        "format_unavailable",
        r"Requested format is not available|requested format not available|"
        r"No video formats found|format is not available",
        "所选画质不可用",
        "该视频没有你选择的清晰度（例如只有 720P）。改用「最佳画质」重新解析即可。",
        "Requested format unavailable",
        "This video does not offer the selected quality. Try the “Best” preset again.",
        fixes=(Fix(ACTION_RETRY, "改用最佳画质", "Use best quality"),),
    ),
    _rule(
        "ssl_error",
        r"certificate verify failed|SSL: |CERTIFICATE_VERIFY_FAILED|ssl error",
        "HTTPS 证书校验失败",
        "系统缺少根证书、或代理软件做了 HTTPS 拦截。可在「设置 → 网络」关闭/调整代理，"
        "或点击修复让 GlowDL 使用内置证书库。",
        "TLS certificate verification failed",
        "Missing root certificates or a TLS-intercepting proxy. Adjust proxy settings or let "
        "GlowDL use its bundled certificate store.",
        fixes=(Fix(ACTION_DIAGNOSTICS, "运行网络自检", "Run network check"),
               Fix(ACTION_PROXY, "配置代理", "Configure proxy")),
    ),
    _rule(
        "proxy_error",
        r"ProxyError|Unable to connect to proxy|proxy.*(?:refused|failed)|"
        r"Cannot connect to proxy",
        "代理连接失败",
        "检查代理地址与端口是否正确、代理软件是否在运行；不需要代理时请留空。",
        "Proxy connection failed",
        "Verify the proxy host/port and that the proxy app is running; leave it empty if unused.",
        fixes=(Fix(ACTION_PROXY, "打开代理设置", "Open proxy settings"),
               Fix(ACTION_RETRY, "重试", "Retry")),
    ),
    _rule(
        "dns_error",
        r"Failed to resolve|Name or service not known|nodename nor servname|getaddrinfo",
        "域名解析失败",
        "网络可能被中断，或 DNS 被污染。检查网络连接，必要时配置代理后重试。",
        "DNS resolution failed",
        "Check your connection; if needed configure a proxy and retry.",
        fixes=(Fix(ACTION_PROXY, "配置代理", "Configure proxy"),
               Fix(ACTION_RETRY, "重试", "Retry")),
    ),
    _rule(
        "timeout",
        r"timed out|Timeout|read timeout|Connection reset|Remote end closed",
        "网络超时或被重置",
        "站点响应太慢或连接被中断。GlowDL 会自动重试；也可以降低并发、开启代理后再试。",
        "Network timeout",
        "The site was slow or the connection was reset. GlowDL retries automatically; lower "
        "concurrency or use a proxy if it persists.",
        fixes=(Fix(ACTION_RETRY, "重试", "Retry"),
               Fix(ACTION_SETTINGS, "降低并发", "Lower concurrency")),
    ),
    _rule(
        "network_error",
        r"Unable to download webpage|Unable to download video data|ConnectionError|"
        r"Network is unreachable|urlopen error|Failed to establish a new connection|"
        r"Max retries exceeded|Connection reset",
        "网络连接失败",
        "请检查网络是否正常。若访问境外站点，请在「设置 → 网络」配置代理。",
        "Network error",
        "Check your connection. For overseas sites, configure a proxy under Settings → Network.",
        fixes=(Fix(ACTION_RETRY, "重试", "Retry"),
               Fix(ACTION_PROXY, "配置代理", "Configure proxy")),
    ),
    _rule(
        "disk_full",
        r"No space left|not enough space|ENOSPC|disk full",
        "磁盘空间不足",
        "清理磁盘或更换下载目录后重试。",
        "Disk is full",
        "Free up space or choose another output folder.",
        fixes=(Fix(ACTION_SETTINGS, "更换下载目录", "Change output folder"),),
    ),
    _rule(
        "permission_denied",
        r"Permission denied|EACCES|Read-only file system|Access is denied",
        "没有写入权限",
        "下载目录不可写，请在设置里换一个目录（例如“下载”文件夹）。",
        "Permission denied",
        "The output folder is not writable. Choose another folder in Settings.",
        fixes=(Fix(ACTION_SETTINGS, "更换下载目录", "Change output folder"),),
    ),
    _rule(
        "live_not_started",
        r"This live event will begin|premieres in|live event has not yet started",
        "直播/首播尚未开始",
        "等开播后再下载；已经开始的可从「正在直播」状态直接抓取。",
        "Live has not started",
        "Wait until it starts; ongoing streams can be downloaded directly.",
        severity="warning",
    ),
    _rule(
        "postprocess_failed",
        r"Postprocessing:|Postprocessor|Unable to convert|Conversion failed|"
        r"Error opening input|Invalid data found when processing input",
        "下载完成但后处理失败",
        "通常是源文件损坏或 ffmpeg 无法识别封装格式。可在设置里关闭“合并为 MP4/嵌入封面”等选项后重试。",
        "Post-processing failed",
        "Usually a broken source or an unsupported container. Turn off MP4 merge/thumbnail "
        "embedding in Settings and retry.",
        fixes=(Fix(ACTION_SETTINGS, "调整后处理选项", "Adjust post-processing"),
               Fix(ACTION_FFMPEG, "修复 ffmpeg", "Fix ffmpeg")),
    ),
    _rule(
        "extractor_broken",
        r"Unable to extract|extractor.*(?:broken|failed)|"
        r"Failed to parse JSON|KeyError|IndexError|no such option",
        "解析器需要更新",
        "站点改版后旧版 yt-dlp 会解析失败。点击「更新内核」升级到最新版通常即可解决。",
        "Extractor needs an update",
        "The site changed and this yt-dlp version can no longer parse it. Update the core.",
        fixes=(Fix(ACTION_UPDATE, "更新内核", "Update core"),
               Fix(ACTION_RETRY, "重试", "Retry")),
    ),
)

GENERIC = Problem(
    code="generic",
    title="下载失败",
    detail="这是一个未归类的错误。可展开“原始信息”查看细节，或运行「问题诊所」自检后重试。",
    fixes=(Fix(ACTION_RETRY, "重试", "Retry"),
           Fix(ACTION_DIAGNOSTICS, "运行自检", "Run diagnostics")),
)

# Strip yt-dlp/ffmpeg noise so we can match the meaningful tail of the message.
_PREFIX_RE = re.compile(
    r"^(?:\s*\[[^\]]+\]\s*)?(?:ERROR|WARNING):\s*", re.I)


def translate(raw: str | BaseException | None, lang: str = "zh") -> Problem:
    """Map a raw error message/exception to a :class:`Problem`."""
    if raw is None:
        return GENERIC
    text = str(raw)
    if isinstance(raw, BaseException) and not text:
        text = raw.__class__.__name__
    needle = _PREFIX_RE.sub("", text.strip())
    for rule in RULES:
        if rule.pattern.search(needle) or rule.pattern.search(text):
            zh_title, zh_detail = rule.zh
            en_title, en_detail = rule.en
            fixes = rule.fixes
            if lang == "en":
                return Problem(rule.code, en_title, en_detail, fixes, raw=text,
                               severity=rule.severity)
            return Problem(rule.code, zh_title, zh_detail, fixes, raw=text,
                           severity=rule.severity)
    detail = GENERIC.detail
    generic = Problem(GENERIC.code, GENERIC.title, detail, GENERIC.fixes, raw=text)
    return generic


def problem_by_code(code: str, lang: str = "zh", raw: str = "") -> Problem:
    for rule in RULES:
        if rule.code == code:
            zh_t, zh_d = rule.zh
            en_t, en_d = rule.en
            if lang == "en":
                return Problem(code, en_t, en_d, rule.fixes, raw=raw, severity=rule.severity)
            return Problem(code, zh_t, zh_d, rule.fixes, raw=raw, severity=rule.severity)
    return Problem(GENERIC.code, GENERIC.title, GENERIC.detail, GENERIC.fixes, raw=raw)


def catalog(lang: str = "zh") -> list[Problem]:
    """All known problems, for the in-app problem library (问题诊所)."""
    return [problem_by_code(rule.code, lang) for rule in RULES]
