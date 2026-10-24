"""Settings page: every option with immediate persistence."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from app import __version__ as app_version
from app.core import cookies as cookies_mod
from app.core import engine, formats as fmt, paths
from app.core.settings import Settings
from app.ui import widgets
from app.ui.theme import DARK


def _section(title: str, hint: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = widgets.Card()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(10)
    head = QLabel(title)
    head.setObjectName("SectionTitle")
    layout.addWidget(head)
    if hint:
        h = QLabel(hint)
        h.setObjectName("Dim")
        h.setWordWrap(True)
        layout.addWidget(h)
    return card, layout


class SettingsPage(QWidget):
    settings_changed = Signal()
    update_requested = Signal()
    browse_cookie_requested = Signal()
    toast_requested = Signal(str, str)

    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.settings = settings
        self._loading = False
        self._build_ui()
        self.load_from_settings()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 20)
        root.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("设置")
        title.setObjectName("PageTitle")
        subtitle = QLabel("所有修改即时保存。设置项旁的文字会解释它解决什么问题。")
        subtitle.setObjectName("PageSub")
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 8, 0)
        content.setSpacing(14)

        content.addWidget(self._build_download_section())
        content.addWidget(self._build_quality_section())
        content.addWidget(self._build_network_section())
        content.addWidget(self._build_cookie_section())
        content.addWidget(self._build_appearance_section())
        content.addWidget(self._build_core_section())
        content.addWidget(self._build_about_section())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def _build_download_section(self) -> QFrame:
        card, layout = _section("下载位置与文件",
                                "目录不存在会自动创建；文件名模板使用 yt-dlp 字段，例如 %(title)s.%(ext)s。")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.editingFinished.connect(self._on_dir_edited)
        dir_row.addWidget(self.dir_edit, 1)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._choose_dir)
        dir_row.addWidget(browse)
        open_btn = QPushButton("打开")
        open_btn.clicked.connect(lambda: paths.open_in_file_manager(self.settings.output_dir))
        dir_row.addWidget(open_btn)
        form.addRow("下载目录", dir_row)

        self.template_edit = QLineEdit()
        self.template_edit.editingFinished.connect(self._on_template_edited)
        form.addRow("文件名模板", self.template_edit)

        embed_row = QHBoxLayout()
        embed_row.setSpacing(18)
        self.thumb_check = QCheckBox("嵌入封面")
        self.thumb_check.toggled.connect(self._on_toggle)
        self.meta_check = QCheckBox("写入元数据")
        self.meta_check.toggled.connect(self._on_toggle)
        self.subs_check = QCheckBox("下载字幕")
        self.subs_check.toggled.connect(self._on_toggle)
        embed_row.addWidget(self.thumb_check)
        embed_row.addWidget(self.meta_check)
        embed_row.addWidget(self.subs_check)
        embed_row.addStretch(1)
        form.addRow("后处理", embed_row)

        self.sub_langs_edit = QLineEdit()
        self.sub_langs_edit.setPlaceholderText("zh-Hans,zh,en")
        self.sub_langs_edit.editingFinished.connect(self._on_text_edited)
        form.addRow("字幕语言", self.sub_langs_edit)

        self.playlist_check = QCheckBox("默认按播放列表下载")
        self.playlist_check.toggled.connect(self._on_toggle)
        form.addRow("", self.playlist_check)
        self.sponsor_check = QCheckBox("跳过赞助片段（SponsorBlock）")
        self.sponsor_check.toggled.connect(self._on_toggle)
        form.addRow("", self.sponsor_check)

        layout.addLayout(form)
        return card

    def _build_quality_section(self) -> QFrame:
        card, layout = _section("默认画质", "每次下载仍可在首页单独调整。")
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.preset_combo = QComboBox()
        lang = self.settings.effective_language()
        for preset in fmt.PRESETS:
            self.preset_combo.addItem(preset.label_for(lang), preset.key)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        form.addRow("默认预设", self.preset_combo)

        self.custom_format_edit = QLineEdit()
        self.custom_format_edit.setPlaceholderText("仅“自定义格式”使用，例如 bv*[height<=1080]+ba")
        self.custom_format_edit.editingFinished.connect(self._on_text_edited)
        form.addRow("自定义格式", self.custom_format_edit)

        self.mp4_check = QCheckBox("优先合并为 MP4（兼容性最好）")
        self.mp4_check.toggled.connect(self._on_toggle)
        form.addRow("", self.mp4_check)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 6)
        self.concurrent_spin.setFixedWidth(120)
        self.concurrent_spin.valueChanged.connect(self._on_spin_changed)
        form.addRow("同时下载数", self.concurrent_spin)
        layout.addLayout(form)
        return card

    def _build_network_section(self) -> QFrame:
        card, layout = _section(
            "网络与速度",
            "访问 YouTube 等境外站点通常需要代理；访问 B 站/抖音一般不需要。留空表示直连。",
        )
        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http://127.0.0.1:7890  或  socks5://127.0.0.1:1080")
        self.proxy_edit.editingFinished.connect(self._on_proxy_edited)
        form.addRow("代理", self.proxy_edit)

        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(0, 1024 * 200)
        self.rate_spin.setFixedWidth(150)
        self.rate_spin.setSuffix(" KB/s")
        self.rate_spin.setSpecialValueText("不限速")
        self.rate_spin.valueChanged.connect(self._on_spin_changed)
        form.addRow("限速", self.rate_spin)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 50)
        self.retries_spin.setFixedWidth(120)
        self.retries_spin.valueChanged.connect(self._on_spin_changed)
        form.addRow("失败重试次数", self.retries_spin)

        self.fragments_spin = QSpinBox()
        self.fragments_spin.setRange(1, 16)
        self.fragments_spin.setFixedWidth(120)
        self.fragments_spin.valueChanged.connect(self._on_spin_changed)
        form.addRow("分片并发", self.fragments_spin)

        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText("留空使用默认 User-Agent")
        self.ua_edit.editingFinished.connect(self._on_text_edited)
        form.addRow("User-Agent", self.ua_edit)

        self.referer_edit = QLineEdit()
        self.referer_edit.setPlaceholderText("部分站点（如抖音）需要 Referer")
        self.referer_edit.editingFinished.connect(self._on_text_edited)
        form.addRow("Referer", self.referer_edit)
        layout.addLayout(form)
        return card

    def _build_cookie_section(self) -> QFrame:
        card, layout = _section(
            "登录态 Cookie",
            "解决 B 站 1080P+/大会员、YouTube 人机验证、抖音私密内容等问题。"
            "GlowDL 只在本机读取浏览器 Cookie，不会上传。",
        )
        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.browser_combo = QComboBox()
        lang = self.settings.effective_language()
        for key, label in cookies_mod.browser_options(include_none=True, lang=lang):
            self.browser_combo.addItem(label, key)
        self.browser_combo.currentIndexChanged.connect(self._on_browser_changed)
        form.addRow("读取浏览器", self.browser_combo)

        file_row = QHBoxLayout()
        self.cookie_file_edit = QLineEdit()
        self.cookie_file_edit.setPlaceholderText("也可以导入 cookies.txt（或 Cookie-Editor 的 JSON）")
        self.cookie_file_edit.editingFinished.connect(self._on_cookie_file_edited)
        file_row.addWidget(self.cookie_file_edit, 1)
        pick = QPushButton("选择文件")
        pick.clicked.connect(self._choose_cookie_file)
        file_row.addWidget(pick)
        check = QPushButton("校验")
        check.clicked.connect(self._validate_cookie_file)
        file_row.addWidget(check)
        form.addRow("Cookie 文件", file_row)

        self.cookie_status = QLabel(cookies_mod.cookie_hint(lang))
        self.cookie_status.setObjectName("Dim")
        self.cookie_status.setWordWrap(True)
        form.addRow("", self.cookie_status)

        installed = cookies_mod.guess_installed_browsers()
        if installed:
            names = "、".join(label for _, label in installed)
            detected = QLabel(f"检测到已安装：{names}")
            detected.setObjectName("Dim")
            form.addRow("", detected)
        layout.addLayout(form)
        return card

    def _build_appearance_section(self) -> QFrame:
        card, layout = _section("外观与提示")
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("主题", self.theme_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("跟随系统", "auto")
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        form.addRow("错误提示语言", self.lang_combo)

        self.open_folder_check = QCheckBox("下载完成后自动打开文件夹")
        self.open_folder_check.toggled.connect(self._on_toggle)
        form.addRow("", self.open_folder_check)
        self.notify_check = QCheckBox("完成时发送系统通知")
        self.notify_check.toggled.connect(self._on_toggle)
        form.addRow("", self.notify_check)
        layout.addLayout(form)
        return card

    def _build_core_section(self) -> QFrame:
        card, layout = _section(
            "下载内核 yt-dlp",
            "站点改版后旧内核会解析失败。这里可以查看版本并一键更新，无需重装整个应用。",
        )
        row = QHBoxLayout()
        self.core_version = QLabel("yt-dlp —")
        self.core_version.setObjectName("Value")
        row.addWidget(self.core_version)
        self.core_pill = widgets.StatusPill("检查中", "info")
        row.addWidget(self.core_pill)
        row.addStretch(1)
        self.update_btn = widgets.make_button("检查更新", "primary", "refresh",
                                              on_click=self.update_requested.emit)
        row.addWidget(self.update_btn)
        layout.addLayout(row)
        self.core_status = QLabel("")
        self.core_status.setObjectName("Dim")
        self.core_status.setWordWrap(True)
        layout.addWidget(self.core_status)
        return card

    def _build_about_section(self) -> QFrame:
        card, layout = _section("关于 GlowDL")
        text = QLabel(
            f"GlowDL 拾光下载器 v{app_version} · Windows / macOS\n"
            "能力内核：yt-dlp（开源，Unlicense） · 界面：PySide6 / Qt 6\n"
            "本软件仅用于下载你有权保存的内容；请遵守目标站点的服务条款与当地法律。"
        )
        text.setObjectName("Muted")
        text.setWordWrap(True)
        layout.addWidget(text)
        links = QHBoxLayout()
        for label, url in (("yt-dlp 项目主页", "https://github.com/yt-dlp/yt-dlp"),
                           ("支持的站点列表", "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md")):
            button = QPushButton(label)
            button.setProperty("role", "quiet")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, u=url: _open_url(u))
            links.addWidget(button)
        links.addStretch(1)
        layout.addLayout(links)
        return card

    # ------------------------------------------------------------- load
    def load_from_settings(self) -> None:
        self._loading = True
        s = self.settings
        self.dir_edit.setText(s.download_dir)
        self.template_edit.setText(s.filename_template)
        self.thumb_check.setChecked(s.embed_thumbnail)
        self.meta_check.setChecked(s.embed_metadata)
        self.subs_check.setChecked(s.write_subs)
        self.sub_langs_edit.setText(s.sub_langs)
        self.playlist_check.setChecked(s.playlist)
        self.sponsor_check.setChecked(s.sponsorblock)
        self.custom_format_edit.setText(s.custom_format)
        self.mp4_check.setChecked(s.prefer_mp4)
        self.concurrent_spin.setValue(s.max_concurrent)
        self.proxy_edit.setText(s.proxy)
        self.rate_spin.setValue(s.rate_limit_kbps)
        self.retries_spin.setValue(s.retries)
        self.fragments_spin.setValue(s.fragment_concurrency)
        self.ua_edit.setText(s.user_agent)
        self.referer_edit.setText(s.referer)
        self.cookie_file_edit.setText(s.cookies_file)
        self.open_folder_check.setChecked(s.open_folder_when_done)
        self.notify_check.setChecked(s.notify_on_finish)
        _select_data(self.preset_combo, s.last_preset)
        _select_data(self.browser_combo, s.cookies_browser)
        _select_data(self.theme_combo, s.theme)
        _select_data(self.lang_combo, s.language)
        self.core_version.setText(f"yt-dlp {engine.ytdlp_version()}")
        self._loading = False

    def set_core_status(self, text: str, kind: str = "info", version: str | None = None) -> None:
        self.core_status.setText(text)
        if version:
            self.core_version.setText(f"yt-dlp {version}")
        names = {"ok": "最新", "warn": "可更新", "info": "检查中", "error": "异常"}
        self.core_pill.setText(names.get(kind, "状态"))
        self.core_pill.set_kind(kind)

    # ------------------------------------------------------------- save
    def _commit(self) -> None:
        if self._loading:
            return
        s = self.settings
        s.download_dir = self.dir_edit.text().strip() or s.download_dir
        s.filename_template = self.template_edit.text().strip() or s.filename_template
        s.embed_thumbnail = self.thumb_check.isChecked()
        s.embed_metadata = self.meta_check.isChecked()
        s.write_subs = self.subs_check.isChecked()
        s.sub_langs = self.sub_langs_edit.text().strip() or "zh-Hans,zh,en"
        s.playlist = self.playlist_check.isChecked()
        s.sponsorblock = self.sponsor_check.isChecked()
        s.custom_format = self.custom_format_edit.text().strip()
        s.prefer_mp4 = self.mp4_check.isChecked()
        s.max_concurrent = self.concurrent_spin.value()
        s.proxy = self.proxy_edit.text().strip()
        s.rate_limit_kbps = self.rate_spin.value()
        s.retries = self.retries_spin.value()
        s.fragment_concurrency = self.fragments_spin.value()
        s.user_agent = self.ua_edit.text().strip()
        s.referer = self.referer_edit.text().strip()
        s.cookies_file = self.cookie_file_edit.text().strip()
        s.cookies_browser = self.browser_combo.currentData() or ""
        s.last_preset = self.preset_combo.currentData() or "best"
        s.theme = self.theme_combo.currentData() or "dark"
        s.language = self.lang_combo.currentData() or "auto"
        s.open_folder_when_done = self.open_folder_check.isChecked()
        s.notify_on_finish = self.notify_check.isChecked()
        s.validate()
        s.save()
        self.settings_changed.emit()

    # ----------------------------------------------------------- handlers
    def _on_toggle(self, _checked: bool) -> None:
        self._commit()

    def _on_spin_changed(self, _value: int) -> None:
        self._commit()

    def _on_preset_changed(self, _index: int) -> None:
        self._commit()

    def _on_browser_changed(self, _index: int) -> None:
        self._commit()

    def _on_theme_changed(self, _index: int) -> None:
        self._commit()

    def _on_lang_changed(self, _index: int) -> None:
        self._commit()

    def _on_text_edited(self) -> None:
        self._commit()

    def _on_dir_edited(self) -> None:
        self._commit()

    def _on_template_edited(self) -> None:
        self._commit()

    def _on_proxy_edited(self) -> None:
        self._commit()

    def _on_cookie_file_edited(self) -> None:
        self._commit()
        if self.settings.cookies_file:
            self._validate_cookie_file()

    def _choose_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择下载目录", self.settings.download_dir)
        if folder:
            self.dir_edit.setText(folder)
            self._commit()

    def _choose_cookie_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Cookie 文件", "",
            "Cookie 文件 (*.txt *.json);;所有文件 (*.*)")
        if path:
            self.cookie_file_edit.setText(path)
            self._commit()
            self._validate_cookie_file()

    def _validate_cookie_file(self) -> None:
        ok, message = cookies_mod.validate_cookiefile(self.cookie_file_edit.text().strip())
        self.cookie_status.setText(message)
        self.cookie_status.setStyleSheet(
            f"color: {DARK['success'] if ok else DARK['danger']};")


def _select_data(combo: QComboBox, value: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


def _open_url(url: str) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    QDesktopServices.openUrl(QUrl(url))
