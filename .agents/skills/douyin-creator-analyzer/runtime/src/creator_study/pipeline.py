"""Create a resumable run directory for Codex to analyze."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from . import media
from .catalog import MEDIA_SUFFIXES, StudyError, as_count, inventory_item, published, read_json, select_posts, write_json


@contextmanager
def run_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(directory / ".lock.sqlite", timeout=0)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise StudyError(f"Another process is using the run directory {directory}") from exc
        yield


def get_video(post: dict, directory: Path, cookies: Path | None, downloader: str,
              expected_author: str | None) -> tuple[Path, dict]:
    if post.get("media"):
        candidate = Path(post["media"])
        if not candidate.is_file():
            raise StudyError(f"Local video not found: {candidate.name}")
        return candidate, {}
    metadata_path = directory / "source.json"
    if metadata_path.is_file():
        metadata = read_json(metadata_path)
        matches = metadata.get("id") == post["id"] and (
            not expected_author or metadata.get("channel_id") == expected_author
        )
        if matches:
            for candidate in directory.glob("source.*"):
                if candidate.suffix.lower() in MEDIA_SUFFIXES and candidate.is_file():
                    return candidate, metadata
    if not post.get("url"):
        raise StudyError("The post is missing a video path or URL")
    return media.download(post["url"], directory / "source", cookies, downloader, expected_author)


def prepare_post(post: dict, run_dir: Path, model: Path, executable: str, language: str,
                 cookies: Path | None, downloader: str, expected_author: str | None) -> dict:
    directory = run_dir / "evidence" / post["id"]
    directory.mkdir(parents=True, exist_ok=True)
    state_path = directory / "state.json"
    prior = read_json(state_path) if state_path.is_file() else {}
    state = {"id": post["id"], "media_status": "failed", "errors": {}}
    try:
        path, metadata = get_video(post, directory, cookies, downloader, expected_author)
        duration, has_audio = media.probe(path)
        signature = media.sha256(path)
    except (StudyError, OSError, ValueError, KeyError, TypeError) as exc:
        state["errors"]["media"] = str(exc)
        write_json(state_path, state)
        return state

    state.update(media_status="ready", duration=duration, media_sha256=signature)
    if not post.get("title") and isinstance(metadata.get("title"), str):
        state["title"] = metadata["title"]
    if not post.get("published_at") and published(metadata.get("timestamp")):
        state["published_at"] = published(metadata["timestamp"])
    for key, source in (("likes", "like_count"), ("comments", "comment_count"),
                        ("favorites", "save_count"), ("shares", "repost_count"), ("views", "view_count")):
        count = as_count(metadata.get(source))
        if post.get(key) is None and count is not None:
            state[key] = count
    if metadata.get("channel_id"):
        state["author_id"] = metadata["channel_id"]
    state["media"] = str(path.relative_to(run_dir)) if path.is_relative_to(run_dir) else str(path)
    same_media = prior.get("media_sha256") == signature
    frame_records = prior.get("frames", []) if same_media else []
    if frame_records and all((directory / item["file"]).is_file() for item in frame_records):
        state["frames"] = frame_records
    else:
        try:
            state["frames"] = media.frames(path, directory, duration)
        except (StudyError, OSError) as exc:
            state["errors"]["frames"] = str(exc)
            state["frames"] = []

    if state.get("frames"):
        try:
            sheet = directory / "contact-sheet.jpg"
            if not (same_media and frame_records == state["frames"] and sheet.is_file()):
                sheet = media.contact_sheet(directory, state["frames"])
            state["contact_sheet"] = str(sheet.relative_to(run_dir))
        except OSError as exc:
            state["errors"]["contact_sheet"] = str(exc)

    if has_audio:
        try:
            cached_audio = prior.get("audio") if same_media else None
            if cached_audio and all((directory / clip["file"]).is_file() for clip in cached_audio["clips"]):
                state["audio"] = cached_audio
            else:
                state["audio"] = media.audio_evidence(path, directory, duration)
        except (StudyError, OSError) as exc:
            state["errors"]["audio"] = str(exc)

    imported = Path(post["transcript"]) if post.get("transcript") else None
    transcript_path = directory / "transcript.json"
    state["speech_status"] = "no_audio"
    if imported or has_audio:
        try:
            transcript_signature = (
                ["import", media.sha256(imported)] if imported else
                [str(model), model.stat().st_mtime_ns if model.is_file() else None, language, executable]
            )
            if not (same_media and prior.get("transcript_signature") == transcript_signature
                    and transcript_path.is_file() and prior.get("speech_status") in {"ready", "no_speech"}):
                normalized = media.transcribe(path, directory, duration, model, executable, language, imported)
                write_json(transcript_path, normalized)
            else:
                normalized = read_json(transcript_path)
            state["speech_status"] = "ready" if normalized else "no_speech"
            state["transcript_signature"] = transcript_signature
            if normalized:
                state["speech_units_per_minute"] = media.speech_density(normalized, duration)
                state["transcript"] = str(transcript_path.relative_to(run_dir))
        except (StudyError, OSError, ValueError, KeyError, TypeError) as exc:
            state["errors"]["speech"] = str(exc)
            state["speech_status"] = "failed"

    write_json(state_path, state)
    return state


def prepare(run_dir: Path, *, request: dict, load_catalog, args) -> dict:
    with run_lock(run_dir):
        snapshot_path = run_dir / "catalog.json"
        if snapshot_path.exists():
            snapshot = read_json(snapshot_path)
            if snapshot.get("request") != request:
                raise StudyError("This run used different sources or sampling settings. Choose a new --out directory.")
        else:
            result = load_catalog()
            selected, sampling = select_posts(result["posts"], args.limit, args.strategy)
            account = result.get("account") or {}
            snapshot = {
                "schema_version": 1,
                "request": request,
                "origin": result["origin"],
                "account": account,
                "collected_at": result["collected_at"],
                "catalog_count": len(result["posts"]),
                "sampling": sampling,
                "inventory": [inventory_item(post) for post in result["posts"]],
                "selected": selected,
            }
            write_json(snapshot_path, snapshot)
        manifest = {key: value for key, value in snapshot.items() if key not in {"request", "selected"}}
        # Older task catalogs still render and resume without a full inventory.
        manifest.setdefault("inventory", [inventory_item(post) for post in snapshot["selected"]])
        manifest["requested_limit"] = args.limit
        manifest["selected_ids"] = [post["id"] for post in snapshot["selected"]]
        manifest["posts"] = []
        profile = snapshot["account"].get("profile_url")
        expected_author = profile.rstrip("/").rsplit("/", 1)[-1] if profile else None
        for i, post in enumerate(snapshot["selected"], 1):
            print(f"[{i}/{len(snapshot['selected'])}] {post['id']}", flush=True)
            state = prepare_post(post, run_dir, args.model, args.whisper, args.language,
                                 args.cookies, args.downloader, expected_author)
            public = {k: v for k, v in post.items() if k not in {"transcript", "media"}}
            manifest["posts"].append({**public, **state})
            write_json(run_dir / "manifest.json", manifest)
        ready = sum(bool(p.get("frames") or p.get("transcript")) for p in manifest["posts"])
        print(f"Evidence ready for {ready}/{len(manifest['posts'])} posts. Manifest: {run_dir / 'manifest.json'}")
        if not ready:
            raise StudyError("No sampled post has usable frames or a transcript. See manifest.json for details.")
        return manifest
