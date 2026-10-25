"""Unit tests for the native Douyin resolver (no browser / no network)."""

from __future__ import annotations

from app.core import douyin, errors

DETAIL = {
    "aweme_detail": {
        "aweme_id": "7675374449897524534",
        "desc": "测试抖音视频 #tag",
        "author": {"nickname": "测试作者"},
        "video": {
            "duration": 392650,
            "width": 1920,
            "height": 1080,
            "cover": {"url_list": ["https://example.com/cover.jpg"]},
            "play_addr": {"url_list": ["https://example.com/fallback.mp4"]},
            "bit_rate": [
                {"gear_name": "normal_1080_0", "bit_rate": 1452007, "format": "mp4",
                 "play_addr": {"url_list": ["https://example.com/1080.mp4"]}},
                {"gear_name": "normal_720_0", "bit_rate": 900000, "format": "mp4",
                 "play_addr": {"url_list": ["https://example.com/720.mp4"]}},
                {"gear_name": "adapt_lowest_4_1", "bit_rate": 400000, "format": "mp4",
                 "play_addr": {"url_list": ["https://example.com/low.mp4"]}},
                # dash entries are video-only and must be ignored
                {"gear_name": "normal_1080_0", "bit_rate": 1400000, "format": "dash",
                 "play_addr": {"url_list": ["https://example.com/1080-dash.mp4"]}},
            ],
        },
    },
}


def test_is_douyin_url():
    assert douyin.is_douyin_url("https://www.douyin.com/video/1")
    assert douyin.is_douyin_url("https://v.douyin.com/abc/")
    assert douyin.is_douyin_url("https://www.douyin.com/video/1?modeFrom=")
    assert not douyin.is_douyin_url("https://www.bilibili.com/video/BV1")
    assert not douyin.is_douyin_url("https://notdouyin.com/video/1")


def test_parse_detail_builds_variants():
    info = douyin.parse_detail(DETAIL, "https://www.douyin.com/video/7675374449897524534")
    assert info.video_id == "7675374449897524534"
    assert info.title.startswith("测试抖音视频")
    assert info.uploader == "测试作者"
    assert info.duration == 392.65
    assert info.thumbnail == "https://example.com/cover.jpg"
    # dash-only duplicates are skipped; one 1080p, one 720p, one unknown-height
    assert len(info.variants) == 3
    assert info.best.bitrate == 1452007
    assert info.best.height == 1080
    assert info.best.width == 1920
    assert any(v.height == 720 and v.width == 1280 for v in info.variants)
    assert info.best.urls[0] == "https://example.com/1080.mp4"


def test_to_info_dict_is_gui_compatible():
    info = douyin.parse_detail(DETAIL, "https://www.douyin.com/video/1")
    payload = douyin.to_info_dict(info)
    assert payload["extractor_key"] == "Douyin"
    assert payload["formats"]
    heights = [f["height"] for f in payload["formats"]]
    assert 1080 in heights
    assert payload["webpage_url"] == "https://www.douyin.com/video/1"


def test_render_filename_uses_template_and_sanitises():
    info = douyin.parse_detail(DETAIL)
    name = douyin.render_filename("%(title)s [%(id)s].%(ext)s", info)
    assert "7675374449897524534" in name
    assert name.endswith(".mp4")
    assert "/" not in name


def test_pick_variant_by_preset():
    info = douyin.parse_detail(DETAIL)
    assert douyin._pick_variant(info, "720").height == 720
    assert douyin._pick_variant(info, "best").height == 1080


def test_douyin_error_translation():
    problem = errors.translate("ERROR: [Douyin] 123: Fresh cookies (not necessarily logged in) are needed")
    assert problem.code == "douyin_cookie"
    assert problem.fixes
