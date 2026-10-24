"""Core unit tests: paths, formats, errors, settings, history, cookies, updater."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import cookies, errors, formats, history, paths, settings as settings_mod, updater
from app.core.settings import Settings


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
def test_sanitize_filename_strips_illegal_characters():
    assert paths.sanitize_filename('a/b\\c:d*e?f"g<h>i|j') == "a／b＼c：d＊e？f＂g＜h＞i｜j"


def test_sanitize_filename_handles_empty_and_reserved():
    assert paths.sanitize_filename("") == "untitled"
    assert paths.sanitize_filename("   ") == "untitled"
    assert paths.sanitize_filename("CON").startswith("_")


def test_sanitize_filename_truncates():
    name = paths.sanitize_filename("视" * 300, max_length=50)
    assert len(name) <= 50


def test_safe_template_neutralises_traversal():
    assert "../" not in paths.safe_template("../%(title)s.%(ext)s")
    assert paths.safe_template("") == "%(title)s.%(ext)s"


def test_human_helpers():
    assert paths.human_size(0) == "—"
    assert paths.human_size(1536) == "1.5 KB"
    assert paths.human_duration(754) == "12:34"
    assert paths.human_duration(3723) == "1:02:03"
    assert paths.human_speed(None) == "—"


# ---------------------------------------------------------------------------
# formats
# ---------------------------------------------------------------------------
INFO = {
    "id": "abc",
    "title": "demo",
    "formats": [
        {"format_id": "137", "ext": "mp4", "height": 1080, "width": 1920, "fps": 30,
         "vcodec": "avc1", "acodec": "none", "filesize": 1000},
        {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "filesize": 100},
        {"format_id": "18", "ext": "mp4", "height": 360, "width": 640, "vcodec": "avc1",
         "acodec": "mp4a", "filesize": 300},
        {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none"},
    ],
}


def test_preset_selector():
    assert formats.build_format_selector("best") == "bestvideo*+bestaudio/best"
    assert "height<=1080" in formats.build_format_selector("1080")
    assert formats.build_format_selector("audio-mp3") == "bestaudio/best"
    assert formats.build_format_selector("custom", "137+140") == "137+140"


def test_audio_postprocessor():
    pp = formats.audio_postprocessor("audio-mp3")
    assert pp and pp["preferredcodec"] == "mp3"
    assert formats.audio_postprocessor("best") is None


def test_classify_formats_filters_storyboards_and_sorts():
    rows = formats.classify_formats(INFO)
    ids = [r.format_id for r in rows]
    assert "sb0" not in ids
    assert ids[0] in {"137", "18"}  # video rows first
    heights = [r.height for r in rows if r.height]
    assert heights == sorted(heights, reverse=True)


def test_preset_availability_disables_4k():
    availability = dict(
        (preset.key, ok) for preset, ok, _ in formats.preset_availability(INFO, "zh")
    )
    assert availability["2160"] is False
    assert availability["1080"] is True
    assert availability["best"] is True


def test_summarize():
    summary = formats.summarize(INFO)
    assert summary["title"] == "demo"
    assert summary["id"] == "abc"


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("message,code", [
    ("ERROR: [youtube] x: Sign in to confirm you're not a bot", "bot_check"),
    ("ERROR: Sign in to confirm you are not a bot", "bot_check"),
    ("This video is only available for registered users", "login_required"),
    ("unable to download video data: HTTP Error 403: Forbidden", "forbidden_403"),
    ("Video unavailable", "unavailable"),
    ("ERROR: Unsupported URL: https://x", "unsupported_url"),
    ("ffmpeg not found. Please install", "ffmpeg_missing"),
    ("Postprocessing: ffprobe and ffmpeg not found", "ffmpeg_missing"),
    ("certificate verify failed: unable to get local issuer certificate", "ssl_error"),
    ("nodename nor servname provided, or not known", "dns_error"),
    ("Requested format is not available", "format_unavailable"),
    ("Private video. Sign in if you've been granted access", "private_video"),
    ("This video is not available in your country", "geo_blocked"),
    ("This video is for premium members only", "membership"),
    ("Unable to extract player response", "extractor_broken"),
    ("HTTP Error 429: Too Many Requests", "rate_limited"),
    ("[Errno 28] No space left on device", "disk_full"),
    ("Permission denied: /x", "permission_denied"),
    ("DRM protected content", "drm"),
    ("ProxyError: Cannot connect to proxy", "proxy_error"),
    ("Read timed out.", "timeout"),
    ("Download cancelled by user", "cancelled"),
    ("something nobody has ever seen", "generic"),
])
def test_error_translation(message, code):
    problem = errors.translate(message)
    assert problem.code == code
    assert problem.title
    assert problem.detail


def test_error_translation_returns_fix_actions():
    problem = errors.translate("Sign in to confirm you're not a bot")
    actions = [fix.action for fix in problem.fixes]
    assert errors.ACTION_COOKIES in actions
    assert errors.ACTION_RETRY in actions


def test_catalog_has_problems():
    items = errors.catalog("zh")
    assert len(items) >= 20
    assert all(p.title and p.detail for p in items)


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------
@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod.paths, "app_data_dir", lambda: tmp_path / "appdata")
    return tmp_path


def test_settings_roundtrip(isolated_settings):
    s = Settings(download_dir=str(isolated_settings / "dl"), proxy="127.0.0.1:7890",
                 max_concurrent=99, retries=-3)
    s.validate()
    assert s.proxy == "http://127.0.0.1:7890"
    assert s.max_concurrent == 6
    assert s.retries == 0
    s.save()

    loaded = Settings.load()
    assert loaded.download_dir == s.download_dir
    assert loaded.proxy == s.proxy
    assert loaded.max_concurrent == 6


def test_settings_defaults_are_sane():
    s = Settings()
    s.validate()
    assert 1 <= s.max_concurrent <= 6
    assert s.filename_template.endswith(".%(ext)s")


def test_effective_language():
    s = Settings(language="zh")
    assert s.effective_language() == "zh"
    s.language = "en"
    assert s.effective_language() == "en"


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
def test_history_add_dedupe_and_limit(tmp_path):
    store = history.HistoryStore(tmp_path / "h.json", limit=3)
    for i in range(5):
        store.add(history.HistoryEntry(url=f"https://e/{i}", title=f"t{i}"))
    assert len(store) == 3
    assert store.entries[0].title == "t4"

    store.add(history.HistoryEntry(url="https://e/4", title="t4 again"))
    assert len(store) == 3
    assert store.entries[0].title == "t4 again"

    store.clear()
    assert len(store) == 0
    assert json.loads((tmp_path / "h.json").read_text()) == []


# ---------------------------------------------------------------------------
# cookies
# ---------------------------------------------------------------------------
def test_validate_cookiefile(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("not a cookie file", encoding="utf-8")
    ok, message = cookies.validate_cookiefile(bad)
    assert not ok and message

    good = tmp_path / "cookies.txt"
    good.write_text("# Netscape HTTP Cookie File\n"
                    ".bilibili.com\tTRUE\t/\tFALSE\t0\tSESSDATA\tabc\n", encoding="utf-8")
    ok, _ = cookies.validate_cookiefile(good)
    assert ok


def test_json_cookie_conversion(tmp_path):
    src = tmp_path / "cookies.json"
    src.write_text(json.dumps([
        {"domain": ".youtube.com", "path": "/", "secure": True,
         "expirationDate": 2000000000, "name": "SID", "value": "v"},
    ]), encoding="utf-8")
    out = cookies.convert_json_cookies(src)
    text = Path(out).read_text(encoding="utf-8")
    assert "Netscape HTTP Cookie File" in text
    assert ".youtube.com" in text and "SID" in text
    assert cookies.prepare_cookiefile(src).endswith(".cookies.txt")


def test_cookiesfrombrowser():
    assert cookies.cookiesfrombrowser("chrome")[0] == "chrome"
    assert cookies.cookiesfrombrowser("") is None
    assert cookies.cookiesfrombrowser("unknown") is None


# ---------------------------------------------------------------------------
# updater
# ---------------------------------------------------------------------------
def test_version_compare():
    assert updater._is_newer("2026.10.22", "2026.10.21")
    assert updater._is_newer("2026.11.1", "2026.10.31")
    assert not updater._is_newer("2026.10.21", "2026.10.21")
    assert updater.current_version()
