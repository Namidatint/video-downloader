# Surface brief — 拾光下载器主窗口

Mode: Operate. Platform: desktop Qt (Windows/macOS), Windows 10 Settings reference. Code-led.

## Direction contract

THESIS: 一个 Windows 10「设置」式的下载工具：左导航 + 白卡片 + 行式设置，界面只呈现任务与操作，不展示技术实现。

OWN-WORLD: 浅灰导航 `#E6E6E6`、内容背景 `#F3F3F3`、白色卡片 `#FFFFFF`、1px `#E1E1E1` 边框、4px 圆角、强调蓝 `#0078D7`；深色模式 `#202020` / `#2B2B2B` / `#4CC2FF`。无阴影、无渐变、无装饰插画。

STORY: 用户打开应用，粘贴链接、选择画质、下载；需要时在设置里改下载位置、网络与登录状态；出问题时进入「诊断」查看原因并修复。

FIRST VIEWPORT: 左侧 260px 导航（☰ + 拾光下载器，五项：下载/队列/历史/诊断/设置）；内容区 28px 页面标题「下载」与一句说明；URL 输入卡片；已解析的媒体卡片；最近完成卡片。主操作蓝色「开始下载」在媒体卡片右下。

FORM: Windows 10「设置」的页面结构：导航栏、页面标题、卡片分组、行式设置项（左侧标题与说明，右侧控件）。这是用户本轮明确指定的参考，覆盖此前的视觉方向。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
