"""Command line interface shared by standalone and Codex workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import StudyError, collect_local
from .douyin import collect_profile, open_login
from .media import default_model, default_whisper, install_model
from .pipeline import prepare, run_lock
from .report import render


def path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def count(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 50:
        raise argparse.ArgumentTypeError("样本数需在 1～50 之间")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creator-study", description="准备博主研究证据并生成报告")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("prepare", help="采集视频并在本地转写、抽帧")
    collect.add_argument("target", nargs="?", help="抖音号或抖音主页链接")
    collect.add_argument("--expect-handle", help="使用主页链接时核验抖音号，并为以后缓存该映射")
    collect.add_argument("--snapshot", type=path, help="已有账号快照 JSON")
    collect.add_argument("--links", type=path, help="每行一个抖音作品长链接的文本文件")
    collect.add_argument("--videos", type=path, help="本地视频目录")
    collect.add_argument("--out", required=True, type=path, help="可续跑的任务目录")
    collect.add_argument("--browser-profile", type=path, default=Path.home() / ".local/share/douyin-creator-study/browser")
    collect.add_argument("--cookies", type=path, help="可选的 yt-dlp 专用 Netscape Cookies 文件")
    collect.add_argument("--downloader", default="auto", help="auto、douyin-pinned 或兼容 yt-dlp 的可执行文件")
    collect.add_argument("--model", type=path, default=default_model())
    collect.add_argument("--whisper", default=default_whisper(), help="whisper-cli 的路径")
    collect.add_argument("--language", default="zh")
    collect.add_argument("--limit", default=12, type=count)
    collect.add_argument("--strategy", default="stratified", choices=("stratified", "recent", "top"))
    model = commands.add_parser("setup-model", help="下载并校验默认的本地中文转写模型")
    model.add_argument("--model", type=path, default=default_model())
    login = commands.add_parser("browser-login", help="打开专用浏览器，供用户手动登录抖音")
    login.add_argument("--browser-profile", type=path, default=collect.get_default("browser_profile"))
    export = commands.add_parser("render", help="校验证据引用并生成 HTML 和 Markdown")
    export.add_argument("--out", required=True, type=path)
    export.add_argument("--analysis", type=path, help="可选，默认读取任务目录下的 analysis.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup-model":
            install_model(args.model)
            print(args.model)
        elif args.command == "browser-login":
            open_login(args.browser_profile)
        elif args.command == "prepare":
            local = (args.snapshot, args.links, args.videos)
            if bool(args.target) == any(local):
                parser.error("请提供抖音号/主页，或提供 --snapshot / --links / --videos")
            if args.expect_handle is not None and not args.target:
                parser.error("--expect-handle 仅用于主页链接")
            if args.cookies and not args.cookies.is_file():
                raise StudyError("指定的 Cookies 文件不存在")
            request = {
                "target": args.target, "expect_handle": args.expect_handle, "snapshot": str(args.snapshot or ""),
                "links": str(args.links or ""), "videos": str(args.videos or ""),
                "limit": args.limit, "strategy": args.strategy,
            }

            def load_catalog():
                if args.target:
                    return collect_profile(args.target, args.browser_profile, min(80, args.limit * 4), args.expect_handle)
                return collect_local(*local)

            prepare(args.out, request=request, load_catalog=load_catalog, args=args)
        elif args.command == "render":
            with run_lock(args.out):
                render(args.out, args.analysis or args.out / "analysis.json")
            print(args.out / "report.html")
            print(args.out / "report.md")
    except (StudyError, OSError, ValueError) as exc:
        print(f"creator-study: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已停止。可用同一 --out 续跑。", file=sys.stderr)
        return 130
    return 0
