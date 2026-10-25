# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

Desktop application (Windows 10/11, macOS 11+), built with PySide6/Qt 6. The word
"adaptive" here means one codebase adapting its window chrome per desktop OS; this is not
a mobile app and the iOS/Android surface guidance does not apply.

## Users

中文用户，主要是三类人：想收藏/离线保存视频的内容爱好者；需要素材的剪辑与二创作者；
把课程、访谈、播客存到本地反复看的学生与从业者。他们手里只有浏览器和链接，没有
Python 环境，也不想记 yt-dlp 的参数；多数人在家里的 Windows 笔记本或 MacBook 上操作，
网络可能直连，也可能挂着代理。

## Product Purpose

把 yt-dlp 的能力收进一个双击即用的桌面窗口：粘贴链接、选画质、下载到本地。成功意味着
用户不需要知道 ffmpeg、format id、cookies.txt 是什么，也能把 B 站 1080P+/4K、YouTube、
抖音、小红书的内容稳定存下来；失败时能看懂原因并一键修复。

## Positioning

同类工具大多只是给 yt-dlp 套一个"链接输入框 + 下载按钮"。GlowDL 的差异是**闭环**：
内置 ffmpeg、浏览器 Cookie 直读、24 条报错翻译、10 项环境自检、内核热更新——把
"装环境、配参数、查报错、等更新"四件运维工作放进同一个窗口。这个闭环是相邻工具
很难诚实照抄的部分。

## Operating Context

- 主流程只有四步：粘贴/拖入链接 → 解析 → 选画质 → 入队下载；批量时用播放列表。
- 下载是长任务：用户会切到别的窗口，回来时关心进度、速度、剩余时间、是否失败。
- 失败是常态而不是例外（登录态、地区、代理、链接失效、内核过期），所以错误必须可读、可修。
- 用户会在 1080P 与仅音频之间反复切换；会在设置里配置一次目录/代理/Cookie 之后长期不再打开设置。
- 界面语言以简体中文为主；英文只作为错误提示的备用语言。

## Capabilities and Constraints

已确认能力：1800+ 站点解析（yt-dlp）、画质预设与自定义 format、并发队列、暂停/续传、
字幕/封面/元数据后处理、浏览器 Cookie 与 cookies.txt/JSON、代理/限速/重试、下载历史、
问题诊所（10 项自检 + 24 条报错百科）、应用内内核热更新、深浅主题、Windows/macOS 打包。

硬约束：不破解 DRM、不绕过付费墙；不内置账号；不依赖外网服务端；单机运行。
技术约束：Qt Widgets（非 WebView），界面需在低配机器上保持低渲染压力；无 Node 运行时依赖。
未决事实：暂无。文中所有产品事实均来自本仓库 README、代码与用户本次明确指令。

## Brand Commitments

- 名称：GlowDL / 拾光下载器；中文优先，英文作为辅助。
- 用户指定参考 **Windows 10「设置」**：浅色导航栏 + 内容区、白色卡片、行式设置项、
  蓝色强调色、4px 小圆角、无阴影的平面视觉。默认浅色，可切深色模式。
- 界面不出现下载引擎名称、版本号、命令行、站点数量等技术信息；只保留任务、状态与操作。
- 并发设置范围 50–200，默认 50。
- 不做游戏化、不做营销话术；工具应当像系统设置应用，而不是一个广告页。

## Evidence on Hand

- 可运行应用：`app/`（PySide6），macOS 打包产物 `dist/GlowDL.app`。
- 设计基线截图：`docs/screenshots/01-home.png` 至 `06-home-dark.png`。
- 测试：`tests/`（58 项），构建脚本 `scripts/`。
- 真实站点数据不可在构建环境复现（外网受限），界面中的示例数据只用于截图与演示。

## Product Principles

1. **任务先于装饰**：任何视觉元素不能遮挡进度、状态、错误与下一个动作。
2. **状态必须可读**：颜色只用来表达状态与层级，不用来制造气氛。
3. **一次配置，长期使用**：设置页密度可以高，主流程必须极简。
4. **失败可修复**：错误不是终点，是修复入口。
5. **低配也流畅**：纯色、细线、无模糊、无阴影；滚动与进度更新不掉帧。

## Accessibility & Inclusion

- 中文界面，正文字号不小于 13px；关键数字与状态用更高对比度。
- 对比度目标：正文文本 ≥ 7:1，次要文本 ≥ 4.5:1，边框 ≥ 3:1。
- 所有交互控件有键盘焦点态；颜色不作为唯一状态信号（配合文字/图标）。
