"""Engine tests: option building (no network) + a real localhost download."""

from __future__ import annotations

import http.server
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

from app.core import engine
from app.core.settings import Settings


@pytest.fixture()
def settings(tmp_path):
    s = Settings(download_dir=str(tmp_path / "out"))
    s.embed_metadata = True
    s.embed_thumbnail = True
    s.max_concurrent = 2
    s.validate()
    return s


def test_build_options_basic(settings):
    opts = engine.build_download_options(settings, "1080")
    assert "height<=1080" in opts["format"]
    assert opts["merge_output_format"] == "mp4"
    assert opts["outtmpl"]["default"].endswith("%(title)s [%(id)s].%(ext)s")
    assert opts["ffmpeg_location"]  # bundled ffmpeg is discovered
    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert "FFmpegMetadata" in keys
    assert "EmbedThumbnail" in keys
    assert opts["writethumbnail"] is True


def test_build_options_audio(settings):
    opts = engine.build_download_options(settings, "audio-mp3")
    pps = [pp["key"] for pp in opts["postprocessors"]]
    assert pps[0] == "FFmpegExtractAudio"
    assert "EmbedThumbnail" not in pps
    assert opts["writethumbnail"] is False


def test_build_options_direct_mode(settings, monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    settings.proxy_mode = "direct"
    settings.proxy = "http://127.0.0.1:7890"
    opts = engine.build_download_options(settings, "best")
    assert opts["proxy"] == ""  # explicit direct wins over the OS proxy


def test_build_options_custom_mode(settings):
    settings.proxy_mode = "custom"
    settings.proxy = "http://127.0.0.1:7890"
    opts = engine.build_download_options(settings, "best")
    assert opts["proxy"] == "http://127.0.0.1:7890"


def test_build_options_network(settings):
    settings.proxy_mode = "custom"
    settings.proxy = "http://127.0.0.1:7890"
    settings.rate_limit_kbps = 512
    settings.cookies_browser = "chrome"
    settings.retries = 7
    opts = engine.build_download_options(settings, "best")
    assert opts["proxy"] == "http://127.0.0.1:7890"
    assert opts["ratelimit"] == 512 * 1024
    assert opts["cookiesfrombrowser"][0] == "chrome"
    assert opts["retries"] == 7


def test_build_options_subtitles(settings):
    settings.write_subs = True
    settings.sub_langs = "zh-Hans, en"
    opts = engine.build_download_options(settings, "720")
    assert opts["writesubtitles"] is True
    assert opts["subtitleslangs"] == ["zh-Hans", "en"]


def test_normalize_progress():
    data = {
        "status": "downloading",
        "downloaded_bytes": 50,
        "total_bytes": 200,
        "speed": 1024,
        "eta": 5,
        "info_dict": {"title": "hello"},
    }
    out = engine.normalize_progress(data)
    assert out["percent"] == 25.0
    assert out["title"] == "hello"
    assert out["eta"] == 5

    out = engine.normalize_progress({"status": "finished", "downloaded_bytes": 10})
    assert out["percent"] == 100.0


# ---------------------------------------------------------------------------
# real download from a localhost HTTP server (no external network needed)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def media_server(tmp_path_factory):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    folder = tmp_path_factory.mktemp("media")
    sample = folder / "sample.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15",
         "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(sample)],
        check=True, capture_output=True,
    )

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=str(folder), **kwargs)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}/sample.mp4"
    server.shutdown()


def test_real_download(settings, media_server):
    events: list[dict] = []
    result = engine.download(media_server, settings, preset_key="best",
                             progress=events.append)
    assert result.filepaths, "expected at least one produced file"
    path = Path(result.filepaths[0])
    assert path.exists() and path.stat().st_size > 0
    assert path.suffix.lower() in {".mp4", ".mkv", ".webm"}
    assert events, "progress callback should have been called"


def test_real_audio_download(settings, media_server):
    settings.embed_metadata = False
    result = engine.download(media_server, settings, preset_key="audio-mp3")
    assert result.filepaths
    assert Path(result.filepaths[0]).suffix.lower() == ".mp3"


def test_cancellation_keeps_partial_file(settings, media_server):
    import threading as th

    cancel = th.Event()
    cancel.set()
    with pytest.raises(engine.DownloadCancelled):
        engine.download(media_server, settings, preset_key="best", cancel_event=cancel)


def test_probe_local(settings, media_server):
    info = engine.probe(media_server, settings)
    assert info.get("id")
    assert info.get("extractor_key")
