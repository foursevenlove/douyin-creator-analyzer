"""Normalize source lists and deterministically select a bounded sample."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

MEDIA_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
HANDLE = re.compile(r"[a-zA-Z0-9_.-]{1,64}")
VIDEO_ID = re.compile(r"\d{8,25}")


METRIC_LABELS = {
    "likes": "点赞", "comments": "评论", "favorites": "收藏", "shares": "分享", "views": "播放",
}
METRIC_KEYS = {
    "likes": "digg_count", "comments": "comment_count", "favorites": "collect_count",
    "shares": "share_count", "views": "play_count",
}


class StudyError(Exception):
    """A recoverable error with a message suitable for the operator."""


def douyin_id(url: str) -> str | None:
    parsed = urlparse(url)
    match = re.fullmatch(r"/video/(\d{8,25})/?", parsed.path)
    if parsed.scheme == "https" and parsed.hostname in {"www.douyin.com", "douyin.com"} and match:
        return match[1]
    return None


def post_url(post_id: str) -> str | None:
    return f"https://www.douyin.com/video/{post_id}" if VIDEO_ID.fullmatch(post_id) else None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, data: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def local_path(base: Path, value: str | None) -> Path | None:
    return (base / value).resolve() if value else None


def as_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def public_metrics(item: dict, statistics: dict | None = None) -> dict:
    statistics = statistics or {}
    return {name: as_count(item.get(name, statistics.get(key)))
            for name, key in METRIC_KEYS.items()}


def duration_seconds(value: object, milliseconds: object = None) -> float | None:
    if type(value) in (int, float) and 0 < value < 86400:
        return float(value)
    if type(milliseconds) in (int, float) and 0 < milliseconds < 86400000:
        return milliseconds / 1000
    return None


def inventory_item(post: dict) -> dict:
    return {key: post.get(key) for key in ("id", "title", "url", "published_at", "listed_duration", *METRIC_KEYS)}


def published(value: object) -> int | None:
    if type(value) in (int, float) and 0 < value < 5_000_000_000:
        return int(value)
    if isinstance(value, str):
        try:
            date = datetime.fromisoformat(value)
            return int(date.timestamp()) if date.tzinfo else None
        except (ValueError, OverflowError, OSError):
            return None
    return None


def video_index(directory: Path | None) -> dict[str, Path]:
    if directory is None:
        return {}
    if not directory.is_dir():
        raise StudyError(f"找不到视频目录 {directory}")
    files = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES:
            match = re.search(r"(?:^|[-_])(\d{8,25})$", path.stem)
            key = match[1] if match else f"local-{len(files) + 1:03d}"
            if key in files:
                raise StudyError(f"视频目录包含重复作品 ID {key}")
            files[key] = path.resolve()
    return files


def collect_local(snapshot: Path | None, links: Path | None, videos: Path | None) -> dict:
    files = video_index(videos)
    source = read_json(snapshot) if snapshot else {}
    if not isinstance(source, dict):
        raise StudyError("作品快照必须是 JSON 对象")
    items = source.get("posts", [])
    if not isinstance(items, list):
        raise StudyError("作品快照的 posts 必须是列表")
    account = source.get("account") or {}
    if not isinstance(account, dict):
        raise StudyError("作品快照的 account 必须是对象")
    normalized = {}
    for item in items:
        if not isinstance(item, dict):
            raise StudyError("作品快照的每一项必须是对象")
        post_id = str(item.get("id") or item.get("aweme_id") or "")
        if not (VIDEO_ID.fullmatch(post_id) or re.fullmatch(r"local-\d+", post_id)):
            raise StudyError(f"无效作品 ID {post_id!r}")
        if post_id in normalized:
            raise StudyError(f"作品快照包含重复 ID {post_id}")
        stats = item.get("statistics") or {}
        media = local_path(snapshot.parent, item.get("media")) or files.get(post_id)
        if item.get("aweme_type") in (68, 150) and not media:
            continue
        transcript = local_path(snapshot.parent, item.get("transcript"))
        normalized[post_id] = {
            "id": post_id,
            "url": post_url(post_id),
            "title": str(item.get("title") or item.get("desc") or ""),
            "published_at": published(item.get("published_at") or item.get("create_time") or item.get("create_time_iso")),
            **public_metrics(item, stats),
            "listed_duration": duration_seconds(item.get("listed_duration") or item.get("duration"), item.get("duration_ms")),
            "media": str(media) if media else None,
            "transcript": str(transcript) if transcript else None,
        }
    if links:
        for line in links.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            post_id = douyin_id(line)
            if post_id is None:
                raise StudyError(f"请在链接清单每行放一个抖音长视频链接。无法识别 {line!r}")
            normalized.setdefault(post_id, {"id": post_id, "url": post_url(post_id)})
    for post_id, path in files.items():
        if not snapshot and not links:
            normalized[post_id] = {"id": post_id, "url": post_url(post_id), "title": path.stem}
        if post_id in normalized:
            normalized[post_id]["media"] = str(path)
    if not normalized:
        raise StudyError("没有可分析的作品")
    return {
        "origin": "public_index" if source.get("origin") == "public_index" else "import",
        "account": account,
        "collected_at": source.get("collected_at"),
        "posts": list(normalized.values()),
    }


def select_posts(posts: list[dict], limit: int, strategy: str) -> tuple[list[dict], str]:
    if strategy == "top":
        ranked = [p for p in posts if p.get("likes") is not None]
        if not ranked:
            raise StudyError("高赞排序需要至少一条带精确点赞数的作品")
        ranked.sort(key=lambda p: (-p["likes"], -(p.get("published_at") or 0), p["id"]))
        return ranked[:limit], "snapshot_likes"
    dated = [p for p in posts if p.get("published_at") and p.get("likes") is not None]
    if strategy == "stratified" and dated:
        latest = max(p["published_at"] for p in dated)
        window = [p for p in dated if p["published_at"] >= latest - 90 * 86400]
        if limit >= 3 and len(window) >= max(limit, 6):
            ranked = sorted(window, key=lambda p: (-p["likes"], p["id"]))
            groups = [ranked[len(ranked) * i // 3:len(ranked) * (i + 1) // 3] for i in range(3)]
            counts = [min(len(group), limit // 3) for group in groups]
            for i, group in enumerate(groups):
                extra = min(len(group) - counts[i], limit - sum(counts))
                counts[i] += extra
            selected = []
            for group, count, name in zip(groups, counts, ("high", "middle", "low")):
                for index in range(count):
                    position = (2 * index + 1) * len(group) // (2 * count)
                    selected.append({**group[position], "stratum": name})
            return selected, "window_likes_90_days"
    if any(p.get("published_at") for p in posts):
        ranked = sorted(posts, key=lambda p: (-(p.get("published_at") or 0), p["id"]))
        return ranked[:limit], "recent_known_dates"
    return posts[:limit], "source_order"
