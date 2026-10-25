"""Quality presets, yt-dlp format selectors and format-table helpers.

Pure functions only: no Qt, no network. The UI asks this module what to show
and which format string to hand to yt-dlp.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VIDEO_HEIGHTS = (2160, 1440, 1080, 720, 480)


@dataclass(frozen=True)
class Preset:
    key: str
    zh: str
    en: str
    kind: str  # "video" | "audio" | "custom"
    height: int | None = None
    audio_codec: str = ""
    hint_zh: str = ""
    hint_en: str = ""

    @property
    def label(self) -> str:
        return self.zh

    def label_for(self, lang: str) -> str:
        return self.en if lang == "en" else self.zh

    def hint_for(self, lang: str) -> str:
        return self.hint_en if lang == "en" else self.hint_zh


PRESETS: tuple[Preset, ...] = (
    Preset("best", "最佳画质（自动合并）", "Best quality (auto merge)", "video", None,
           hint_zh="优先最高分辨率，画面与声音自动合并",
           hint_en="Highest resolution, video and audio merged automatically"),
    Preset("2160", "4K · 2160P", "4K · 2160P", "video", 2160,
           hint_zh="需要站点提供 4K 且通常需要登录 Cookie",
           hint_en="Requires 4K source; usually needs login cookies"),
    Preset("1440", "2K · 1440P", "2K · 1440P", "video", 1440),
    Preset("1080", "1080P 全高清", "1080P Full HD", "video", 1080,
           hint_zh="B 站 1080P+ 需要大会员 Cookie",
           hint_en="Bilibili 1080P+ requires member cookies"),
    Preset("720", "720P 高清", "720P HD", "video", 720),
    Preset("480", "480P 流畅", "480P", "video", 480),
    Preset("audio-mp3", "仅音频 · MP3", "Audio only · MP3", "audio", None, "mp3",
           hint_zh="转成通用 MP3，适合播客/音乐",
           hint_en="Universal MP3, great for podcasts and music"),
    Preset("audio-m4a", "仅音频 · M4A 原声", "Audio only · M4A", "audio", None, "m4a",
           hint_zh="不转码，保留原始音质",
           hint_en="No re-encode, keeps the original audio quality"),
    Preset("custom", "自定义格式", "Custom format", "custom", None,
           hint_zh="高级：直接填写格式表达式，例如 137+140",
           hint_en="Advanced: raw yt-dlp format expression, e.g. 137+140"),
)

PRESET_MAP = {p.key: p for p in PRESETS}


def get_preset(key: str) -> Preset:
    return PRESET_MAP.get(key or "best", PRESET_MAP["best"])


def is_audio_preset(key: str) -> bool:
    return get_preset(key).kind == "audio"


def build_format_selector(preset_key: str, custom: str = "") -> str:
    """Return the yt-dlp ``format`` string for a preset."""
    preset = get_preset(preset_key)
    if preset.kind == "custom":
        return (custom or "").strip() or "bv*+ba/b"
    if preset.kind == "audio":
        return "bestaudio/best"
    if preset.height:
        h = preset.height
        return (
            f"bestvideo[height<={h}]+bestaudio/"
            f"best[height<={h}]/bestvideo+bestaudio/best"
        )
    return "bestvideo*+bestaudio/best"


def audio_postprocessor(preset_key: str) -> dict[str, Any] | None:
    preset = get_preset(preset_key)
    if preset.kind != "audio":
        return None
    codec = preset.audio_codec or "mp3"
    return {
        "key": "FFmpegExtractAudio",
        "preferredcodec": codec,
        "preferredquality": "0",  # best VBR
    }


@dataclass(frozen=True)
class FormatRow:
    format_id: str
    ext: str
    height: int | None
    width: int | None
    fps: float | None
    vcodec: str
    acodec: str
    tbr: float | None
    filesize: int | None
    note: str = ""
    is_audio: bool = False

    @property
    def resolution(self) -> str:
        if self.height:
            if self.width:
                return f"{self.width}×{self.height}"
            return f"{self.height}P"
        return "audio" if self.is_audio else "?"

    def label_for(self, lang: str = "zh") -> str:
        bits = [self.resolution]
        if self.fps and self.fps >= 48:
            bits.append(f"{int(round(self.fps))}fps")
        bits.append(self.ext.upper())
        if self.vcodec and not self.is_audio:
            bits.append(self.vcodec.split(".")[0])
        if self.is_audio and self.acodec:
            bits.append(self.acodec.split(".")[0])
        return " · ".join(bits)


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "", 0) else None
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def classify_formats(info: dict[str, Any] | None) -> list[FormatRow]:
    """Turn ``info['formats']`` into a de-duplicated, sorted list for the UI."""
    if not info:
        return []
    rows: list[FormatRow] = []
    seen: set[tuple] = set()
    for fmt in info.get("formats") or []:
        if not isinstance(fmt, dict):
            continue
        vcodec = str(fmt.get("vcodec") or "none")
        acodec = str(fmt.get("acodec") or "none")
        is_audio = vcodec == "none" and acodec != "none"
        height = _to_int(fmt.get("height"))
        if not is_audio and not height:
            continue  # image/storyboard/etc.
        filesize = _to_int(fmt.get("filesize")) or _to_int(fmt.get("filesize_approx"))
        row = FormatRow(
            format_id=str(fmt.get("format_id") or ""),
            ext=str(fmt.get("ext") or ""),
            height=height,
            width=_to_int(fmt.get("width")),
            fps=_to_float(fmt.get("fps")),
            vcodec=vcodec,
            acodec=acodec,
            tbr=_to_float(fmt.get("tbr")),
            filesize=filesize,
            note=str(fmt.get("format_note") or ""),
            is_audio=is_audio,
        )
        key = (row.height, row.ext, row.vcodec, row.acodec, row.format_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    def sort_key(row: FormatRow):
        return (0 if row.is_audio else 1, row.height or 0, row.tbr or 0)

    rows.sort(key=sort_key, reverse=True)
    return rows


def available_heights(info: dict[str, Any] | None) -> set[int]:
    heights: set[int] = set()
    for row in classify_formats(info):
        if row.height:
            heights.add(row.height)
    return heights


def preset_availability(info: dict[str, Any] | None, lang: str = "zh") -> list[tuple[Preset, bool, str]]:
    """Presets in display order with an availability flag and a short hint."""
    heights = available_heights(info)
    max_height = max(heights) if heights else 0
    out: list[tuple[Preset, bool, str]] = []
    for preset in PRESETS:
        ok = True
        hint = preset.hint_for(lang)
        if preset.height and heights:
            # A preset is meaningful only when the source can actually reach it;
            # otherwise the selector would silently fall back to a lower quality.
            ok = max_height >= preset.height
            if not ok:
                hint = (f"该视频最高 {max_height}P" if lang != "en"
                        else f"This video maxes out at {max_height}P")
        out.append((preset, ok, hint))
    return out


def guess_title(info: dict[str, Any] | None, fallback: str = "") -> str:
    if not info:
        return fallback
    return str(info.get("title") or info.get("id") or fallback or "未命名")


def summarize(info: dict[str, Any] | None) -> dict[str, Any]:
    """Small dict consumed by the media card."""
    info = info or {}
    duration = _to_float(info.get("duration"))
    return {
        "id": str(info.get("id") or ""),
        "title": guess_title(info),
        "uploader": str(info.get("uploader") or info.get("channel") or info.get("creator") or ""),
        "duration": duration,
        "thumbnail": str(info.get("thumbnail") or ""),
        "extractor": str(info.get("extractor_key") or info.get("extractor") or ""),
        "webpage_url": str(info.get("webpage_url") or ""),
        "is_playlist": bool(info.get("_type") == "playlist" or info.get("entries")),
        "playlist_count": len(info.get("entries") or []) if info.get("entries") else 0,
        "view_count": _to_int(info.get("view_count")),
        "upload_date": str(info.get("upload_date") or ""),
        "description": str(info.get("description") or "")[:400],
    }


def format_bytes(num: int | None) -> str:
    from app.core.paths import human_size

    return human_size(num)
