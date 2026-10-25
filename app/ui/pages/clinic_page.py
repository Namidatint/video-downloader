"""Problem clinic: environment self-check + searchable error handbook."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from app.core import diagnostics
from app.core.errors import Problem, catalog
from app.ui import icons, theme, widgets


class _Dot(QLabel):
    def __init__(self, status: str, parent: QWidget | None = None):
        super().__init__(parent)
        color = {"pass": theme.active["success"], "warn": theme.active["warn"], "fail": theme.active["danger"]}.get(
            status, theme.active["muted"])
        self.setFixedSize(8, 8)
        self.setStyleSheet(f"background: {color};")


class CheckRow(QFrame):
    def __init__(self, check: diagnostics.CheckResult, parent: QWidget | None = None,
                 fix_callback=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 7, 4, 7)
        layout.setSpacing(10)
        layout.addWidget(_Dot(check.status), alignment=Qt.AlignTop)
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        title = QLabel(check.title)
        title.setObjectName("SectionTitle")
        text_box.addWidget(title)
        detail = QLabel(check.detail)
        detail.setObjectName("Dim")
        detail.setWordWrap(True)
        text_box.addWidget(detail)
        layout.addLayout(text_box, 1)
        if check.fix and fix_callback:
            fix = check.fix
            button = QPushButton("修复")
            button.setProperty("role", "ghost")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda: fix_callback(fix.action))
            layout.addWidget(button, alignment=Qt.AlignVCenter)


class ProblemRow(QFrame):
    fix_requested = Signal(str, object)

    def __init__(self, problem: Problem, parent: QWidget | None = None):
        super().__init__(parent)
        self.problem = problem
        self._expanded = False
        self.setObjectName("CardSoft")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(9)
        self.marker = QLabel()
        self.marker.setFixedSize(7, 7)
        self.marker.setStyleSheet(f"background: transparent; border: 1px solid {theme.active['muted']};")
        header.addWidget(self.marker, alignment=Qt.AlignVCenter)
        self.toggle = QPushButton(problem.title)
        self.toggle.setProperty("role", "quiet")
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setStyleSheet("text-align: left; font-weight: 600; font-size: 13.5px;")
        self.toggle.clicked.connect(self._toggle)
        header.addWidget(self.toggle, 1)
        kind = {"error": "error", "warning": "warn", "info": "info"}.get(problem.severity, "info")
        header.addWidget(widgets.StatusPill(
            {"error": "错误", "warn": "提醒", "info": "提示"}.get(kind, "错误"),
            "error" if kind == "error" else ("warn" if kind == "warn" else "info"),
        ))
        outer.addLayout(header)

        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(20, 2, 0, 4)
        body_layout.setSpacing(8)
        detail = QLabel(problem.detail)
        detail.setWordWrap(True)
        detail.setObjectName("Muted")
        body_layout.addWidget(detail)
        if problem.raw:
            raw = QLabel(problem.raw[:500])
            raw.setWordWrap(True)
            raw.setObjectName("Dim")
            body_layout.addWidget(raw)
        if problem.fixes:
            fix_row = QHBoxLayout()
            fix_row.setSpacing(8)
            for fix in problem.fixes:
                button = QPushButton(fix.label)
                button.setProperty("role", "ghost")
                button.setCursor(Qt.PointingHandCursor)
                button.clicked.connect(lambda _=False, f=fix: self.fix_requested.emit(
                    f.action, self.problem))
                fix_row.addWidget(button)
            fix_row.addStretch(1)
            body_layout.addLayout(fix_row)
        self.body.hide()
        outer.addWidget(self.body)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self.body.setVisible(self._expanded)
        self.marker.setStyleSheet(
            "background: %s; border: 1px solid %s;"
            % (theme.active["accent"] if self._expanded else "transparent",
               theme.active["accent"] if self._expanded else theme.active["muted"])
        )

    def matches(self, needle: str) -> bool:
        if not needle:
            return True
        haystack = " ".join((self.problem.title, self.problem.detail, self.problem.code)).lower()
        return needle in haystack


class ClinicPage(QWidget):
    rerun_requested = Signal()
    fix_requested = Signal(str, object)

    def __init__(self, settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.settings = settings
        self._problem_rows: list[ProblemRow] = []
        self._build_ui()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("诊断")
        title.setObjectName("PageTitle")
        subtitle = QLabel("检查运行环境，定位并修复常见问题。")
        subtitle.setObjectName("PageSub")
        box.addWidget(title)
        box.addWidget(subtitle)
        header.addLayout(box)
        header.addStretch(1)
        self.rerun_btn = widgets.make_button("重新自检", "primary", "pulse",
                                             on_click=self.rerun_requested.emit, height=38)
        header.addWidget(self.rerun_btn)
        root.addLayout(header)

        self.banner = widgets.Card()
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(18, 14, 18, 14)
        banner_layout.setSpacing(14)
        self.banner_icon = QLabel()
        self.banner_icon.setPixmap(icons.pixmap("pulse", theme.active["accent"], 28))
        banner_layout.addWidget(self.banner_icon)
        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        self.banner_title = QLabel("正在检查运行环境…")
        self.banner_title.setObjectName("CardTitle")
        self.banner_detail = QLabel("检查网络、登录状态、存储空间与证书。")
        self.banner_detail.setObjectName("Muted")
        self.banner_detail.setWordWrap(True)
        text_box.addWidget(self.banner_title)
        text_box.addWidget(self.banner_detail)
        banner_layout.addLayout(text_box, 1)
        self.banner_pill = widgets.StatusPill("检查中", "info")
        banner_layout.addWidget(self.banner_pill, alignment=Qt.AlignTop)
        root.addWidget(self.banner)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 6, 0)
        content.setSpacing(14)

        checks_card = widgets.Card()
        checks_layout = QVBoxLayout(checks_card)
        checks_layout.setContentsMargins(18, 14, 18, 14)
        checks_layout.setSpacing(4)
        checks_header = QLabel("环境自检")
        checks_header.setObjectName("SectionTitle")
        checks_layout.addWidget(checks_header)
        self.checks_box = QVBoxLayout()
        self.checks_box.setSpacing(0)
        checks_layout.addLayout(self.checks_box)
        content.addWidget(checks_card)

        handbook_card = widgets.Card()
        handbook_layout = QVBoxLayout(handbook_card)
        handbook_layout.setContentsMargins(18, 14, 18, 14)
        handbook_layout.setSpacing(10)
        top = QHBoxLayout()
        handbook_title = QLabel("错误说明")
        handbook_title.setObjectName("SectionTitle")
        top.addWidget(handbook_title)
        top.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索错误，例如 403 / 登录")
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(self._on_search)
        top.addWidget(self.search)
        handbook_layout.addLayout(top)
        hint = QLabel("点击条目展开原因与修复动作。")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        handbook_layout.addWidget(hint)

        self.handbook_box = QVBoxLayout()
        self.handbook_box.setSpacing(6)
        handbook_layout.addLayout(self.handbook_box)
        content.addWidget(handbook_card)
        content.addStretch(1)

        self.scroll.setWidget(container)
        root.addWidget(self.scroll, 1)

        self.reload_handbook()

    # ------------------------------------------------------------- data
    def reload_handbook(self) -> None:
        lang = self.settings.effective_language()
        while self.handbook_box.count():
            item = self.handbook_box.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._problem_rows = []
        for problem in catalog(lang):
            row = ProblemRow(problem)
            row.fix_requested.connect(self.fix_requested.emit)
            self.handbook_box.addWidget(row)
            self._problem_rows.append(row)

    def _on_search(self, text: str) -> None:
        needle = text.strip().lower()
        for row in self._problem_rows:
            row.setVisible(row.matches(needle))

    def set_running(self, running: bool) -> None:
        self.rerun_btn.setEnabled(not running)
        self.rerun_btn.setText("检查中…" if running else "重新自检")
        if running:
            self.banner_title.setText("正在检查运行环境…")
            self.banner_detail.setText("检查网络、登录状态、存储空间与证书。")
            self.banner_pill.setText("检查中")
            self.banner_pill.set_kind("info")
            self._set_check_placeholder("正在检查组件、目录、网络与登录状态…")

    def _set_check_placeholder(self, text: str) -> None:
        while self.checks_box.count():
            item = self.checks_box.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        label = QLabel(text)
        label.setObjectName("Dim")
        label.setContentsMargins(4, 10, 4, 12)
        self.checks_box.addWidget(label)

    def set_checks(self, checks: list[diagnostics.CheckResult]) -> None:
        while self.checks_box.count():
            item = self.checks_box.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for index, check in enumerate(checks):
            self.checks_box.addWidget(CheckRow(check, fix_callback=self._fix_check))
            if index < len(checks) - 1:
                self.checks_box.addWidget(widgets.hline())

        overall = diagnostics.overall_status(checks)
        fails = [c for c in checks if c.status == diagnostics.FAIL]
        warns = [c for c in checks if c.status == diagnostics.WARN]
        if overall == diagnostics.PASS:
            self.banner_icon.setPixmap(icons.pixmap("check", theme.active["success"], 28))
            self.banner_title.setText("一切正常，可以开始下载")
            self.banner_detail.setText("所有检查均已通过。")
            self.banner_pill.setText("健康")
            self.banner_pill.set_kind("ok")
        elif overall == diagnostics.WARN:
            self.banner_icon.setPixmap(icons.pixmap("warn", theme.active["warn"], 28))
            self.banner_title.setText(f"{len(warns)} 项建议优化")
            self.banner_detail.setText("这些不是致命问题，但可能影响高清下载或速度。")
            self.banner_pill.setText("可用")
            self.banner_pill.set_kind("warn")
        else:
            self.banner_icon.setPixmap(icons.pixmap("error", theme.active["danger"], 28))
            self.banner_title.setText(f"发现 {len(fails)} 个需要修复的问题")
            self.banner_detail.setText("按下列条目的“修复”按钮处理，或查看报错百科寻找对应说明。")
            self.banner_pill.setText("需修复")
            self.banner_pill.set_kind("error")

    def _fix_check(self, action: str) -> None:
        self.fix_requested.emit(action, None)
