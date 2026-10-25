"""Headless CLI: diagnostics, probing and downloading for power users / CI."""

from __future__ import annotations

import argparse
import sys

from app.core import formats as fmt
from app.core import paths
from app.core.settings import Settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glowdl",
        description="视频下载器 · by NamidaTint · 命令行模式",
    )
    parser.add_argument("url", nargs="?", help="视频链接")
    parser.add_argument("--cli", action="store_true", help="无界面下载")
    parser.add_argument("--diagnose", action="store_true", help="打印环境自检报告")
    parser.add_argument("--version", action="store_true", help="打印版本信息")
    parser.add_argument("-q", "--quality", default="best",
                        help="画质预设：best/2160/1440/1080/720/480/audio-mp3/audio-m4a")
    parser.add_argument("-f", "--format", dest="custom_format", default="",
                        help="自定义 yt-dlp format 表达式")
    parser.add_argument("-o", "--output", default="", help="输出目录")
    parser.add_argument("--playlist", action="store_true", help="下载整个播放列表")
    parser.add_argument("--info", action="store_true", help="只解析，不下载")
    parser.add_argument("--cookie-browser", default="", help="从浏览器读取 Cookie：chrome/edge/firefox/safari")
    parser.add_argument("--cookies", default="", help="cookies.txt 路径")
    parser.add_argument("--proxy", default="", help="代理地址，例如 http://127.0.0.1:7890")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from app import __version__

        print(f"视频下载器 {__version__}")
        print("by NamidaTint")
        print(f"Python {sys.version.split()[0]}")
        return 0

    settings = Settings.load()
    if args.output:
        settings.download_dir = args.output
    if args.cookie_browser:
        settings.cookies_browser = args.cookie_browser
    if args.cookies:
        settings.cookies_file = args.cookies
    if args.proxy:
        settings.proxy = args.proxy

    if args.diagnose:
        from app.core import diagnostics

        checks = diagnostics.run_all(settings)
        width = max(len(c.title) for c in checks) + 2
        print("视频下载器 环境自检")
        print("=" * 60)
        for check in checks:
            mark = {"pass": "✓", "warn": "!", "fail": "✗"}.get(check.status, "?")
            print(f"[{mark}] {check.title:<{width}} {check.detail}")
        print("=" * 60)
        print(f"总体：{diagnostics.overall_status(checks)}")
        return 0 if diagnostics.overall_status(checks) != "fail" else 1

    if not args.url:
        parser.print_help()
        return 2

    if args.info:
        from app.core import engine

        try:
            info = engine.probe(args.url, settings, playlist=args.playlist)
        except engine.DownloadError as exc:
            print(f"解析失败：{exc.problem.title}\n{exc.problem.detail}", file=sys.stderr)
            return 1
        summary = fmt.summarize(info)
        print(f"标题：{summary['title']}")
        print(f"站点：{summary['extractor']}  时长：{paths.human_duration(summary['duration'])}")
        for row in fmt.classify_formats(info)[:25]:
            print(f"  {row.format_id:>12}  {row.label_for('zh')}")
        return 0

    from app.core import engine

    last_percent = -1

    def on_progress(data: dict) -> None:
        nonlocal last_percent
        if data.get("status") != "downloading":
            return
        percent = int((data.get("downloaded_bytes") or 0)
                      / max(1, (data.get("total_bytes") or data.get("total_bytes_estimate") or 1))
                      * 100)
        if percent != last_percent:
            last_percent = percent
            speed = paths.human_speed(data.get("speed"))
            print(f"\r下载中 {percent:3d}%  {speed}", end="", flush=True)

    try:
        result = engine.download(
            args.url, settings,
            preset_key=args.quality,
            custom_format=args.custom_format,
            progress=on_progress,
            playlist=args.playlist,
        )
    except engine.DownloadCancelled:
        print("\n已取消")
        return 130
    except engine.DownloadError as exc:
        print(f"\n下载失败：{exc.problem.title}", file=sys.stderr)
        print(exc.problem.detail, file=sys.stderr)
        if exc.raw:
            print(f"原始信息：{exc.raw}", file=sys.stderr)
        return 1
    print()
    for path in result.filepaths:
        print(f"完成：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
