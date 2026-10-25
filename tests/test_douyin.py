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


def test_extract_url_from_share_text():
    text = ("5.38 复制打开抖音，看看【张小莲的图文作品】感觉至上# 神级live现场 # 张艺兴  "
            "https://v.douyin.com/4FMez9M7KPI/ :6pm 11/29 UyG:/ y@g.oD")
    assert douyin.extract_url(text) == "https://v.douyin.com/4FMez9M7KPI/"
    assert douyin.extract_url("https://www.douyin.com/video/1，") == "https://www.douyin.com/video/1"
    assert douyin.extract_url("没有链接") == ""


def test_parse_note_gallery():
    info = douyin.parse_note(
        {"title": "感觉至上#神级live现场 - 抖音",
         "images": ["https://example.com/a.webp", "https://example.com/b.webp"]},
        "https://www.douyin.com/note/7686466217775889275",
    )
    assert info.is_images
    assert info.video_id == "7686466217775889275"
    assert info.title == "感觉至上#神级live现场"
    assert len(info.images) == 2
    payload = douyin.to_info_dict(info)
    assert payload["_type"] == "images"
    assert payload["image_count"] == 2
    assert payload["formats"][0]["ext"] == "zip"
    assert douyin.render_filename("%(title)s.%(ext)s", info, ext="zip").endswith(".zip")


def test_parse_detail_rejects_image_only_post():
    payload = {"aweme_detail": {"aweme_id": "1", "desc": "图文",
                                "images": [{"url_list": ["https://example.com/a.webp"]}]}}
    try:
        douyin.parse_detail(payload)
    except douyin.DouyinError as exc:
        assert "图文作品" in str(exc)
    else:
        raise AssertionError("image-only detail should not produce a video")


def test_resolve_share_text_extracts_url(monkeypatch):
    douyin._CACHE.clear()
    monkeypatch.setattr(douyin, "find_browser", lambda: ("/bin/true", "edge"))
    monkeypatch.setattr(douyin, "_expand_url",
                        lambda url: "https://www.douyin.com/video/7675374449897524534")
    monkeypatch.setattr(douyin, "_cdp_resolve", lambda url, timeout=25: DETAIL)
    text = "复制打开抖音 https://v.douyin.com/4FMez9M7KPI/ 看看"
    info = douyin.resolve(text)
    assert info.video_id == "7675374449897524534"
    assert info.title.startswith("测试抖音视频")
