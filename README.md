# 视频下载器 · by NamidaTint

Windows / macOS 桌面视频下载器。界面参考 Windows 10「设置」，粘贴链接或分享口令即可解析、选画质并下载。

<p align="center">
  <img src="app/resources/icon.png" width="112" alt="视频下载器图标">
</p>

![下载页](docs/screenshots/01-home.png)

**GitHub**：https://github.com/Namidatint/video-downloader

## 下载

| 平台 | 文件 | 说明 |
|---|---|---|
| Windows | [VideoDownloader-1.0.5-Windows-x64.zip](https://github.com/Namidatint/video-downloader/releases/download/v1.0.5/VideoDownloader-1.0.5-Windows-x64.zip) | 解压后运行 `视频下载器.exe`，免安装 |
| macOS | [VideoDownloader-1.0.5-macOS.dmg](https://github.com/Namidatint/video-downloader/releases/download/v1.0.5/VideoDownloader-1.0.5-macOS.dmg) | 打开后拖入「应用程序」 |

Windows 首次运行若提示 SmartScreen：更多信息 → 仍要运行。应用未做商业代码签名。

## 功能

- 基于 yt-dlp：支持 B 站、YouTube、抖音、小红书等站点，画质预设与「全部格式」选择。
- 抖音原生解析：直接粘贴整段分享口令，自动提取链接；本机 Edge/Chrome 无头解析，读取无水印播放源，不经过第三方接口。
- 抖音实况照片：导出手机可导入的实况包——iPhone 用 `.livp` / HEIC+MOV，Android 用单张 Motion Photo JPEG；Apple 动态片段自动裁到 2.9 秒。
- 并发队列 50–200（默认 50），实时进度、暂停、重试、断点续传。
- 内置 ffmpeg 与封面/元数据写入；自动读取浏览器 Cookie 或导入 cookies.txt。
- 网络模式：跟随系统 / 直连 / 自定义代理；限速、重试、分片并发。
- 诊断页：12 项环境检查 + 常见错误说明与一键修复。
- Windows 10 风格浅色/深色界面，切换主题后重启生效。

## 使用

1. 复制视频链接，或抖音的整段分享文字，例如：
   `5.38 复制打开抖音，看看【…】… https://v.douyin.com/xxxx/ …`
2. 粘贴到下载页，点「解析」；抖音视频通常 5–10 秒，成功后缓存。
3. 选择画质（或「全部格式」），点「开始下载」。
4. 抖音图文作品会显示「图文 · N 张」，ZIP 内是原始图片。
5. 实况照片显示「实况 · N 张 + 动态」，ZIP 内含：
   - `LivePhoto.livp`：iPhone 优先用这个单文件，AirDrop 后用「文件」打开并存储到照片；
   - `iPhone/`：JPG / HEIC + MOV 备用，可一起导入「照片」；
   - `Android/MV_*.jpg`：单文件动态照片，Google 相册 / 三星相册识别。

## 常见问题

| 现象 | 处理 |
|---|---|
| 网页能打开、软件连接被拒 | 设置 → 网络模式改为「直连」；代理软件关闭后尤其常见 |
| 证书校验失败 | 应用已内置根证书；诊断页运行「重新自检」 |
| 抖音提示安装浏览器 | 需要本机安装 Microsoft Edge 或 Google Chrome |
| 抖音分享文字无法解析 | 1.0.5 已支持整段口令；仍失败请更新到最新版 |
| 下载的 B 站视频有 UP 主水印 | 水印由 UP 主上传时烧录，下载器不会添加，也无法无损去除；可换源或裁剪 |
| macOS 提示无法验证开发者 | 右键应用 → 打开；或系统设置 → 隐私与安全性 → 仍要打开 |

## 构建

要求 Python 3.10+；Windows 10+ / macOS 11+。

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt pyinstaller
python scripts/make_icons.py
python -m PyInstaller --noconfirm --clean scripts/glowdl.spec

# macOS
codesign --deep --force --sign - "dist/视频下载器.app"
hdiutil create -volname 视频下载器 -srcfolder "dist/视频下载器.app" \
  -ov -format UDZO "dist/视频下载器-1.0.5-macOS.dmg"

# Windows（PowerShell）
Compress-Archive -Path "dist\视频下载器\*" `
  -DestinationPath "dist\视频下载器-1.0.5-Windows-x64.zip"
```

GitHub Actions 会在 Windows / macOS 上自动构建，见 `.github/workflows/build.yml`。

## 测试

```bash
python -m pytest -q        # 77 passed
```

## 技术栈与许可

- 解析内核：[yt-dlp](https://github.com/yt-dlp/yt-dlp)（Unlicense）
- 界面：PySide6 / Qt 6（LGPL）
- 音视频合并：ffmpeg（LGPL/GPL，随应用分发）
- 本项目代码：仅用于下载你有权保存的内容，请遵守目标站点条款与当地法律。

设计规范见 [DESIGN.md](DESIGN.md)。
