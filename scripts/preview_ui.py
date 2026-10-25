"""Generate UI preview screenshots without network access.

Usage:  python scripts/preview_ui.py [output_dir]
This is a development helper; it fabricates one parsed video and a few queue
tasks so the visual design can be reviewed offline.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

import app.ui.main_window as mw_module
from app.core import paths as core_paths
from app.core.errors import translate
from app.core.settings import Settings
from app.core.tasks import QUEUED, DownloadTask
from app.ui import theme

# no timers -> no background diagnostics/update threads in this preview
mw_module.QTimer.singleShot = lambda *args, **kwargs: None
# never touch the real user config/history while generating screenshots
PREVIEW_HOME = Path(tempfile.mkdtemp(prefix="glowdl-preview-"))
core_paths.app_data_dir = lambda: PREVIEW_HOME

FAKE_INFO = {
    "id": "BV1GJ411x7h7",
    "title": "4K 修复｜把喜欢的视频一键收藏到本地：完整流程演示（字幕与封面）",
    "uploader": "拾光研究所",
    "duration": 754,
    "thumbnail": "",
    "extractor_key": "BiliBili",
    "webpage_url": "https://www.bilibili.com/video/BV1GJ411x7h7",
    "view_count": 1284000,
    "description": "从粘贴链接到下载完成：选择画质、合并音轨、嵌入封面与字幕、断点续传，"
                   "以及出错后的诊断流程。",
    "formats": [
        {"format_id": "30280", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2",
         "tbr": 192, "filesize": 18_100_000},
        {"format_id": "30216", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2",
         "tbr": 64, "filesize": 6_000_000},
        {"format_id": "30080", "ext": "mp4", "height": 2160, "width": 3840, "fps": 60,
         "vcodec": "hev1.1.6.L150", "acodec": "none", "tbr": 18_000,
         "filesize": 1_700_000_000},
        {"format_id": "30077", "ext": "mp4", "height": 1080, "width": 1920, "fps": 60,
         "vcodec": "avc1.640032", "acodec": "none", "tbr": 6_200,
         "filesize": 580_000_000},
        {"format_id": "80", "ext": "mp4", "height": 1080, "width": 1920, "fps": 30,
         "vcodec": "avc1.640028", "acodec": "none", "tbr": 3_100,
         "filesize": 290_000_000},
        {"format_id": "64", "ext": "mp4", "height": 720, "width": 1280, "fps": 30,
         "vcodec": "avc1.4d401f", "acodec": "none", "tbr": 1_500,
         "filesize": 140_000_000},
    ],
}


def make_thumbnail(width: int = 640, height: int = 360) -> QPixmap:
    pixmap = QPixmap(width, height)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor("#2A2F6B"))
    gradient.setColorAt(0.45, QColor("#5B4B8A"))
    gradient.setColorAt(1.0, QColor("#1B7A8C"))
    painter = QPainter(pixmap)
    painter.fillRect(pixmap.rect(), gradient)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QColor(255, 255, 255, 40))
    for i in range(6):
        painter.drawEllipse(QPointF(width * (0.15 + i * 0.14), height * 0.72), 60 + i * 18,
                            60 + i * 18)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("PingFang SC")
    font.setPixelSize(44)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(40, height - 120, width - 80, 60), Qt.AlignLeft, "4K 修复 · 完整流程")
    font.setPixelSize(22)
    font.setBold(False)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 190))
    painter.drawText(QRectF(40, height - 62, width - 80, 40), Qt.AlignLeft,
                     "GlowDL · 1080P / HEVC · 字幕 · 封面")
    painter.end()
    return pixmap


def build_tasks(settings: Settings) -> list[DownloadTask]:
    now = time.time()
    tasks = [
        DownloadTask(url="https://www.bilibili.com/video/BV1GJ411x7h7",
                     title="4K 修复｜把喜欢的视频一键收藏到本地：完整流程演示",
                     site="哔哩哔哩", preset="1080", duration=754),
        DownloadTask(url="https://youtu.be/dQw4w9WgXcQ", title="Rick Astley - Never Gonna Give You Up",
                     site="YouTube", preset="audio-mp3", duration=213),
        DownloadTask(url="https://www.douyin.com/video/7300000000000000000",
                     title="城市夜景延时摄影 · 4K 60fps", site="抖音", preset="2160"),
        DownloadTask(url="https://www.xiaohongshu.com/explore/66aa", title="周末露营 vlog｜两天一夜",
                     site="小红书", preset="720"),
    ]
    running, done, failed, queued = tasks
    running.mark_running()
    running.progress = 43.6
    running.downloaded = 128_000_000
    running.total = 293_000_000
    running.speed = 6_200_000
    running.eta = 26
    running.started_at = now - 18

    done.mark_running()
    done.filepaths = ["/Users/a1/Downloads/GlowDL/Rick Astley - Never Gonna Give You Up.mp3"]
    done.progress = 100
    done.mark_done()

    failed.mark_running()
    failed.progress = 12.4
    failed.mark_failed(translate("ERROR: [douyin] 7300: HTTP Error 403: Forbidden"))
    queued.status = QUEUED
    return tasks


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    settings = Settings.load()
    settings.theme = "light"
    settings.language = "zh"
    settings.cookies_browser = "edge"
    settings.max_concurrent = 50
    theme.apply_theme(app, "light")

    window = mw_module.MainWindow(settings)
    window.resize(1240, 820)
    window.show()
    app.processEvents()

    thumb = make_thumbnail()
    window.home_page.thumb.set_thumbnail(thumb)
    window.home_page.url_input.setText(FAKE_INFO["webpage_url"])
    window.home_page.show_media(FAKE_INFO)
    window.home_page.thumb.set_thumbnail(thumb)
    app.processEvents()
    window.grab().save(str(out_dir / "01-home.png"))

    for task in build_tasks(settings):
        window._tasks[task.id] = task
        window.queue_page.add_task(task)
    window._refresh_queue_state()
    window._go(1)
    app.processEvents()
    window.grab().save(str(out_dir / "02-queue.png"))

    from app.core.history import HistoryEntry

    entries = [
        HistoryEntry(url="https://www.bilibili.com/video/BV1GJ411x7h7",
                     title="4K 修复｜把喜欢的视频一键收藏到本地：完整流程演示",
                     site="哔哩哔哩", preset="1080",
                     filepath="/Users/a1/Downloads/GlowDL/4K 修复.mp4",
                     filesize=293_000_000, duration=754, finished_at=time.time() - 300),
        HistoryEntry(url="https://youtu.be/dQw4w9WgXcQ",
                     title="Rick Astley - Never Gonna Give You Up", site="YouTube",
                     preset="audio-mp3",
                     filepath="/Users/a1/Downloads/GlowDL/Rick Astley.mp3",
                     filesize=4_900_000, duration=213, finished_at=time.time() - 3600),
        HistoryEntry(url="https://www.xiaohongshu.com/explore/66aa",
                     title="周末露营 vlog｜两天一夜", site="小红书", preset="720",
                     filepath="/Users/a1/Downloads/GlowDL/露营.mp4",
                     filesize=88_000_000, duration=420, finished_at=time.time() - 86400),
    ]
    window.history_page.set_entries(entries)
    window.home_page.set_recent(entries)
    window._go(0)
    app.processEvents()
    window.grab().save(str(out_dir / "01-home.png"))

    window._go(2)
    app.processEvents()
    window.grab().save(str(out_dir / "03-history.png"))

    from app.core import diagnostics

    checks = [
        diagnostics.CheckResult("python", "运行环境 Python", diagnostics.PASS, "Python 3.11.9（Windows）"),
        diagnostics.CheckResult("platform", "运行平台", diagnostics.PASS, "Windows 11 · GlowDL 1.0.0"),
        diagnostics.CheckResult("yt_dlp", "解析组件", diagnostics.PASS,
                                "已内置，无需安装"),
        diagnostics.CheckResult("ffmpeg", "音视频合并", diagnostics.PASS, "已就绪"),
        diagnostics.CheckResult("postprocess", "封面 / 元数据嵌入", diagnostics.PASS, "已就绪"),
        diagnostics.CheckResult("douyin", "抖音原生解析", diagnostics.PASS, "使用本机 Edge 解析"),
        diagnostics.CheckResult("output_dir", "下载目录可写", diagnostics.PASS,
                                "D:/Downloads/GlowDL"),
        diagnostics.CheckResult("disk", "磁盘剩余空间", diagnostics.PASS, "剩余 214.6 GB"),
        diagnostics.CheckResult("proxy", "代理设置", diagnostics.WARN,
                                "未启用代理（访问 YouTube 时可能需要）"),
        diagnostics.CheckResult("network", "站点连通性", diagnostics.PASS, "B站: 可访问；YouTube: 可访问"),
        diagnostics.CheckResult("ssl", "HTTPS 证书链", diagnostics.PASS, "证书校验正常（TLSv1.3）"),
        diagnostics.CheckResult("cookies", "登录 Cookie", diagnostics.PASS,
                                "从 Microsoft Edge 读取"),
    ]
    window.clinic_page.set_running(False)
    window.clinic_page.set_checks(checks)
    window._checks = checks
    window.stack.setCurrentIndex(3)
    window.nav_buttons[3].setChecked(True)
    window._refresh_nav_icons()
    app.processEvents()
    window.grab().save(str(out_dir / "04-clinic.png"))

    window._go(4)
    app.processEvents()
    window.grab().save(str(out_dir / "05-settings.png"))

    # Dark theme is a separate rebuild: icons are built against the active palette,
    # so switching theme in a live window is intentionally deferred to restart.
    window.close()
    settings.theme = "dark"
    theme.apply_theme(app, "dark")
    window_light = mw_module.MainWindow(settings)
    window_light.resize(1240, 820)
    window_light.show()
    window_light.home_page.url_input.setText(FAKE_INFO["webpage_url"])
    window_light.home_page.show_media(FAKE_INFO)
    window_light.home_page.thumb.set_thumbnail(thumb)
    window_light.home_page.set_recent(entries)
    app.processEvents()
    window_light.grab().save(str(out_dir / "06-home-dark.png"))
    window_light.close()

    print("saved screenshots to", out_dir.resolve())
    window.close()


if __name__ == "__main__":
    main()
