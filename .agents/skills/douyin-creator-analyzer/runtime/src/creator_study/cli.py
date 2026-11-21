"""Command line interface for standalone and agent workflows."""

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
        raise argparse.ArgumentTypeError("Sample size must be between 1 and 50")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare creator research evidence and generate reports")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("prepare", help="Collect videos, transcribe speech locally, and extract frames")
    collect.add_argument("target", nargs="?", help="Douyin handle or profile URL")
    collect.add_argument("--expect-handle", help="Verify and cache the handle when using a profile URL")
    collect.add_argument("--snapshot", type=path, help="Existing account snapshot JSON")
    collect.add_argument("--links", type=path, help="Text file with one canonical Douyin post URL per line")
    collect.add_argument("--videos", type=path, help="Local video directory")
    collect.add_argument("--out", required=True, type=path, help="Run directory for outputs and resuming")
    collect.add_argument("--browser-profile", type=path, default=Path.home() / ".local/share/douyin-creator-study/browser")
    collect.add_argument("--cookies", type=path, help="Optional Netscape cookies file for yt-dlp")
    collect.add_argument("--downloader", default="auto", help="auto, douyin-pinned, or a yt-dlp-compatible executable")
    collect.add_argument("--model", type=path, default=default_model())
    collect.add_argument("--whisper", default=default_whisper(), help="Path to whisper-cli")
    collect.add_argument("--language", default="zh")
    collect.add_argument("--limit", default=12, type=count)
    collect.add_argument("--strategy", default="stratified", choices=("stratified", "recent", "top"))
    model = commands.add_parser("setup-model", help="Download and verify the default local speech model")
    model.add_argument("--model", type=path, default=default_model())
    login = commands.add_parser("browser-login", help="Open the dedicated browser for Douyin login")
    login.add_argument("--browser-profile", type=path, default=collect.get_default("browser_profile"))
    export = commands.add_parser("render", help="Validate evidence references and generate HTML and Markdown")
    export.add_argument("--out", required=True, type=path)
    export.add_argument("--analysis", type=path, help="Optional path to analysis.json, which defaults to the run directory")
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
                parser.error("Provide either a Douyin handle or profile URL, or input via --snapshot, --links, or --videos")
            if args.expect_handle is not None and not args.target:
                parser.error("--expect-handle requires a profile URL")
            if args.cookies and not args.cookies.is_file():
                raise StudyError("The specified cookies file does not exist")
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
        print(f"{parser.prog}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped. Resume with the same --out directory.", file=sys.stderr)
        return 130
    return 0
