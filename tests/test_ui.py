"""GUI smoke tests (offscreen): pages, media card, queue cards, theme switch."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.settings import Settings
from app.core.tasks import DownloadTask

INFO = {
    "id": "BV1xx",
    "title": "测试视频标题",
    "uploader": "测试作者",
    "duration": 125,
    "thumbnail": "",
    "extractor_key": "BiliBili",
    "webpage_url": "https://www.bilibili.com/video/BV1xx",
    "view_count": 12345,
    "description": "描述",
    "formats": [
        {"format_id": "137", "ext": "mp4", "height": 1080, "width": 1920, "fps": 30,
         "vcodec": "avc1", "acodec": "none", "filesize": 1000},
        {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a"},
    ],
}


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def window(app, tmp_path, monkeypatch):
    from app.core import paths
    from app.ui import theme
    from app.ui.main_window import MainWindow

    # Never touch the real user config/history while testing.
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path / "appdata")
    monkeypatch.setattr(MainWindow, "_run_diagnostics", lambda self, silent=False: None)
    monkeypatch.setattr(MainWindow, "_check_updates_quietly", lambda self: None)
    settings = Settings(download_dir=str(tmp_path / "out"))
    theme.apply_theme(app, "dark")
    win = MainWindow(settings)
    yield win
    win.close()


def test_pages_exist(window):
    assert window.stack.count() == 5
    for index in range(5):
        window._go(index)
        assert window.stack.currentIndex() == index


def test_media_card_renders(window):
    page = window.home_page
    page.show_media(INFO)
    assert page.media_card.isVisibleTo(page)
    assert "测试视频标题" in page.title_label.text()
    assert page.preset_combo.count() >= 8
    assert page.thumb.width() > 100


def test_probe_error_card(window):
    from app.core import errors

    problem = errors.translate("Sign in to confirm you're not a bot")
    window.home_page.show_error(problem)
    assert window.home_page.error_card.isVisibleTo(window.home_page)
    assert problem.title in window.home_page.err_title.text()


def test_enqueue_and_progress(window):
    page = window.queue_page
    task = DownloadTask(url="http://127.0.0.1/x.mp4", title="任务一", site="测试", preset="720")
    window._tasks[task.id] = task
    page.add_task(task)
    window._refresh_queue_state()
    assert task.id in page._cards

    task.mark_running()
    task.progress = 42.5
    task.speed = 1024 * 1024
    task.total = 10 * 1024 * 1024
    page.update_task(task)
    card = page._cards[task.id]
    assert card.progress.value() == 42
    assert "42.5%" in card.stat_label.text()

    task.mark_failed(__import__("app.core.errors", fromlist=["translate"]).translate(
        "HTTP Error 403: Forbidden"))
    page.update_task(task)
    assert card.pill.text() == "失败"
    assert "403" not in card.title_label.text()


def test_network_mode_setting(window):
    page = window.settings_page
    index = page.proxy_mode_combo.findData("direct")
    page.proxy_mode_combo.setCurrentIndex(index)
    assert window.settings.proxy_mode == "direct"
    assert page.proxy_edit.isEnabled() is False
    page.proxy_mode_combo.setCurrentIndex(page.proxy_mode_combo.findData("custom"))
    assert page.proxy_edit.isEnabled() is True


def test_history_page_rows(window):
    from app.core.history import HistoryEntry

    entries = [HistoryEntry(url="https://e/1", title="已下载视频", site="B站",
                            filepath="/tmp/none.mp4", filesize=1024)]
    window.history_page.set_entries(entries)
    assert window.history_page.list_layout.count() >= 2


def test_theme_switch(window, app):
    from app.ui import theme

    theme.apply_theme(app, "light")
    stylesheet = app.styleSheet()
    assert "F0ECE3" in stylesheet
    # The brief pins a square, flat, low-render world.
    assert "border-radius" not in stylesheet
    assert "qlineargradient" not in stylesheet
    theme.apply_theme(app, "dark")
    assert "0B0A09" in app.styleSheet()
