"""Home page: paste a link, inspect media, choose quality, enqueue a download."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from app.core import formats as fmt
from app.core import paths
from app.core.errors import Problem
from app.core.settings import Settings
from app.core.tasks import DownloadTask
from app.ui import icons, theme, widgets

SITE_LABELS = {
    "youtube": "YouTube",
    "youtube:tab": "YouTube",
    "bilibili": "哔哩哔哩",
    "bilibili:bangumi": "哔哩哔哩",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "twitter": "X / Twitter",
    "weibo": "微博",
    "tiktok": "TikTok",
    "vimeo": "Vimeo",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitch": "Twitch",
    "neteasemusic": "网易云音乐",
    "qqmusic": "QQ 音乐",
    "acfun": "AcFun",
    "iqiyi": "爱奇艺",
    "youku": "优酷",
}


def site_label(extractor: str) -> str:
    key = (extractor or "").lower()
    if key in SITE_LABELS:
        return SITE_LABELS[key]
    for prefix, label in SITE_LABELS.items():
        if key.startswith(prefix.split(":")[0]):
            return label
    return extractor.replace(":", " · ") or "未知站点"


class HomePage(QWidget):
    parse_requested = Signal(str, bool)
    download_requested = Signal(object)  # DownloadTask
    fix_requested = Signal(str, object, str)  # action, problem, url
    settings_changed = Signal()
    history_requested = Signal()
    open_path_requested = Signal(str)
    settings_page_requested = Signal()

    def __init__(self, settings: Settings, image_loader, parent: QWidget | None = None):
        super().__init__(parent)
        self.settings = settings
        self._loader = image_loader
        self._info: dict[str, Any] | None = None
        self._thumb_url = ""
        self._error_problem: Problem | None = None
        self._build_ui()
        self._loader.pixmap_ready.connect(self._on_pixmap)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(16)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        heading = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("下载")
        title.setObjectName("PageTitle")
        subtitle = QLabel("粘贴链接，选择画质，下载到本地。")
        subtitle.setObjectName("PageSub")
        box.addWidget(title)
        box.addWidget(subtitle)
        heading.addLayout(box)
        heading.addStretch(1)
        root.addLayout(heading)

        # --- URL card ---------------------------------------------------
        hero = widgets.Card(object_name="HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 16)
        hero_layout.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText("粘贴视频链接，例如 https://www.bilibili.com/video/BV… 或 https://youtu.be/…")
        self.url_input.returnPressed.connect(self._on_parse_clicked)
        self.url_input.textChanged.connect(self._on_url_changed)
        row.addWidget(self.url_input, 1)

        paste_btn = widgets.IconButton("copy", "从剪贴板粘贴", 18, theme.active["muted"])
        paste_btn.setFixedSize(42, 42)
        paste_btn.clicked.connect(self._paste)
        row.addWidget(paste_btn)

        self.parse_btn = widgets.make_button("解析", "primary", "search", on_click=self._on_parse_clicked,
                                             height=42)
        self.parse_btn.setMinimumWidth(104)
        row.addWidget(self.parse_btn)
        hero_layout.addLayout(row)

        hint_row = QHBoxLayout()
        hint_row.setSpacing(8)
        hint = QLabel("支持 B 站、YouTube、抖音、小红书等站点")
        hint.setObjectName("Dim")
        hint_row.addWidget(hint)
        hint_row.addStretch(1)
        self.playlist_check = QCheckBox("按播放列表下载")
        self.playlist_check.setChecked(self.settings.playlist)
        self.playlist_check.setToolTip("开启后，播放列表链接会整体加入队列")
        hint_row.addWidget(self.playlist_check)
        hero_layout.addLayout(hint_row)
        root.addWidget(hero)

        # --- loading / error -------------------------------------------
        self.loading_row = QWidget()
        loading_layout = QHBoxLayout(self.loading_row)
        loading_layout.setContentsMargins(4, 0, 4, 0)
        loading_layout.setSpacing(8)
        self.loading_label = QLabel("正在解析链接…")
        self.loading_label.setObjectName("Muted")
        loading_layout.addWidget(self.loading_label)
        loading_layout.addStretch(1)
        self.loading_row.hide()
        root.addWidget(self.loading_row)

        self.error_card = self._build_error_card()
        self.error_card.hide()
        root.addWidget(self.error_card)

        # --- media card -------------------------------------------------
        self.media_card = self._build_media_card()
        self.media_card.hide()
        root.addWidget(self.media_card)

        # --- recent ledger ----------------------------------------------
        self.recent_card = self._build_recent_card()
        self.recent_card.hide()
        root.addWidget(self.recent_card)

        # --- empty state ------------------------------------------------
        self.empty = widgets.EmptyState(
            "download",
            "还没有待下载的内容",
            "把视频链接粘贴到上面的输入框，或直接把链接拖进窗口。",
            action=("从剪贴板粘贴", self._paste),
        )
        root.addWidget(self.empty, 1)

        root.addStretch(1)

    def _build_recent_card(self) -> QFrame:
        card = widgets.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        head = QWidget()
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(20, 14, 12, 12)
        head_layout.setSpacing(8)
        title = QLabel("最近完成")
        title.setObjectName("SectionHeader")
        head_layout.addWidget(title)
        head_layout.addStretch(1)
        all_btn = QPushButton("全部历史")
        all_btn.setProperty("role", "quiet")
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(self.history_requested.emit)
        head_layout.addWidget(all_btn)
        layout.addWidget(head)
        layout.addWidget(widgets.hline())
        self.recent_rows = QVBoxLayout()
        self.recent_rows.setContentsMargins(0, 0, 0, 0)
        self.recent_rows.setSpacing(0)
        layout.addLayout(self.recent_rows)
        return card

    def set_recent(self, entries) -> None:
        while self.recent_rows.count():
            item = self.recent_rows.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        entries = list(entries or [])[:3]
        self.recent_card.setVisible(bool(entries))
        for index, entry in enumerate(entries):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(20, 10, 16, 10)
            row_layout.setSpacing(10)
            title = widgets.ElidedLabel(entry.title or entry.url)
            title.setObjectName("CardTitle")
            row_layout.addWidget(title, 1)
            meta = QLabel(entry.site or "视频")
            meta.setObjectName("Dim")
            row_layout.addWidget(meta)
            size = QLabel(paths.human_size(entry.filesize) if entry.filesize else "")
            size.setObjectName("MonoDim")
            row_layout.addWidget(size)
            when = QLabel(entry.when)
            when.setObjectName("MonoDim")
            row_layout.addWidget(when)
            reveal = widgets.IconButton("folder", "在文件夹中显示", 15, theme.active["muted"])
            reveal.clicked.connect(
                lambda _=False, path=entry.filepath: self.open_path_requested.emit(path))
            row_layout.addWidget(reveal)
            self.recent_rows.addWidget(row)
            if index < len(entries) - 1:
                self.recent_rows.addWidget(widgets.hline())

    def _build_error_card(self) -> QFrame:
        card = widgets.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(icons.pixmap("error", theme.active["danger"], 22))
        top.addWidget(icon_label, alignment=Qt.AlignTop)
        self.err_title = QLabel("解析失败")
        self.err_title.setObjectName("CardTitle")
        top.addWidget(self.err_title, 1)
        close = widgets.IconButton("close", "关闭", 14, theme.active["dim"])
        close.clicked.connect(lambda: self.error_card.hide())
        top.addWidget(close)
        layout.addLayout(top)

        self.err_detail = QLabel("")
        self.err_detail.setWordWrap(True)
        self.err_detail.setObjectName("Muted")
        self.err_detail.setContentsMargins(32, 0, 0, 0)
        layout.addWidget(self.err_detail)

        self.err_fixes = QHBoxLayout()
        self.err_fixes.setContentsMargins(32, 2, 0, 0)
        self.err_fixes.setSpacing(8)
        layout.addLayout(self.err_fixes)

        self.raw_toggle = QPushButton("查看原始信息")
        self.raw_toggle.setProperty("role", "quiet")
        self.raw_toggle.setCursor(Qt.PointingHandCursor)
        self.raw_toggle.clicked.connect(self._toggle_raw)
        layout.addWidget(self.raw_toggle, alignment=Qt.AlignLeft)
        self.raw_box = QPlainTextEdit()
        self.raw_box.setReadOnly(True)
        self.raw_box.setMaximumHeight(110)
        self.raw_box.hide()
        layout.addWidget(self.raw_box)
        return card

    def _build_media_card(self) -> QFrame:
        card = widgets.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        body = QHBoxLayout()
        body.setSpacing(18)
        self.thumb = widgets.Thumbnail(260, 146, 0)
        body.addWidget(self.thumb, alignment=Qt.AlignTop)

        info_box = QVBoxLayout()
        info_box.setSpacing(7)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self.site_badge = QLabel("站点")
        self.site_badge.setObjectName("Badge")
        meta_row.addWidget(self.site_badge)
        self.uploader_label = widgets.ElidedLabel("")
        self.uploader_label.setObjectName("Muted")
        meta_row.addWidget(self.uploader_label)
        self.duration_label = QLabel("")
        self.duration_label.setObjectName("MonoDim")
        meta_row.addWidget(self.duration_label)
        self.views_label = QLabel("")
        self.views_label.setObjectName("Dim")
        meta_row.addWidget(self.views_label)
        meta_row.addStretch(1)
        info_box.addLayout(meta_row)

        self.title_label = widgets.ElidedLabel("")
        self.title_label.setObjectName("MediaTitle")
        info_box.addWidget(self.title_label)

        self.desc_label = widgets.ElidedLabel("")
        self.desc_label.setObjectName("Muted")
        info_box.addWidget(self.desc_label)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(10)
        q_label = QLabel("画质")
        q_label.setObjectName("SectionHint")
        quality_row.addWidget(q_label)
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(200)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        quality_row.addWidget(self.preset_combo, 1)
        self.formats_btn = QPushButton("全部格式")
        self.formats_btn.setProperty("role", "ghost")
        self.formats_btn.setCursor(Qt.PointingHandCursor)
        self.formats_btn.clicked.connect(self._show_formats)
        quality_row.addWidget(self.formats_btn)
        info_box.addLayout(quality_row)
        self.preset_hint = QLabel("")
        self.preset_hint.setObjectName("Dim")
        self.preset_hint.setWordWrap(True)
        info_box.addWidget(self.preset_hint)

        option_row = QHBoxLayout()
        option_row.setSpacing(16)
        self.subs_check = QCheckBox("下载字幕")
        self.subs_check.setChecked(self.settings.write_subs)
        self.thumb_check = QCheckBox("嵌入封面")
        self.thumb_check.setChecked(self.settings.embed_thumbnail)
        self.meta_check = QCheckBox("写入元数据")
        self.meta_check.setChecked(self.settings.embed_metadata)
        for box in (self.subs_check, self.thumb_check, self.meta_check):
            option_row.addWidget(box)
        option_row.addStretch(1)
        info_box.addLayout(option_row)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.dir_label = widgets.ElidedLabel(self.settings.download_dir)
        self.dir_label.setObjectName("Dim")
        folder_btn = widgets.IconButton("folder", "更改下载目录", 16, theme.active["muted"])
        folder_btn.clicked.connect(self._choose_dir)
        bottom.addWidget(QLabel("保存到"))
        bottom.addWidget(self.dir_label, 1)
        bottom.addWidget(folder_btn)
        bottom.addStretch(1)
        self.download_btn = widgets.make_button("开始下载", "primary", "download",
                                                on_click=self._on_download_clicked, height=40)
        self.download_btn.setMinimumWidth(146)
        bottom.addWidget(self.download_btn)
        info_box.addLayout(bottom)

        body.addLayout(info_box, 1)
        layout.addLayout(body)
        return card

    # ------------------------------------------------------------- actions
    def _paste(self) -> None:
        from PySide6.QtWidgets import QApplication

        text = QApplication.clipboard().text().strip()
        if not text:
            return
        if "\n" in text:
            text = text.splitlines()[0].strip()
        self.url_input.setText(text)
        self.url_input.setFocus()
        if _looks_like_url(text):
            self._on_parse_clicked()

    def _on_url_changed(self, text: str) -> None:
        text = text.strip()
        self.parse_btn.setEnabled(bool(text))

    def _on_parse_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self.url_input.setFocus()
            return
        self.clear_error()
        self.media_card.hide()
        self.empty.hide()
        self.loading_row.show()
        if "douyin.com" in url:
            self.loading_label.setText("抖音链接需要启动本机浏览器解析，约 10 秒，请稍候…")
        else:
            self.loading_label.setText("正在解析链接，请稍候…")
        self.parse_btn.setEnabled(False)
        self.parse_btn.setText("解析中…")
        self.parse_requested.emit(url, self.playlist_check.isChecked())

    def set_loading(self, loading: bool, message: str = "") -> None:
        self.loading_row.setVisible(loading)
        if message:
            self.loading_label.setText(message)
        self.parse_btn.setEnabled(not loading and bool(self.url_input.text().strip()))
        self.parse_btn.setText("解析中…" if loading else "解析")

    def show_error(self, problem: Problem) -> None:
        self._error_problem = problem
        self.loading_row.hide()
        self.media_card.hide()
        self.empty.show()
        self.error_card.show()
        self.err_title.setText(problem.title)
        self.err_detail.setText(problem.detail)
        self.raw_box.setPlainText(problem.raw or problem.title)

        while self.err_fixes.count():
            item = self.err_fixes.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for fix in problem.fixes:
            button = QPushButton(fix.label)
            button.setProperty("role", "ghost")
            button.setCursor(Qt.PointingHandCursor)
            url = self.url_input.text().strip()
            button.clicked.connect(
                lambda _=False, f=fix, p=problem, u=url: self.fix_requested.emit(f.action, p, u)
            )
            self.err_fixes.addWidget(button)
        self.err_fixes.addStretch(1)


    def clear_error(self) -> None:
        self._error_problem = None
        self.error_card.hide()
        self.raw_box.hide()
        self.raw_toggle.setText("查看原始信息")

    def _toggle_raw(self) -> None:
        visible = not self.raw_box.isVisible()
        self.raw_box.setVisible(visible)
        self.raw_toggle.setText("收起原始信息" if visible else "查看原始信息")

    # --------------------------------------------------------- media state
    def show_media(self, info: dict[str, Any]) -> None:
        self._info = info
        summary = fmt.summarize(info)
        self.loading_row.hide()
        self.empty.hide()
        self.error_card.hide()
        self.media_card.show()

        self.site_badge.setText(site_label(summary["extractor"]))
        uploader = summary["uploader"]
        self.uploader_label.setText(uploader[:28] if uploader else "")
        is_images = info.get("_type") == "images"
        is_live = bool(info.get("live_photo"))
        if is_images:
            count = int(info.get("image_count") or 0)
            self.duration_label.setText(
                f"实况 · {count} 张 + 动态" if is_live else f"图文 · {count} 张")
        else:
            self.duration_label.setText(
                paths.human_duration(summary["duration"]) if summary["duration"] else "")
        self.download_btn.setText("下载实况" if is_live else ("下载图文" if is_images else "开始下载"))
        views = summary["view_count"]
        self.views_label.setText(f"· {_compact_number(views)} 次播放" if views else "")
        self.title_label.setText(summary["title"])
        desc = summary["description"].replace("\n", " ").strip()
        self.desc_label.setText(desc)
        self.desc_label.setVisible(bool(desc))

        self.thumb.set_thumbnail(None)
        self._thumb_url = summary["thumbnail"]
        self.thumb.set_placeholder(summary["title"][:2])
        if self._thumb_url:
            pixmap = self._loader.load(self._thumb_url)
            if pixmap:
                self.thumb.set_thumbnail(pixmap)

        self._populate_presets()

        self.dir_label.setText(self.settings.download_dir)
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("解析")

    def _populate_presets(self) -> None:
        lang = self.settings.effective_language()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        if (self._info or {}).get("_type") == "images":
            count = int((self._info or {}).get("image_count") or 0)
            live = bool((self._info or {}).get("live_photo"))
            self.preset_combo.addItem(
                f"实况 · {count} 张（打包 ZIP）" if live else f"图文 · {count} 张（打包 ZIP）",
                "best")
            self.formats_btn.hide()
            self.preset_hint.setText(
                "实况照片会打包静态图 + 动态视频（ZIP）。" if live
                else "图文作品会打包成一个 ZIP，内含原始图片。")
            self.preset_combo.blockSignals(False)
            return
        self.formats_btn.show()
        availability = fmt.preset_availability(self._info, lang)
        target_index = 0
        for preset, ok, hint in availability:
            self.preset_combo.addItem(preset.label_for(lang), preset.key)
            index = self.preset_combo.count() - 1
            model = self.preset_combo.model()
            if isinstance(model, QStandardItemModel) and not ok:
                item = model.item(index)
                if item:
                    item.setEnabled(False)
            if preset.key == self.settings.last_preset:
                target_index = index
        self.preset_combo.blockSignals(False)
        self.preset_combo.setCurrentIndex(target_index)
        self._on_preset_changed(target_index)

    def _on_preset_changed(self, index: int) -> None:
        key = self.preset_combo.itemData(index) or "best"
        preset = fmt.get_preset(key)
        lang = self.settings.effective_language()
        self.preset_hint.setText(preset.hint_for(lang))
        if preset.kind == "audio":
            self.thumb_check.setChecked(False)
            self.thumb_check.setEnabled(False)
            self.subs_check.setEnabled(False)
        else:
            self.thumb_check.setEnabled(True)
            self.subs_check.setEnabled(True)
            self.thumb_check.setChecked(self.settings.embed_thumbnail)

    def _choose_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择下载目录", self.settings.download_dir)
        if folder:
            self.settings.download_dir = folder
            self.settings.save()
            self.dir_label.setText(folder)
            self.settings_changed.emit()

    def _show_formats(self) -> None:
        from app.ui.format_dialog import FormatsDialog

        dialog = FormatsDialog(self._info, self)
        dialog.exec()

    def _on_download_clicked(self) -> None:
        if not self._info:
            return
        summary = fmt.summarize(self._info)
        preset_key = self.preset_combo.currentData() or "best"
        if preset_key == "custom":
            self.settings_page_requested.emit()
            widgets.Toast(self.window()).show_message(
                "自定义格式请在设置页填写 format 表达式", "info")
            return
        task = DownloadTask(
            url=summary["webpage_url"] or self.url_input.text().strip(),
            title=summary["title"],
            site=site_label(summary["extractor"]),
            preset=preset_key,
            thumbnail=summary["thumbnail"],
            duration=summary["duration"],
            playlist=self.playlist_check.isChecked(),
        )
        # Persist per-download toggles so the next download keeps the choice.
        self.settings.embed_thumbnail = self.thumb_check.isChecked()
        self.settings.embed_metadata = self.meta_check.isChecked()
        self.settings.write_subs = self.subs_check.isChecked()
        self.settings.last_preset = preset_key
        self.settings.save()
        self.download_requested.emit(task)
        self.media_card.hide()
        self.empty.show()
        self.url_input.clear()

    # ------------------------------------------------------------- helpers
    def reset(self) -> None:
        self._info = None
        self.clear_error()
        self.media_card.hide()
        self.loading_row.hide()
        self.empty.show()
        self.parse_btn.setEnabled(bool(self.url_input.text().strip()))
        self.parse_btn.setText("解析")

    def _on_pixmap(self, url: str, pixmap) -> None:
        if url == self._thumb_url and self.media_card.isVisible():
            self.thumb.set_thumbnail(pixmap)


def _looks_like_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://") or "." in text


def _compact_number(value: int | None) -> str:
    if not value:
        return ""
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f} 亿"
    if value >= 10_000:
        return f"{value / 10_000:.1f} 万"
    return f"{value:,}"
