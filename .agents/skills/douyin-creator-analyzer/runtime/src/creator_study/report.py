"""Validate evidence references, then render Markdown and an offline dashboard."""

from __future__ import annotations

import re
from collections import Counter
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from .catalog import StudyError, post_url, read_json
from .douyin import profile_url
from .report_data import aggregate, date, fmt, timecode

CATEGORIES = {
    "topics": "选题", "script": "标题与文案", "visuals": "画面与分镜",
    "audio": "声音与节奏", "duration": "时长", "style": "视频风格", "workflow": "拍摄与制作",
    "review": "发布与复盘", "other": "其他观察",
}
SAMPLING = {
    "window_likes_90_days": "以快照最新日期向前 90 天，按点赞分层取样",
    "snapshot_likes": "按快照内可见点赞数取高赞作品",
    "recent_known_dates": "按已知发布时间取近期样本", "source_order": "按来源返回顺序取样",
}
SOURCES = {
    "douyin_browser": "抖音网页采集", "public_index": "公开索引作品样本",
    "import": "导入作品快照", "example": "虚构示例 · 演示数据",
}


def required_text(record: dict, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StudyError(f"analysis.json is missing the text field {key}")
    return value.strip()


def records(data: dict, key: str) -> list[dict]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise StudyError(f"analysis.json field {key} must be an array of objects")
    return value


def sound_summary(post: dict) -> str:
    audio = post.get("audio") or {}
    measurements = (
        ("混音响度", audio.get("loudness_lufs"), " LUFS"),
        ("真峰值", audio.get("true_peak_dbtp"), " dBTP"),
        ("低电平占比", audio.get("quiet_percent"), "%"),
        ("转写文本密度", post.get("speech_units_per_minute"), " 字词单位/分钟"),
    )
    return " · ".join(f"{label} {fmt(value)}{unit}" for label, value, unit in measurements if value is not None)


def evidence_index(run_dir: Path, posts: list[dict]) -> dict:
    index = {}
    for post in posts:
        post_id = post["id"]
        folder = Path("evidence") / post_id
        for frame in post.get("frames", []):
            path = folder / frame["file"]
            if (run_dir / path).is_file():
                index[(post_id, frame["id"])] = {
                    "label": f"{timecode(frame['second'])} · {frame['id']} · {post_id}",
                    "url": quote(path.as_posix()), "kind": "image", "snippet": "",
                    "time": timecode(frame["second"]),
                    "caption": f"{(post.get('title') or post_id).partition(' #')[0]} · {timecode(frame['second'])}",
                }
        for clip in (post.get("audio") or {}).get("clips", []):
            if (run_dir / folder / clip["file"]).is_file():
                index[(post_id, clip["id"])] = {
                    "label": f"{timecode(clip['start'])}–{timecode(clip['end'])} · 听音 · {post_id}",
                    "url": f"#audio-{post_id}-{clip['id']}",
                    "file_url": quote((folder / clip["file"]).as_posix()), "kind": "audio", "snippet": "",
                }
        sound = sound_summary(post)
        if sound:
            index[(post_id, "audio-metrics")] = {
                "label": f"音轨与转写数据 · {post_id}", "url": f"#sound-{post_id}",
                "file_url": "manifest.json", "kind": "metrics", "snippet": sound,
            }
        if post.get("transcript"):
            path = run_dir / post["transcript"]
            if not path.is_file():
                raise StudyError(f"Transcript file not found for post {post_id}")
            for segment in read_json(path):
                index[(post_id, segment["id"])] = {
                    "label": f"{timecode(segment['start'])}–{timecode(segment['end'])} · 转写 · {post_id}",
                    "url": quote(post["transcript"]), "kind": "text", "snippet": segment["text"],
                    "start": segment["start"], "end": segment["end"],
                }
    return index


def evidence_refs(record: dict, index: dict, field: str = "evidence", owner: str | None = None) -> list[tuple]:
    value = record.get(field, [])
    if not isinstance(value, list) or (field == "evidence" and not value):
        raise StudyError(f"Each entry must include valid {field} references")
    refs = []
    for ref in value:
        if not isinstance(ref, str) or ref.count("/") != 1:
            raise StudyError(f"Expected an evidence reference in post-id/evidence-id format, got {ref!r}")
        key = tuple(ref.split("/"))
        if key not in index:
            raise StudyError(f"Unknown evidence reference: {ref}")
        if owner and key[0] != owner:
            raise StudyError(f"The analysis for post {owner} must cite evidence from that post")
        if key not in refs:
            refs.append(key)
    return refs


def availability(post: dict) -> str:
    if post["media_status"] != "ready":
        return "媒体未获取"
    speech = {
        "ready": "有转写", "no_audio": "无音轨", "no_speech": "未识别到口播", "failed": "转写失败",
    }.get(post.get("speech_status"), "无转写")
    return f"{len(post.get('frames', []))} 张画面 · {speech}"


def video_view(run_dir: Path, post: dict, observation: dict | None, index: dict) -> dict:
    post_id = post["id"]
    title = post.get("title") or post_id
    frames = [{"src": index[(post_id, frame["id"])]["url"], "time": timecode(frame["second"]),
               "id": frame["id"], "second": frame["second"]}
              for frame in post.get("frames", []) if (post_id, frame["id"]) in index]
    gallery = frames
    if len(frames) > 4:
        duration = post.get("duration") or frames[-1]["second"]
        picks = {min(range(len(frames)), key=lambda i: abs(frames[i]["second"] - duration * point))
                 for point in (0, 0.25, 0.5, 0.75)}
        gallery = [frames[i] for i in sorted(picks)]
    sheet = post.get("contact_sheet")
    audio = post.get("audio")
    if audio:
        audio = {**audio, "clips": [{**clip, "url": index[(post_id, clip["id"])]["file_url"]}
                                    for clip in audio.get("clips", []) if (post_id, clip["id"]) in index]}
    meta = [text for text in (date(post.get("published_at")), timecode(post.get("duration"))) if text != "—"]
    if post.get("likes") is not None:
        meta.append(f"{fmt(post['likes'])} 点赞")
    if post.get("stratum"):
        meta.append({"high": "高赞组", "middle": "中位组", "low": "低赞组"}.get(post["stratum"], ""))
    notes = []
    if observation:
        for key, label in (("observation", "视频结构与表达"), ("script", "文案与开头"), ("visual", "画面与剪辑"), ("voice", "声音与口播")):
            if observation.get(key):
                notes.append((label, required_text(observation, key)))
    return {
        "id": post_id, "title": title, "topic": observation.get("topic") if observation else None,
        "url": post_url(post_id) if post.get("url") else None,
        "state": availability(post), "meta": " · ".join(meta), "duration": post.get("duration"),
        "cover": frames[0]["src"] if frames else None, "gallery": gallery,
        "notes": notes, "audio": audio, "sound": sound_summary(post),
        "contact_sheet": quote(sheet) if sheet and (run_dir / sheet).is_file() else None,
        "refs": observation.get("refs", []) if observation else [],
        "transcript": quote(post["transcript"]) if post.get("transcript") else None,
        "errors": "；".join(post.get("errors", {}).values()),
    }


def creator_takeaways(analysis: dict, index: dict) -> list[dict]:
    if "takeaways" not in analysis:
        return []
    takeaways = []
    for item in records(analysis, "takeaways"):
        category = required_text(item, "category")
        if category not in CATEGORIES:
            raise StudyError(f"Unknown takeaway category: {category}")
        takeaways.append({
            "category": CATEGORIES[category],
            **{key: required_text(item, key) for key in ("title", "observed", "how", "example", "check")},
            "refs": [index[key] for key in evidence_refs(item, index)],
        })
    return takeaways


def creator_studies(analysis: dict, index: dict) -> list[dict]:
    if "studies" not in analysis:
        return []
    studies = []
    for item in records(analysis, "studies"):
        refs = [index[key] for key in evidence_refs(item, index)]
        studies.append({
            "title": required_text(item, "title"),
            "sections": [(label, required_text(item, key).split("\n\n")) for key, label in (
                ("observed", "原作拆解"), ("analysis", "怎样理解这个选择"), ("lesson", "学习收获"),
            )],
            "refs": refs,
            "pictures": [ref for ref in refs if ref["kind"] == "image"][:2],
        })
    return studies


def comparison_views(run_dir: Path, spec: dict, rows: dict, index: dict) -> list[dict]:
    if "comparisons" not in spec:
        return []
    proof_path = run_dir / "comparison-evidence.json"
    if proof_path.is_file():
        supplemental = read_json(proof_path)
        if not isinstance(supplemental, dict):
            raise StudyError("comparison-evidence.json must be an object")
        extra = evidence_index(run_dir, records(supplemental, "posts"))
        if extra.keys() & index.keys():
            raise StudyError("Supplemental comparison evidence reuses an existing ID")
        index = {**index, **extra}

    comparisons = []
    linked = set()
    for page in records(spec, "comparisons"):
        entries = records(page, "works")
        if len(entries) != 2 or entries[0].get("post_id") == entries[1].get("post_id"):
            raise StudyError("Each comparison requires two distinct posts")
        works = []
        for item in entries:
            post_id = required_text(item, "post_id")
            if post_id not in rows:
                raise StudyError(f"Comparison post {post_id} is missing from the catalog")
            shots = {}
            for name in ("opening", "visual"):
                shot = item.get(name)
                if not isinstance(shot, dict):
                    raise StudyError(f"Comparison post {post_id} requires a frame for {name}")
                frame_id = required_text(shot, "frame_id")
                frame = index.get((post_id, frame_id))
                if not frame or frame["kind"] != "image":
                    raise StudyError(f"Comparison frame {frame_id} not found for post {post_id}")
                shots[name] = {"frame": frame, "note": required_text(shot, "note")}
            segments = [index[key] for key in evidence_refs(item["opening"], index, owner=post_id)]
            if any(segment["kind"] != "text" for segment in segments):
                raise StudyError("The opening quote must cite its own post transcript")
            start = min(segment["start"] for segment in segments)
            end = max(segment["end"] for segment in segments)
            anchor = f"video-{post_id}" if post_id not in linked else None
            linked.add(post_id)
            row = rows[post_id]
            row["sample"] = True
            works.append({
                **row, **shots, "anchor": anchor, "angle": required_text(item, "angle"),
                "quote": required_text(item["opening"], "quote"),
                "quote_time": f"{timecode(start)}–{timecode(end)}", "transcript_url": segments[0]["url"],
            })
        comparisons.append({
            **{key: required_text(page, key) for key in ("title", "difference", "action", "visual_heading")},
            "works": works,
        })
    if comparisons:
        for row in rows.values():
            row["sample"] = row["id"] in linked
    return comparisons


def script_breakdown(entry: dict, index: dict, duration: float | None) -> dict | None:
    if "script_breakdown" not in entry:
        return None
    spec = entry["script_breakdown"]
    if not isinstance(spec, dict) or not isinstance(spec.get("opening"), dict):
        raise StudyError("A script breakdown requires script_breakdown and opening objects")
    post_id = entry["post_id"]

    def excerpt(item: dict) -> dict:
        refs = [index[key] for key in evidence_refs(item, index, owner=post_id)]
        segments = [ref for ref in refs if ref["kind"] == "text"]
        if not segments:
            raise StudyError(f"Script quotes must cite transcript segments from post {post_id}")
        start = min(ref["start"] for ref in segments)
        end = max(ref["end"] for ref in segments)
        return {"quote": required_text(item, "quote"), "analysis": required_text(item, "analysis"),
                "time": f"{timecode(start)}–{timecode(end)}", "url": segments[0]["url"]}

    beats = []
    for item in records(spec, "beats"):
        segment_id = required_text(item, "at")
        anchor = index.get((post_id, segment_id))
        if not anchor or anchor["kind"] != "text":
            raise StudyError(f"Script section timestamp {segment_id} not found for post {post_id}")
        start = anchor["start"]
        if beats and start <= beats[-1]["start"]:
            raise StudyError(f"Script sections for post {post_id} must be in chronological order")
        refs = [index[key] for key in evidence_refs(item, index, owner=post_id)]
        frame = next((ref for ref in refs if ref["kind"] == "image"), None)
        frame_note = required_text(item, "frame_note") if frame and "frame_note" in item else ""
        beats.append({"title": required_text(item, "title"), "detail": required_text(item, "detail"),
                      "start": start, "url": anchor["url"], "frame": frame, "frame_note": frame_note})
    highlights = [{"title": required_text(item, "title"), **excerpt(item)} for item in records(spec, "highlights")]
    if not beats or not highlights:
        raise StudyError(f"The script breakdown for post {post_id} requires body sections and highlights")
    ends = [beat["start"] for beat in beats[1:]] + [duration]
    for beat, end in zip(beats, ends):
        beat["time"] = timecode(beat["start"])
        if end is not None:
            beat["time"] += f"–{timecode(end)}"
    return {"opening": excerpt(spec["opening"]), "throughline": required_text(spec, "throughline"),
            "beats": beats, "highlights": highlights}


def synthesis_view(spec: dict, index: dict) -> list[dict]:
    modules = []
    for item in records(spec, "synthesis"):
        if "points" not in item:
            modules.extend(creator_studies({"studies": [item]}, index))
            continue
        points = [{**{key: required_text(point, key) for key in ("title", "principle", "example")},
                   "refs": [index[key] for key in evidence_refs(point, index)]} for point in records(item, "points")]
        if not points:
            raise StudyError("Each learning module requires at least one evidence-backed point")
        modules.append({"title": required_text(item, "title"), "points": points,
                        "summary": required_text(item, "summary")})
    return modules


def editorial_view(run_dir: Path, spec: dict, data: dict, observations: dict, index: dict) -> dict:
    if not isinstance(spec, dict):
        raise StudyError("analysis.json field editorial must be an object")
    rows = {row["id"]: row for row in data["rows"]}
    membership = {}
    categories = []
    for group in records(spec, "taxonomy"):
        title = required_text(group, "title")
        ids = group.get("post_ids")
        if not isinstance(ids, list) or not ids:
            raise StudyError(f"Category {title} requires at least one post ID")
        for post_id in ids:
            if not isinstance(post_id, str) or post_id not in rows or post_id in membership:
                raise StudyError(f"Category {title} contains an invalid or duplicate post ID {post_id!r}")
            membership[post_id] = title
        example = max((rows[post_id] for post_id in ids),
                      key=lambda row: row["likes"] if row["likes"] is not None else -1)
        categories.append({"title": title, "detail": required_text(group, "detail"), "example": example,
                           "count": len(ids), "share": round(len(ids) * 100 / len(rows), 1)})
    if set(membership) != set(rows):
        raise StudyError("Content categories must cover every catalog post")
    for row in rows.values():
        row["category"] = membership[row["id"]]
        row["sample"] = row["id"] in observations
    categories.sort(key=lambda item: -item["count"])
    likes = [row for row in rows.values() if row["likes"] is not None]
    likes.sort(key=lambda row: (-row["likes"], row["id"]))
    ranks = {row["id"]: rank for rank, row in enumerate(likes, 1)}
    reviewed = {}
    for item in records(spec, "readings"):
        post_id = required_text(item, "post_id")
        if post_id not in rows or post_id in reviewed:
            raise StudyError(f"Sample readings contain an invalid or duplicate post ID {post_id}")
        reviewed[post_id] = {
            "title": rows[post_id]["title"], "category": membership[post_id],
            "rank": ranks.get(post_id), "url": rows[post_id]["url"],
            **{key: required_text(item, key) for key in ("opening", "visual", "note")},
            "refs": [index[key] for key in evidence_refs(item, index, owner=post_id)],
        }
    if set(reviewed) != {key[0] for key in index}:
        raise StudyError("Sample readings must cover every post with citable evidence")
    synthesis = synthesis_view(spec, index)
    if not synthesis:
        raise StudyError("An editorial report requires learning modules across the sample")
    return {
        "taxonomy": categories, "readings": list(reviewed.values()), "synthesis": synthesis,
        "comparisons": comparison_views(run_dir, spec, rows, index),
        "has_comparison_evidence": bool(spec.get("comparisons")) and (run_dir / "comparison-evidence.json").is_file(),
        "case_ranks": ranks, "opening_counts": Counter(v["opening"] for v in reviewed.values()).most_common(),
        "visual_counts": Counter(v["visual"] for v in reviewed.values()).most_common(),
        "details": {post_id: [(label, required_text(entry, key).split("\n\n")) for key, label in (
            ("topic", "选题"), ("script", "文案"), ("visual", "画面"),
        )] for post_id, entry in observations.items()},
        **{key: required_text(spec, key) for key in ("style", "selection", "conclusion", "sources")},
    }


def render(run_dir: Path, analysis_path: Path) -> None:
    manifest = read_json(run_dir / "manifest.json")
    posts = manifest["posts"]
    if [post["id"] for post in posts] != manifest["selected_ids"]:
        raise StudyError("Evidence preparation is incomplete. Resume prepare first.")
    analysis = read_json(analysis_path)
    if not isinstance(analysis, dict) or analysis.get("schema_version") != 1:
        raise StudyError("analysis.json requires schema_version = 1")
    index = evidence_index(run_dir, posts)
    available = {key[0] for key in index}
    is_editorial = "editorial" in analysis
    if is_editorial:
        for ref in index.values():
            if ref["url"].startswith("#"):
                ref["url"] = ref["file_url"]
    observations = {}
    for entry in records(analysis, "videos"):
        post_id = required_text(entry, "post_id")
        if post_id not in available or post_id in observations:
            raise StudyError(f"Video analysis contains a duplicate post or a post without evidence: {post_id}")
        required_text(entry, "topic")
        required_text(entry, "observation")
        refs = evidence_refs(entry, index, owner=post_id)
        observations[post_id] = {**entry, "refs": [index[key] for key in refs]}
    if not observations or (not is_editorial and set(observations) != available):
        raise StudyError("Provide a videos entry for each post with evidence")
    findings = []
    finding_records = records(analysis, "findings") if "findings" in analysis else []
    for item in finding_records:
        refs = evidence_refs(item, index)
        pictures = [index[key] for key in refs if index[key]["kind"] == "image"][:3]
        findings.append({
            "title": required_text(item, "title"), "detail": required_text(item, "detail"),
            "category": CATEGORIES.get(item.get("category"), "其他观察"),
            "count": len({key[0] for key in refs}), "refs": [index[key] for key in refs], "pictures": pictures,
            "counter": [index[key] for key in evidence_refs(item, index, "counter_evidence")],
        })
    studies = creator_studies(analysis, index)
    takeaways = creator_takeaways(analysis, index)
    idea_records = records(analysis, "ideas") if "ideas" in analysis else []
    ideas = [{"title": required_text(item, "title"),
              "details": [(label, required_text(item, key)) for label, key in
                          [("给谁看", "audience"), ("切入点", "angle"), ("开头怎么拍", "opener"), ("怎么验证", "test")]],
              "refs": [index[key] for key in evidence_refs(item, index)]} for item in idea_records]
    if not findings and not is_editorial:
        raise StudyError("The report requires at least one evidence-backed finding")
    if len(ideas) > 3:
        raise StudyError("The report accepts at most three topic ideas")
    if not (studies or takeaways or ideas or is_editorial):
        raise StudyError("The report requires at least one study, takeaway, or topic idea")

    data = aggregate(manifest)
    editorial = editorial_view(run_dir, analysis["editorial"], data, observations, index) if is_editorial else None
    coverage = f"{sum(bool(p.get('frames')) for p in posts)} 条有画面 · {sum(bool(p.get('transcript')) for p in posts)} 条有转写"
    scope = f"{SAMPLING.get(manifest['sampling'], manifest['sampling'])}。已取得 {len(data['rows'])} 条作品记录，选样 {len(posts)}/{manifest['requested_limit']} 条。"
    if data["date_count"]:
        scope += f" 有发布日期的作品覆盖 {data['date_start']} 至 {data['date_end']}。"
    videos = [video_view(run_dir, post, observations.get(post["id"]), index) for post in posts]
    if editorial:
        videos = [video for video in videos if video["id"] in observations]
        for video in videos:
            post_id = video["id"]
            video.update(rank=editorial["case_ranks"].get(post_id), detail=editorial["details"][post_id],
                         lead=observations[post_id]["observation"])
            video["breakdown"] = script_breakdown(observations[post_id], index, video["duration"])
    hero_video = next((item for item in videos if item["cover"]), None)
    hero = {"src": hero_video["cover"], "title": hero_video["title"], "time": "开场"} if hero_video else None
    account = manifest.get("account") or {}
    context = dict(title=required_text(analysis, "title"), summary=required_text(analysis, "summary"),
                   source_label=SOURCES.get(manifest["origin"], "导入资料"), account=account,
                   profile_url=profile_url(account.get("profile_url") or ""), data=data,
                   snapshot_date=(manifest.get("collected_at") or "")[:10], coverage=coverage, scope=scope,
                   catalog_count=manifest["catalog_count"], sample_count=len(observations), likes=data["metrics"][0],
                   studies=studies, takeaways=takeaways, findings=findings, ideas=ideas, videos=videos, hero=hero,
                   editorial=editorial, evidence_count=len(available),
                   has_catalog=(run_dir / "catalog.json").is_file(),
                   limitations=required_text(analysis, "limitations"))
    environment = Environment(loader=PackageLoader("creator_study", "templates"),
                              autoescape=select_autoescape(("html",)))
    environment.filters.update(number=fmt, clock=timecode)
    document = environment.get_template("editorial.html" if editorial else "report.html").render(**context)
    text_report = editorial_markdown(context) if editorial else markdown(context)
    with TemporaryDirectory(dir=run_dir) as workspace:
        for name, content in (("report.md", text_report), ("report.html", document)):
            path = Path(workspace) / name
            path.write_text(content, encoding="utf-8")
            path.replace(run_dir / name)


def md_text(value: str) -> str:
    safe = escape(value, quote=False).replace("|", "&#124;").replace("\n", " ")
    return re.sub(r"([\\\[\]*_`!])", r"\\\1", safe)


def md_refs(items: list) -> str:
    return " · ".join(f"[{md_text(item['label'])}]({item.get('file_url', item['url'])})" for item in items)


def markdown(c: dict) -> str:
    source = " · ".join(value for value in (c["source_label"], c["snapshot_date"]) if value)
    lines = [f"# {md_text(c['title'])}", "", md_text(source), "", md_text(c["summary"]), ""]
    if c["studies"]:
        lines += ["## 创作精读", ""]
    for item in c["studies"]:
        lines += [f"### {md_text(item['title'])}", ""]
        for label, paragraphs in item["sections"]:
            lines += [f"#### {label}", ""]
            for paragraph in paragraphs:
                lines += [md_text(paragraph), ""]
        lines += [md_refs(item["refs"]), ""]
    if c["takeaways"]:
        lines += ["## 给创作者的启发", ""]
    for item in c["takeaways"]:
        lines += [f"### {md_text(item['title'])}", "", md_text(item["category"]), "", md_text(item["how"]), "",
                  f"- **用你的素材试** {md_text(item['example'])}",
                  f"- **怎么验证** {md_text(item['check'])}",
                  f"- **原作怎么做** {md_text(item['observed'])}", "", md_refs(item["refs"]), ""]
    lines += ["## 作品数据", "", md_text(c["coverage"]), md_text(c["scope"]), "",
              "| 指标 | 总量 | 中位数 | 已覆盖 |", "| --- | ---: | ---: | ---: |"]
    for item in c["data"]["metrics"]:
        lines.append(f"| {item['label']} | {fmt(item['total'])} | {fmt(item['median'])} | {item['count']} |")
    lines += ["", "## 风格与内容规律", ""]
    for item in c["findings"]:
        lines += [f"### {md_text(item['title'])}", "", md_text(item["detail"]), "", md_refs(item["refs"]), ""]
        if item["counter"]:
            lines += ["例外 · " + md_refs(item["counter"]), ""]
    lines += ["## 逐条拆解", ""]
    for item in c["videos"]:
        title = md_text(item["title"])
        if item["url"]:
            title = f"[{title}]({item['url']})"
        lines += [f"### {title}", "", md_text(item["meta"] + " · " + item["state"]), ""]
        if item["topic"]:
            lines += [md_text(item["topic"]), ""]
        if item["notes"]:
            lines += [f"- **{label}** {md_text(detail)}" for label, detail in item["notes"]]
            lines += ["", md_refs(item["refs"]), ""]
        if item["sound"]:
            lines += [md_text(item["sound"]), ""]
        if item["contact_sheet"]:
            lines += [f"[查看关键帧总览]({item['contact_sheet']})", ""]
        if item["audio"] and item["audio"]["clips"]:
            lines += [" · ".join(f"[{clip['label']}音频]({clip['url']})" for clip in item["audio"]["clips"]), ""]
        if item["errors"]:
            lines += [md_text(item["errors"]), ""]
    if c["ideas"]:
        lines += ["## 可拍选题", ""]
    for item in c["ideas"]:
        lines += [f"### {md_text(item['title'])}", "", *[f"- **{label}** {md_text(detail)}" for label, detail in item["details"]],
                  "", md_refs(item["refs"]), ""]
    lines += ["## 采样与证据说明", "", md_text(c["limitations"]), ""]
    return "\n".join(lines)


def editorial_markdown(c: dict) -> str:
    feature = c["editorial"]
    data = c["data"]
    lines = [f"# {md_text(c['title'])}的抖音内容研究", "", md_text(c["summary"]), "", "## 整体数据与内容分析", "",
             md_text(c["scope"]), "",
             f"视频时长均值 {timecode(data['duration_mean'])}，中位数 {timecode(data['duration_median'])}。",
             "", "| 单条互动指标 | 平均 | 中位 | 最大值 | 总量 | 覆盖 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for item in data["metrics"]:
        lines.append(f"| {item['label']} | {fmt(item['mean'])} | {fmt(item['median'])} | "
                     f"{fmt(item['max'])} | {fmt(item['total'])} | {item['count']} / {len(data['rows'])} |")
    lines += ["", "| 内容类别 | 条数 | 占比 | 解读 |", "| --- | ---: | ---: | --- |"]
    for category in feature["taxonomy"]:
        lines.append(f"| {md_text(category['title'])} | {category['count']} | {category['share']}% | {md_text(category['detail'])} |")
    lines += ["", md_text(feature["style"]), "", "## 代表性爆款深度拆解", "", md_text(feature["selection"]), ""]
    for page in feature["comparisons"]:
        lines += [f"### {md_text(page['title'])}", "", md_text(page["difference"]), ""]
        for work in page["works"]:
            title = md_text(work["title"])
            if work["url"]:
                title = f"[{title}]({work['url']})"
            lines += [f"#### {title}", "", f"{work['date']} · {fmt(work['likes'])} 点赞", "", md_text(work["angle"]), "",
                      f'> “{md_text(work["quote"])}”', "", f"[开场转写 {work['quote_time']}]({work['transcript_url']})", ""]
            for shot in (work["opening"], work["visual"]):
                frame = shot["frame"]
                lines += [f"[{frame['time']} 原图]({frame['url']}) · {md_text(shot['note'])}", ""]
        lines += [f"**值得一试** {md_text(page['action'])}", ""]
    standalone = [] if feature["comparisons"] else c["videos"]
    for video in standalone:
        title = md_text(video["title"])
        if video["url"]:
            title = f"[{title}]({video['url']})"
        lines += [f"### {title}", "", md_text(video["meta"]), "", md_text(video["lead"]), ""]
        if script := video["breakdown"]:
            opening = script["opening"]
            lines += ["#### 开头说了什么，为什么这样说", "", f'> “{md_text(opening["quote"])}”', "",
                      f"[开头转写 {opening['time']}]({opening['url']})", "", md_text(opening["analysis"]), "",
                      "#### 正文怎么推进", "", md_text(script["throughline"]), ""]
            for beat in script["beats"]:
                lines += [f"- **[{beat['time']}]({beat['url']}) {md_text(beat['title'])}** {md_text(beat['detail'])}"]
                if frame := beat["frame"]:
                    lines[-1] += f" [关键帧 {frame['time']}]({frame['url']})"
                    if beat["frame_note"]:
                        lines[-1] += f" · {md_text(beat['frame_note'])}"
            lines += ["", "#### 文案亮点", ""]
            for item in script["highlights"]:
                lines += [f"**{md_text(item['title'])}** · [{item['time']}]({item['url']})", "",
                          f'> “{md_text(item["quote"])}”', "", md_text(item["analysis"]), ""]
            if video["transcript"]:
                lines += [f"[完整转写]({video['transcript']})", ""]
            continue
        for label, paragraphs in video["detail"]:
            lines += [f"#### {label}", ""]
            for paragraph in paragraphs:
                lines += [md_text(paragraph), ""]
        lines += [md_refs(video["refs"]), ""]
    lines += ["## 经验总结与模仿学习", ""]
    for study in feature["synthesis"]:
        lines += [f"### {md_text(study['title'])}", ""]
        if points := study.get("points"):
            lines += [f"{i}. {md_text(point['title'])}" for i, point in enumerate(points, 1)] + [""]
            for i, point in enumerate(points, 1):
                lines += [f"#### {i}. {md_text(point['title'])}", "", md_text(point["principle"]), "",
                          md_text(point["example"]), "", md_refs(point["refs"]), ""]
            lines += [f"**小结** {md_text(study['summary'])}", ""]
            continue
        for label, paragraphs in study["sections"]:
            lines += [f"#### {label}", ""]
            for paragraph in paragraphs:
                lines += [md_text(paragraph), ""]
        lines += [md_refs(study["refs"]), ""]
    lines += ["## 总结与证据来源", "", md_text(feature["conclusion"]), "", md_text(feature["sources"]), "",
              md_text(c["limitations"]), "", "[作品数据与证据清单](manifest.json)", ""]
    if feature["has_comparison_evidence"]:
        lines += ["[对照补充证据](comparison-evidence.json)", ""]
    lines += ["### 样本阅读记录", "", "| 作品 | 开场 | 主画面 | 观察 |", "| --- | --- | --- | --- |"]
    for reading in feature["readings"]:
        title = md_text(reading["title"])
        if reading["url"]:
            title = f"[{title}]({reading['url']})"
        lines.append(f"| {title} | {md_text(reading['opening'])} | {md_text(reading['visual'])} | "
                     f"{md_text(reading['note'])} · {md_refs(reading['refs'])} |")
    return "\n".join(lines) + "\n"
