"""Summaries derived from source metadata and inspected sample files."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import mean, median

from .catalog import METRIC_LABELS, post_url

SHANGHAI = timezone(timedelta(hours=8))
BINS = [("< 30 秒", 30), ("30–59 秒", 60), ("1–2 分钟", 180), ("3–5 分钟", 360),
        ("6–9 分钟", 600), ("≥ 10 分钟", float("inf"))]


def date(value: int | None) -> str:
    return datetime.fromtimestamp(value, SHANGHAI).strftime("%Y-%m-%d") if value else "—"


def timecode(value: float | None) -> str:
    if value is None:
        return "—"
    minute, second = divmod(round(value), 60)
    return f"{minute}:{second:02d}"


def fmt(value) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def aggregate(manifest: dict) -> dict:
    inventory = manifest.get("inventory") or manifest["posts"]
    inspected = {post["id"]: post for post in manifest["posts"]}
    rows = []
    for post in inventory:
        sample = inspected.get(post["id"], {})
        duration = sample.get("duration") or post.get("listed_duration")
        row = {
            "id": post["id"], "title": sample.get("title") or post.get("title") or post["id"],
            "url": post_url(post["id"]) if post.get("url") else None,
            "duration": duration, "date": date(post.get("published_at") or sample.get("published_at")),
            "sample": bool(sample), "stratum": sample.get("stratum"),
        }
        for key in METRIC_LABELS:
            row[key] = post.get(key) if post.get(key) is not None else sample.get(key)
        if row["views"] == 0 and any(row[key] for key in ("likes", "comments", "favorites", "shares")):
            row["views"] = None
        rows.append(row)
    rows.sort(key=lambda row: (row["date"] != "—", row["date"], row["id"]), reverse=True)
    durations = [row["duration"] for row in rows if row["duration"] is not None]
    counts = Counter(next(label for label, maximum in BINS if value < maximum) for value in durations)
    scale = max(counts.values(), default=1)
    histogram = [(label, counts[label], round(counts[label] * 100 / scale)) for label, _ in BINS]
    dates = [row["date"] for row in rows if row["date"] != "—"]
    releases = Counter(value[:7] for value in dates)
    peak_month = max(releases.values(), default=1)
    publication_months = [(month, count, round(count * 100 / peak_month))
                          for month, count in sorted(releases.items())]
    numbers = []
    for key, label in METRIC_LABELS.items():
        present = [row[key] for row in rows if row[key] is not None]
        numbers.append({
            "key": key, "label": label, "count": len(present),
            "total": sum(present) if present else None, "median": round(median(present)) if present else None,
            "mean": round(mean(present), 1) if present else None, "max": max(present, default=None),
        })
    return {
        "rows": rows, "date_count": len(dates), "date_start": min(dates, default="—"),
        "date_end": max(dates, default="—"), "duration_count": len(durations),
        "duration_median": median(durations) if durations else None,
        "duration_mean": mean(durations) if durations else None,
        "histogram": histogram, "publication_months": publication_months, "metrics": numbers,
    }
