---
name: GlowDL 拾光下载器
description: 反向接触印相 / 资产清单式的桌面下载工具
colors:
  ink: "#F7F4ED"
  ground: "#0B0A09"
  surface: "#131110"
  surface-raised: "#191614"
  surface-hover: "#221F1B"
  rail: "#0D0C0B"
  rule: "#2E2A25"
  rule-strong: "#4B453C"
  text-secondary: "#D8D2C6"
  text-muted: "#A9A29A"
  text-dim: "#817A70"
  signal-success: "#4CD98C"
  signal-warn: "#F2B24A"
  signal-danger: "#FF6E60"
typography:
  page-title:
    fontFamily: "PingFang SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1.2
  media-title:
    fontFamily: "PingFang SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "PingFang SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  meta:
    fontFamily: "PingFang SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
  mono:
    fontFamily: "monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  none: "0px"
spacing:
  "2xs": "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  "2xl": "30px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
    height: "36px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
    height: "36px"
  nav-item-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    padding: "9px 12px"
    height: "40px"
  input:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 10px"
    height: "36px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "18px"
  tag:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.none}"
    padding: "1px 7px"
---

## Overview

GlowDL 的界面世界是**反向接触印相 / 资产清单**：把下载任务当成一卷需要归档的素材，
用暖黑底、纸白墨、1px 细线、零圆角和等宽数字来记录它们。它不是一张漂亮的营销页，
而是一台在深夜工作台上持续运转的仪器：所有区域对齐，所有状态有名字，所有数字可比较。

这套视觉从视频素材管理的工作方式里借来四样东西——字体、配色、密度、一个标志性动作：
**时间码/清单读数**。导航、控件与布局保持桌面工具的熟悉形态，不被"行业外观"绑架。

## Colors

- **Ground `#0B0A09`**：窗口底色，比面板更深，形成前后层次但不使用阴影。
- **Surface `#131110`**：卡片/面板；**Surface-raised `#191614`**：输入框与进度轨道。
- **Ink `#F7F4ED`**：正文与主操作；正文对比度约 16:1。
- **Rule `#2E2A25` / Rule-strong `#4B453C`**：1px 分隔线与输入边框；后者用于需要被看见的边界。
- **Signal**：绿 `#4CD98C` 完成、琥珀 `#F2B24A` 进行中/暂停、红 `#FF6E60` 失败。
  颜色只表达状态，不做装饰；除状态色外全场只有一个"纸白"强调色。

浅色主题是同一世界的相纸版本：ground `#F0ECE3`、surface `#FAF7F0`、墨色 `#141210`。
两套主题的图标在启动时按当前调色板绘制，运行时切换需要重启应用。

## Typography

系统中文无衬线（PingFang SC / Microsoft YaHei UI / Segoe UI）承担全部文案；
`26px/700` 页面标题，`17px/600` 媒体标题，`13px/400` 正文，`12px` 元数据。
等宽字体只用于**测量值**：内核版本、时间码、体积、速度、进度数字、format id。
不使用装饰性字体、不使用渐变文字、不使用全大写 kicker。

## Layout

- 左侧 226px 固定导轨：品牌标记、5 个方形导航、内核版本、自检。
- 主列 30px 外边距、16px 纵向节奏；首页可滚动，底部永远有一条"资产清单"状态带。
- 卡片之间用 1px 线与间距分隔，不嵌套卡片；设置页按任务分组，组内表单行左对齐。
- 最小窗口 1080×700：媒体信息单行省略，质量选择压缩为一行，内容不足时滚动而不是挤压。

## Elevation & Depth

**没有海拔系统。** 不使用阴影、模糊、玻璃或发光。层级只由三种手段建立：
底色明度差（ground → surface → raised）、1px 边框、间距。这让窗口在低配机器上重绘成本极低。

## Shapes

**零圆角。** 所有卡片、按钮、输入框、标签、复选框、进度条、滚动条都是直角。
状态点是小方块（6–8px），不是圆点。品牌图标是一枚方形接触印相格。
分隔线一律 1px；不使用彩色左边框、不使用硬偏移投影。

## Components

- **Primary button**：纸白底、黑字、1px 同色边框；hover 纯白；disabled 变面板灰。用于"解析/开始下载/重新自检"。
- **Ghost button**：透明底、1px rule-strong 边框、次级文字色；用于"全部格式/浏览/打开"。
- **Quiet button**：无边框，仅文字与 hover 底色；用于"查看原始信息/全部历史"。
- **Navigation item**：40px 高；选中态是整块纸白底 + 黑字 + 黑色图标，不使用圆角药丸。
- **Input / select**：raised 底 + 1px rule-strong；focus 时边框变 ink；无外发光。
- **Card**：surface 底 + 1px rule 边框；标题 13–15px；元数据 12px；内容左对齐。
- **Tag / pill**：透明底 + 1px 状态色边框 + 同色文字；不填充、不圆角。
- **Progress**：6px 高的实心轨道；进行中纸白、完成绿、失败红、暂停琥珀；没有渐变、没有动画。
- **Timecode row**：等宽数字右对齐，单位与数值之间用 ` · ` 分隔（`43.6% · 122.1 MB / 279.4 MB · 5.9 MB/s · 剩余 0:26`）。

## Do's and Don'ts

**Do**
- 用对齐、留白与 1px 线建立层级，而不是阴影和圆角。
- 让状态自己说话：颜色 + 文字 + 位置三重编码。
- 数字用等宽、右对齐、带单位；长标题单行省略，完整文本进 tooltip。
- 在最小窗口下仍保证主操作可见；内容放不下就滚动。

**Don't**
- 不要圆角、渐变、模糊、发光、透明度动画。
- 不要把颜色当装饰；不要用颜色作为唯一状态信号。
- 不要嵌套卡片，不要用图标+标题+说明的三联卡当页面结构。
- 不要在标题上方加 kicker/eyebrow；标题自己承担层级。
- 不要用 emoji 或 Unicode 字符代替图标系统。
