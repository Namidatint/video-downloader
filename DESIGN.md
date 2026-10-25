---
name: 拾光下载器
description: Windows 10「设置」风格的桌面下载工具
colors:
  accent: "#0078D7"
  surface: "#FFFFFF"
  background: "#F3F3F3"
  navigation: "#E6E6E6"
  border: "#E1E1E1"
  control-border: "#ADADAD"
  text: "#1B1B1B"
  text-secondary: "#5F5F5F"
  success: "#107C10"
  warning: "#9D5D00"
  error: "#C42B1C"
  dark-background: "#202020"
  dark-surface: "#2B2B2B"
  dark-accent: "#4CC2FF"
typography:
  page-title:
    fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei UI, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.2
  section-title:
    fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei UI, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.4
  row-title:
    fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei UI, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  description:
    fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  control: "2px"
  card: "4px"
  bar: "2px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "20px"
  xl: "28px"
  "2xl": "36px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.card}"
    padding: "7px 14px"
    height: "36px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "7px 14px"
    height: "36px"
  navigation-item-active:
    backgroundColor: "#E5F1FB"
    textColor: "{colors.text}"
    rounded: "0px"
    padding: "9px 12px"
    height: "40px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "0px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "7px 10px"
    height: "34px"
  checkbox:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    size: "18px"
  link:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    rounded: "0px"
    padding: "0px"
---

## Overview

拾光下载器的界面参考 **Windows 10「设置」**：一个浅色导航栏加一个安静的内容区，内容以白色卡片
分组，设置项排成「左侧标题与说明、右侧控件」的行。它不要品牌插画、不要仪表盘，也不展示下载引擎
的名称和版本；用户只需要看到任务、状态和可操作的选项。

深色模式遵循 Windows 10 深色主题：`#202020` 背景、`#2B2B2B` 卡片、`#4CC2FF` 强调色。两套主题
共用同一套行、卡片、控件尺寸；切换主题在重启后生效（图标按当前主题绘制）。

## Colors

- **强调色 `#0078D7`**：主按钮、链接、选中项的竖条与焦点边框；只用于可操作或已选中的元素。
- **背景 `#F3F3F3`**：窗口内容区；**导航 `#E6E6E6`**：左侧导航栏，形成清晰的区域分隔。
- **卡片 `#FFFFFF`**：承载分组内容；边框 `#E1E1E1`，控件边框 `#ADADAD`。
- **文字 `#1B1B1B` / `#5F5F5F`**：标题与说明；次要文字对比度 ≥ 4.5:1。
- **状态色**：绿 `#107C10` 完成、琥珀 `#9D5D00` 警告、红 `#C42B1C` 错误；只编码状态。

## Typography

Segoe UI（Windows）/ 苹方（macOS）。页面标题 28px/600；分组标题 14px/600；行标题 15px/600；
正文 13px；说明 12px 灰色。不使用等宽字体、不使用全大写 label、不在标题上方加 kicker。

## Layout

- 左侧导航固定 260px：顶部 `☰ 拾光下载器`，下方五个 40px 导航项；底部留空，不放版本号或技术信息。
- 内容区 36px 外边距；页面标题 + 一句说明；卡片间距 14px，页面可滚动。
- 设置页每行 20px 内边距、12px 纵向留白，行与行之间 1px 分隔线；控件右对齐、宽 110–440px。
- 最小窗口 1080×700：文字省略、控件压缩，内容整体可滚动，不裁切。

## Elevation & Depth

**没有阴影系统。** 层级由背景明度（`#F3F3F3` 内容 / `#FFFFFF` 卡片 / `#E6E6E6` 导航）、
1px 边框和 4px 圆角建立。不使用发光、玻璃或模糊。

## Shapes

- 卡片与按钮：4px 圆角；输入框、复选框、标签：2px 圆角；导航项：直角 + 3px 强调色竖条。
- 状态点/进度条：2–3px 圆角；不使用胶囊形标签。
- 卡片内不嵌套卡片；同一页面卡片等宽、顶对齐。

## Components

- **Navigation item**：40px 高；hover `#DADADA`；选中 `#E5F1FB` 背景 + 左侧 3px `#0078D7` 竖条，
  图标与文字使用强调色。
- **Card**：白色、1px `#E1E1E1` 边框、4px 圆角；分组标题在卡片顶部，行之间用 1px 线分隔。
- **Row**：左侧 15px 标题 + 12px 说明，右侧控件；控件垂直居中、固定宽度。
- **Primary button**：`#0078D7` 底、白字、4px 圆角；hover `#106EBE`；disabled 变灰。
- **Secondary button**：白底、`#ADADAD` 边框；hover `#E9E9E9`。
- **Input / Select**：白底、`#ADADAD` 边框、2px 圆角；focus 为 2px `#0078D7` 边框。
- **Checkbox**：18px 方形、2px 圆角；选中填充强调色并显示白色对勾。
- **Progress**：4px 轨道、`#0078D7` 填充、2px 圆角；失败红、暂停琥珀、完成绿。
- **Link-style button**：无边框、强调色文字（如「全部历史」）。

## Do's and Don'ts

**Do**
- 用 Windows 10 设置的结构：导航栏、页面标题、卡片分组、行式设置。
- 让控件右对齐并保持统一宽度；说明文字保持一行以内。
- 状态用文字 + 颜色双重编码；主操作每页只有一个。
- 内容区滚动，保证 1080×700 下主操作仍可见。

**Don't**
- 不要在界面中出现命令行、组件名称、版本号、站点数量等技术信息。
- 不要使用大圆角、胶囊标签、渐变、阴影、模糊或发光。
- 不要在卡片里嵌套卡片；不要用图标卡片墙代替任务内容。
- 不要在标题上方加小标签（kicker）；不要用表情符号代替图标。
