"""Windows 10 Settings-style settings page.

Rows: label + description on the left, the control on the right, separated by
hairlines inside a card. Helper copy stays to one line per row.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

from app import APP_AUTHOR, __version__ as app_version
from app.core import cookies as cookies_mod
from app.core import formats as fmt, paths
from app.core.settings import Settings
from app.ui import theme, widgets


def _card(title: str, hint: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = widgets.Card()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    head = QWidget()
    head_layout = QVBoxLayout(head)
    head_layout.setContentsMargins(20, 16, 20, 10)
    head_layout.setSpacing(2)
    label = QLabel(title)
    label.setObjectName("SectionHeader")
    head_layout.addWidget(label)
    if hint:
        sub = QLabel(hint)
        sub.setObjectName("SectionHint")
        sub.setWordWrap(True)
        head_layout.addWidget(sub)
    layout.addWidget(head)
    layout.addWidget(widgets.hline())
    return card, layout


def _row(title: str, control: QWidget, description: str = "",
         control_width: int = 300) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(20, 12, 20, 12)
    layout.setSpacing(24)
    text_box = QVBoxLayout()
    text_box.setSpacing(2)
    label = QLabel(title)
    label.setObjectName("Value")
    text_box.addWidget(label)
    if description:
        desc = QLabel(description)
        desc.setObjectName("SectionHint")
        desc.setWordWrap(True)
        text_box.addWidget(desc)
    layout.addLayout(text_box, 1)
    if control_width > 0:
        control.setMinimumWidth(control_width)
        control.setMaximumWidth(control_width)
    layout.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
    return row


def _add(layout: QVBoxLayout, row: QWidget, last: bool = False) -> None:
    layout.addWidget(row)
    if not last:
        layout.addWidget(widgets.hline())


def _select(combo: QComboBox, value: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


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
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(14)

        title = QLabel("设置")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        subtitle = QLabel("更改下载、网络和界面选项。部分更改需要重启应用。")
        subtitle.setObjectName("PageSub")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 4, 8, 0)
        content.setSpacing(14)

        content.addWidget(self._build_download_card())
        content.addWidget(self._build_quality_card())
        content.addWidget(self._build_network_card())
        content.addWidget(self._build_login_card())
        content.addWidget(self._build_appearance_card())
        content.addWidget(self._build_update_card())
        content.addWidget(self._build_about_card())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def _build_download_card(self) -> QFrame:
        card, layout = _card("下载")
        self.dir_edit = QLineEdit()
        self.dir_edit.editingFinished.connect(self._on_dir_edited)
        browse = QPushButton("选择")
        browse.clicked.connect(self._choose_dir)
        open_btn = QPushButton("打开")
        open_btn.clicked.connect(lambda: paths.open_in_file_manager(self.settings.output_dir))
        dir_box = QWidget()
        dir_layout = QHBoxLayout(dir_box)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(6)
        dir_layout.addWidget(self.dir_edit, 1)
        dir_layout.addWidget(browse)
        dir_layout.addWidget(open_btn)
        _add(layout, _row("下载位置", dir_box, "视频保存到该文件夹。", control_width=430))

        self.template_edit = QLineEdit()
        self.template_edit.editingFinished.connect(self._on_template_edited)
        _add(layout, _row("文件名", self.template_edit,
                          "可用 %(title)s、%(id)s、%(ext)s 等字段。", control_width=430))

        self.playlist_check = QCheckBox("按播放列表下载")
        self.playlist_check.toggled.connect(self._on_toggle)
        _add(layout, _row("播放列表", self.playlist_check, "播放列表链接会整体加入队列。"))

        self.thumb_check = QCheckBox()
        self.thumb_check.toggled.connect(self._on_toggle)
        self.meta_check = QCheckBox()
        self.meta_check.toggled.connect(self._on_toggle)
        self.subs_check = QCheckBox()
        self.subs_check.toggled.connect(self._on_toggle)
        self.sponsor_check = QCheckBox()
        self.sponsor_check.toggled.connect(self._on_toggle)
        embed_box = QWidget()
        embed_layout = QHBoxLayout(embed_box)
        embed_layout.setContentsMargins(0, 0, 0, 0)
        embed_layout.setSpacing(16)
        for text, check in (("封面", self.thumb_check), ("元数据", self.meta_check),
                            ("字幕", self.subs_check), ("跳过赞助片段", self.sponsor_check)):
            label = QLabel(text)
            label.setObjectName("Muted")
            embed_layout.addWidget(check)
            embed_layout.addWidget(label)
        _add(layout, _row("下载内容", embed_box, "嵌入封面、元数据或同时下载字幕。", control_width=440))

        self.sub_langs_edit = QLineEdit()
        self.sub_langs_edit.setPlaceholderText("zh-Hans,zh,en")
        self.sub_langs_edit.editingFinished.connect(self._on_text_edited)
        _add(layout, _row("字幕语言", self.sub_langs_edit, "多个语言用逗号分隔。"), last=True)
        return card

    def _build_quality_card(self) -> QFrame:
        card, layout = _card("画质")
        self.preset_combo = QComboBox()
        lang = self.settings.effective_language()
        for preset in fmt.PRESETS:
            self.preset_combo.addItem(preset.label_for(lang), preset.key)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        _add(layout, _row("默认画质", self.preset_combo, "每次下载仍可单独调整。"))

        self.custom_format_edit = QLineEdit()
        self.custom_format_edit.setPlaceholderText("仅“自定义格式”使用")
        self.custom_format_edit.editingFinished.connect(self._on_text_edited)
        _add(layout, _row("自定义格式", self.custom_format_edit,
                          "高级：填写格式表达式，例如 bv*[height<=1080]+ba。", control_width=430))

        self.mp4_check = QCheckBox()
        self.mp4_check.toggled.connect(self._on_toggle)
        _add(layout, _row("优先 MP4", self.mp4_check, "兼容性最好，必要时才合并为其他格式。"))

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(50, 200)
        self.concurrent_spin.setValue(50)
        self.concurrent_spin.setFixedWidth(110)
        self.concurrent_spin.valueChanged.connect(self._on_spin_changed)
        _add(layout, _row("同时下载数", self.concurrent_spin,
                          "至少 50 个任务并行（50–200）。", control_width=110), last=True)
        return card

    def _build_network_card(self) -> QFrame:
        card, layout = _card("网络", "代理软件关闭后若无法联网，把网络模式改为“直连”。")
        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.addItem("跟随系统", "system")
        self.proxy_mode_combo.addItem("直连", "direct")
        self.proxy_mode_combo.addItem("自定义代理", "custom")
        self.proxy_mode_combo.currentIndexChanged.connect(self._on_proxy_mode_changed)
        _add(layout, _row("网络模式", self.proxy_mode_combo,
                          "跟随系统会使用 macOS/Windows 的系统代理。"))

        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http://127.0.0.1:7890")
        self.proxy_edit.editingFinished.connect(self._on_proxy_edited)
        _add(layout, _row("代理地址", self.proxy_edit, "仅在“自定义代理”下使用。", control_width=380))

        self.proxy_hint = QLabel("")
        self.proxy_hint.setObjectName("Dim")
        self.proxy_hint.setWordWrap(True)
        hint_row = QWidget()
        hint_layout = QVBoxLayout(hint_row)
        hint_layout.setContentsMargins(20, 4, 20, 10)
        hint_layout.addWidget(self.proxy_hint)
        layout.addWidget(hint_row)
        layout.addWidget(widgets.hline())

        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(0, 1024 * 200)
        self.rate_spin.setFixedWidth(150)
        self.rate_spin.setSuffix(" KB/s")
        self.rate_spin.setSpecialValueText("不限速")
        self.rate_spin.valueChanged.connect(self._on_spin_changed)
        _add(layout, _row("限速", self.rate_spin, "0 表示不限速。", control_width=150))

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 50)
        self.retries_spin.setFixedWidth(110)
        self.retries_spin.valueChanged.connect(self._on_spin_changed)
        _add(layout, _row("失败重试", self.retries_spin, "网络中断时自动重试的次数。", control_width=110))

        self.fragments_spin = QSpinBox()
        self.fragments_spin.setRange(1, 16)
        self.fragments_spin.setFixedWidth(110)
        self.fragments_spin.valueChanged.connect(self._on_spin_changed)
        _add(layout, _row("分片并发", self.fragments_spin, "同时下载的分片数量。", control_width=110))

        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText("留空使用默认值")
        self.ua_edit.editingFinished.connect(self._on_text_edited)
        _add(layout, _row("User-Agent", self.ua_edit, "仅特殊站点需要修改。", control_width=380))

        self.referer_edit = QLineEdit()
        self.referer_edit.setPlaceholderText("部分站点需要")
        self.referer_edit.editingFinished.connect(self._on_text_edited)
        _add(layout, _row("Referer", self.referer_edit, "部分站点需要来源页地址。", control_width=380), last=True)
        return card

    def _build_login_card(self) -> QFrame:
        card, layout = _card("登录", "读取浏览器登录状态，用于高清或需要登录的内容。只在本机读取。")
        self.browser_combo = QComboBox()
        lang = self.settings.effective_language()
        for key, label in cookies_mod.browser_options(include_none=True, lang=lang):
            self.browser_combo.addItem(label, key)
        self.browser_combo.currentIndexChanged.connect(self._on_browser_changed)
        _add(layout, _row("浏览器", self.browser_combo, "选择你已登录目标网站的浏览器。"))

        self.cookie_file_edit = QLineEdit()
        self.cookie_file_edit.setPlaceholderText("可选：cookies.txt")
        self.cookie_file_edit.editingFinished.connect(self._on_cookie_file_edited)
        pick = QPushButton("选择")
        pick.clicked.connect(self._choose_cookie_file)
        file_box = QWidget()
        file_layout = QHBoxLayout(file_box)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(6)
        file_layout.addWidget(self.cookie_file_edit, 1)
        file_layout.addWidget(pick)
        _add(layout, _row("Cookie 文件", file_box, "支持 cookies.txt 或浏览器导出的 JSON。", control_width=430))

        self.cookie_status = QLabel(cookies_mod.cookie_hint(lang))
        self.cookie_status.setObjectName("Dim")
        self.cookie_status.setWordWrap(True)
        status_box = QWidget()
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(20, 6, 20, 12)
        status_layout.addWidget(self.cookie_status)
        layout.addWidget(status_box)
        return card

    def _build_appearance_card(self) -> QFrame:
        card, layout = _card("个性化")
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        _add(layout, _row("主题", self.theme_combo, "切换后重启应用生效。"))

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("跟随系统", "auto")
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        _add(layout, _row("语言", self.lang_combo, "影响部分提示文案。"))

        self.open_folder_check = QCheckBox()
        self.open_folder_check.toggled.connect(self._on_toggle)
        _add(layout, _row("完成后打开文件夹", self.open_folder_check, "下载完成后自动定位文件。"))

        self.notify_check = QCheckBox()
        self.notify_check.toggled.connect(self._on_toggle)
        _add(layout, _row("完成时通知", self.notify_check, "在系统通知中心显示下载结果。"), last=True)
        return card

    def _build_update_card(self) -> QFrame:
        card, layout = _card("更新", "保持解析组件为最新版本，以获得新站点支持。")
        self.update_btn = widgets.make_button("检查更新", "primary", on_click=self.update_requested.emit)
        self.update_btn.setFixedWidth(130)
        _add(layout, _row("组件更新", self.update_btn, "无需重新安装应用。"))
        self.core_status = QLabel("")
        self.core_status.setObjectName("Dim")
        self.core_status.setWordWrap(True)
        status_box = QWidget()
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(20, 4, 20, 12)
        status_layout.addWidget(self.core_status)
        layout.addWidget(status_box)
        return card

    def _build_about_card(self) -> QFrame:
        card, layout = _card("关于")
        version = QLabel(f"视频下载器  {app_version}")
        version.setObjectName("Value")
        legal = QLabel("仅用于下载你有权保存的内容，请遵守目标站点的服务条款与当地法律。")
        legal.setObjectName("SectionHint")
        legal.setWordWrap(True)
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(20, 4, 20, 16)
        box_layout.setSpacing(4)
        byline = QLabel(f"by {APP_AUTHOR}")
        byline.setObjectName("Muted")
        box_layout.addWidget(version)
        box_layout.addWidget(byline)
        box_layout.addWidget(legal)
        layout.addWidget(box)
        return card

    # ------------------------------------------------------------- state
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
        self.concurrent_spin.setValue(max(50, s.max_concurrent))
        _select(self.proxy_mode_combo, getattr(s, "proxy_mode", "system"))
        self.proxy_edit.setText(s.proxy)
        self.rate_spin.setValue(s.rate_limit_kbps)
        self.retries_spin.setValue(s.retries)
        self.fragments_spin.setValue(s.fragment_concurrency)
        self.ua_edit.setText(s.user_agent)
        self.referer_edit.setText(s.referer)
        self.cookie_file_edit.setText(s.cookies_file)
        self.open_folder_check.setChecked(s.open_folder_when_done)
        self.notify_check.setChecked(s.notify_on_finish)
        _select(self.preset_combo, s.last_preset)
        _select(self.browser_combo, s.cookies_browser)
        _select(self.theme_combo, s.theme if s.theme in ("light", "dark") else "light")
        _select(self.lang_combo, s.language)
        self._sync_proxy_mode_ui()
        self._loading = False

    def set_core_status(self, text: str, kind: str = "info") -> None:
        colors = {
            "ok": theme.active["success"],
            "warn": theme.active["warn"],
            "error": theme.active["danger"],
            "info": theme.active["muted"],
        }
        self.core_status.setText(text)
        self.core_status.setStyleSheet(f"color: {colors.get(kind, theme.active['muted'])};")

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
        s.proxy_mode = self.proxy_mode_combo.currentData() or "system"
        s.proxy = self.proxy_edit.text().strip()
        s.rate_limit_kbps = self.rate_spin.value()
        s.retries = self.retries_spin.value()
        s.fragment_concurrency = self.fragments_spin.value()
        s.user_agent = self.ua_edit.text().strip()
        s.referer = self.referer_edit.text().strip()
        s.cookies_file = self.cookie_file_edit.text().strip()
        s.cookies_browser = self.browser_combo.currentData() or ""
        s.last_preset = self.preset_combo.currentData() or "best"
        s.theme = self.theme_combo.currentData() or "light"
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

    def _on_proxy_mode_changed(self, _index: int) -> None:
        self._sync_proxy_mode_ui()
        self._commit()

    def _sync_proxy_mode_ui(self) -> None:
        mode = self.proxy_mode_combo.currentData() or "system"
        self.proxy_edit.setEnabled(mode == "custom")
        if mode == "direct":
            self.proxy_hint.setText("所有请求直连，不读取系统代理。")
        elif mode == "custom":
            self.proxy_hint.setText("只使用上面填写的代理地址，支持 http:// 与 socks5://。")
        else:
            self.proxy_hint.setText("自动读取系统代理；代理软件关闭后连不上时，请改为“直连”。")

    def _choose_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择下载位置", self.settings.download_dir)
        if folder:
            self.dir_edit.setText(folder)
            self._commit()

    def _choose_cookie_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Cookie 文件", "", "Cookie 文件 (*.txt *.json);;所有文件 (*.*)")
        if path:
            self.cookie_file_edit.setText(path)
            self._commit()
            self._validate_cookie_file()

    def _validate_cookie_file(self) -> None:
        ok, message = cookies_mod.validate_cookiefile(self.cookie_file_edit.text().strip())
        self.cookie_status.setText(message)
        self.cookie_status.setStyleSheet(
            f"color: {theme.active['success'] if ok else theme.active['danger']};")
