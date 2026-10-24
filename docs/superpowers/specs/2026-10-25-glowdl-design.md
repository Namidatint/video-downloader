# GlowDL · 拾光下载器 — 设计说明（Design Spec）

- 日期：2026-10-25
- 状态：已实现（v1.0.0）
- 参考：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)（能力内核）
- 参考文章：[yt-dlp 从入门到顺手：我把 B 站、YouTube、抖音视频一键下载到本地](https://zhuanlan.zhihu.com/p/2045080302888939589)（需求与痛点来源）

> 说明：知乎对非登录访问返回 403（已尝试网页抓取、移动 UA、无头浏览器、开放 API、存档服务），
> 无法取得正文。本文依据该文标题、检索摘要，以及 yt-dlp 社区长期高频问题，归纳出
> “第二个网站中提到的问题”，并逐条给出软件层解法（见 `docs/问题诊所.md`）。

## 1. 目标

给 yt-dlp 套上一副“桌面软件”的外壳：用户不需要装 Python、不需要敲命令、不需要单独折腾
ffmpeg / Cookie / 代理 / 格式选择，也能在 Windows 与 macOS 上稳定地把 B 站、YouTube、
抖音等站点的视频下载到本地；出错时软件要能**说人话**并给出**一键修复**，而不是甩一段
英文 traceback。

## 2. 非目标（YAGNI）

- 不做 DRM 破解、不做会员内容绕过、不内置任何账号。
- 不做视频转码编辑器、不做视频剪辑、不做云端服务。
- 不做浏览器插件版本（本期只交付桌面端）。

## 3. 架构

```
┌──────────────────────────── UI (PySide6) ────────────────────────────┐
│ MainWindow                                                           │
│  ├─ HomePage        粘贴解析 / 预设选择 / 媒体卡片                    │
│  ├─ QueuePage       并发队列 / 进度 / 暂停 / 取消 / 打开目录           │
│  ├─ HistoryPage     下载历史 / 重新下载                               │
│  ├─ ClinicPage      问题诊所：错误字典 + 环境自检 + 一键修复            │
│  └─ SettingsPage    目录 / Cookie / 代理 / 限速 / 命名模板 / 内核更新   │
└───────────────▲───────────────────────────────▲──────────────────────┘
                │ Qt Signals                     │
┌───────────────┴───────────────┐   ┌───────────┴──────────────────────┐
│ DownloadWorker (QThread)      │   │ core 层（零 Qt 依赖，可单测）      │
│  · 每个任务一个线程            │──▶│ engine    yt-dlp 封装/进度/取消    │
│  · 队列管理器限制并发数        │   │ formats   画质预设与格式分类       │
└───────────────────────────────┘   │ errors    错误 → 人话 + 修复动作    │
                                    │ ffmpeg    自检/自动定位/自动安装    │
                                    │ cookies   浏览器 Cookie / 文件导入  │
                                    │ settings  JSON 配置持久化           │
                                    │ history   历史记录                  │
                                    │ diagnostics 环境自检               │
                                    │ updater   内核热更新               │
                                    └──────────────────────────────────┘
```

**关键分界**：`app/core/*` 不 import PySide6，全部逻辑可在 CLI / 测试中直接调用。
`app/ui/*` 只做展示与交互。这样安装/打包、自动化测试、无头验证都不依赖窗口系统。

## 4. 数据流

1. 用户粘贴 URL（或拖入 / 自动读剪贴板）→ `engine.probe()` 在后台线程取回 `info_dict`。
2. `formats.build_options(info)` 生成“最佳 / 4K / 1080P / 720P / 仅音频…”预设，UI 只做展示。
3. 用户点下载 → 生成 `DownloadTask` → 队列管理器按 `max_concurrent` 调度 `DownloadWorker`。
4. `engine.download()` 注入 `progress_hooks` 与自定义 logger，把 yt-dlp 的字节进度实时转成
   Qt Signal（限流 5Hz，避免事件循环过载）。
5. 完成 → 写入 `history.json`；失败 → `errors.translate()` 生成 `Problem`（标题/原因/修复按钮），
   UI 顶部弹出可展开的错误卡片。

## 5. 错误处理与“问题诊所”

`errors.translate()` 用一组按优先级排序的正则规则，把 yt-dlp 原始报错映射为结构化 `Problem`：

```python
Problem(
    code="bot_check",
    title="站点要求验证你是真人",
    detail="YouTube 判定当前网络异常，需要登录 Cookie。",
    fixes=[Fix("use_browser_cookies", "读取浏览器 Cookie 后重试"),
           Fix("open_login_page", "打开浏览器登录")],
)
```

UI 把每个 `Fix` 渲染成按钮，直接跳到设置页 / 重新入队 / 打开登录页。
`diagnostics.run_all()` 独立检查：Python 版本、yt-dlp 版本、ffmpeg、网络、代理、Cookie 库、
磁盘空间、SSL 根证书、输出目录可写性。任何一项失败都给出同一套修复动作，形成闭环。

## 6. 关键设计取舍

| 决策 | 选择 | 理由 |
|---|---|---|
| 内核 | 以 Python 库方式内嵌 yt-dlp | 免装 Python 之外的二进制；异常可捕获、进度可控；打包后单文件运行 |
| ffmpeg | `imageio-ffmpeg` 自带二进制 | 直接消灭“找不到 ffmpeg / 合并失败”这一类问题，Win/mac 都有对应 wheel |
| GUI | PySide6 (Qt 6) | 单一代码库覆盖 Win/mac，原生窗口、成熟打包方案（PyInstaller） |
| 取消 | 在 progress hook 中抛 `DownloadCancelled` | 保留 `.part` 文件，支持断点续传，而不是 kill 进程 |
| Cookie | 浏览器直读（Chrome/Edge/Firefox/Safari/Brave）+ cookies.txt 导入 | 解决 B 站 1080P+、YouTube 人机验证、抖音登录态 |
| 更新 | PyPI wheel 解包到用户目录并前置 sys.path | 打包后也能更新内核，无需重新下载整个安装包 |
| 语言 | 中英双语字典，默认跟随系统 | 中文用户占比高，同时不锁死英文用户 |

## 7. 打包与交付

- `pyproject.toml` + `app/main.py` 入口，`pip install -e .` 可开发运行。
- `scripts/build_macos.sh` → `GlowDL.app` + `.dmg`（PyInstaller + hdiutil）。
- `scripts/build_windows.ps1` → `GlowDL.exe`（PyInstaller one-dir，附带图标）。
- `.github/workflows/build.yml`：macos-latest / windows-latest 双平台矩阵，产出可下载 artifact。
- 应用图标由 `scripts/make_icons.py` 从 SVG 生成 `icns/ico/png`。

## 8. 测试策略

- 单元测试（pytest，无 GUI）：格式预设、文件名清洗、错误映射、设置读写、历史记录、输出模板。
- 集成测试：本地 `http.server` 提供一个由 ffmpeg 生成的 mp4，走真实 yt-dlp generic 提取器下载，
  校验文件落地、进度回调、取消行为。
- GUI 冒烟测试：`QT_QPA_PLATFORM=offscreen` 启动主窗口，检查页面切换、解析失败提示、
  错误卡片渲染，并输出截图供人工审查。
- 打包验证：PyInstaller 产物启动后 3 秒内不崩溃（macOS 本地实测）。

## 9. 风险

- 站点反爬策略随时变化 → 依靠内核更新机制 + 浏览器 Cookie 兜底。
- 打包体积较大（Qt）→ 使用 one-dir + 压缩，约 120–200MB，可接受。
- 知乎原文无法直接获取 → 痛点清单以公开高频问题为准，已在 `docs/问题诊所.md` 逐条对应。
