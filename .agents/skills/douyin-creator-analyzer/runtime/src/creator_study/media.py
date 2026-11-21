"""Prepare local, timestamped speech and visual evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageOps

from .catalog import MEDIA_SUFFIXES, StudyError, douyin_id, read_json, write_json

MODEL_NAME = "ggml-small-q5_1.bin"
MODEL_SHA256 = "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb"
DOUYIN_YTDLP = "git+https://github.com/viking1304/yt-dlp@728fe46fbaa97d6f03efcaf9e766d4db63338b8d"
MODEL_URL = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{MODEL_NAME}"


def default_model() -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "douyin-creator-study" / MODEL_NAME


def default_whisper() -> str:
    configured = os.environ.get("CREATOR_STUDY_WHISPER")
    if configured:
        return configured
    installed = default_model().parent / "bin" / "whisper-cli"
    return str(installed) if installed.is_file() else "whisper-cli"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def install_model(path: Path) -> None:
    if path.is_file() and sha256(path) == MODEL_SHA256:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as directory:
        temp = Path(directory) / MODEL_NAME
        try:
            with urlopen(MODEL_URL, timeout=60) as response, temp.open("wb") as output:
                shutil.copyfileobj(response, output)
            if sha256(temp) != MODEL_SHA256:
                raise StudyError("Default Whisper model checksum mismatch")
            temp.replace(path)
        except OSError as exc:
            raise StudyError(f"Unable to download the local Whisper model. Download it from {MODEL_URL} and pass its path with --model.") from exc


def run(command: list[str], timeout: int, label: str, *, diagnostics: bool = False) -> str:
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise StudyError(f"Required executable not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise StudyError(f"{label} timed out") from exc
    if result.returncode:
        raise StudyError(f"{label} failed (exit code {result.returncode})")
    return result.stderr if diagnostics else result.stdout


def probe(path: Path) -> tuple[float, bool]:
    data = json.loads(run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
        "-of", "json", str(path),
    ], 30, "Media validation"))
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, ValueError, TypeError) as exc:
        raise StudyError("Could not read the video duration") from exc
    types = {s["codec_type"] for s in data.get("streams", [])}
    if "video" not in types or not 0 < duration < 86400:
        raise StudyError("The file has no valid video stream or duration")
    return duration, "audio" in types


def download(url: str, destination: Path, cookies: Path | None, downloader: str,
             expected_author: str | None) -> tuple[Path, dict]:
    with TemporaryDirectory(dir=destination.parent) as directory:
        temp = Path(directory)
        options = [
            "--ignore-config", "--no-playlist", "--no-progress", "--no-warnings", "--write-info-json",
            "--socket-timeout", "20", "--retries", "2", "--fragment-retries", "2",
            "-f", "b[ext=mp4][height<=1080]/b[height<=1080]/b",
            "-o", str(temp / "video.%(ext)s"),
        ]
        if cookies:
            cookie_copy = temp / "cookies.txt"
            shutil.copyfile(cookies, cookie_copy)
            cookie_copy.chmod(0o600)
            options += ["--cookies", str(cookie_copy)]
        options += ["--", url]
        if downloader == "douyin-pinned":
            command = ["uvx", "--from", DOUYIN_YTDLP, "yt-dlp"]
        else:
            command = ["yt-dlp" if downloader == "auto" else downloader]
        try:
            run(command + options, 360, "Douyin video download")
        except StudyError:
            if downloader != "auto" or cookies:
                raise
            # The stock extractor currently fails for some public Douyin works.
            for entry in temp.iterdir():
                if entry.is_file():
                    entry.unlink()
            run(["uvx", "--from", DOUYIN_YTDLP, "yt-dlp", *options], 360, "Douyin video download (fallback downloader)")
        files = [p for p in temp.iterdir() if p.suffix.lower() in MEDIA_SUFFIXES]
        if len(files) != 1:
            raise StudyError("The downloader did not produce a video file")
        data = read_json(temp / "video.info.json")
        post_id = douyin_id(url)
        if str(data.get("id")) != post_id:
            raise StudyError("The downloader returned a different post ID")
        if expected_author and data.get("channel_id") != expected_author:
            raise StudyError("Could not verify the post author against the requested creator")
        metadata = {key: data[key] for key in ("id", "title", "timestamp", "like_count", "comment_count", "repost_count", "save_count", "view_count", "channel_id", "duration")
                    if data.get(key) is not None}
        probe(files[0])
        output = destination.with_suffix(files[0].suffix)
        write_json(destination.with_suffix(".json"), metadata)
        files[0].replace(output)
        return output, metadata


def frame_times(duration: float) -> list[float]:
    # Target the opening, a few points across the main body, and the ending.
    end = max(0.0, duration - 0.25)
    proposed = [0, 0.7, 1.5, 3, 5, 8, 15, duration * .25, duration * .5, duration * .75, duration * .9, end]
    selected = []
    for candidate in sorted(min(end, t) for t in proposed):
        if not selected or candidate - selected[-1] >= .32:
            selected.append(round(candidate, 3))
    return selected


def frames(path: Path, directory: Path, duration: float) -> list[dict]:
    records = []
    for index, second in enumerate(frame_times(duration), 1):
        target = directory / f"frame-{index:02}.jpg"
        target.unlink(missing_ok=True)
        run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(second), "-i", str(path),
            "-frames:v", "1", "-vf", "scale='min(1080,iw)':-2", "-q:v", "3", str(target),
        ], 45, "Frame extraction")
        if target.is_file() and target.stat().st_size > 0:
            records.append({"id": f"f{index:02}", "second": second, "file": target.name})
    if not records:
        raise StudyError("No frames were extracted")
    return records


def audio_evidence(path: Path, directory: Path, duration: float) -> dict:
    # Metrics refer to the mixed soundtrack, including possible music or effects.
    log = run([
        "ffmpeg", "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a:0",
        "-af", "ebur128=peak=true,silencedetect=noise=-35dB:d=0.30", "-f", "null", "-",
    ], max(90, int(duration * .75)), "Soundtrack measurement", diagnostics=True)
    summary = log.rsplit("Summary:", 1)[-1]
    loudness = re.search(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?\d+(?:\.\d+)?) dBFS", summary)
    silent = sum(float(seconds) for seconds in re.findall(r"silence_duration:\s+(\d+(?:\.\d+)?)", log))
    windows = [("a01", "开头", 0.0)]
    if duration > 26:
        windows.append(("a02", "正文", max(0.0, duration * .5 - 6)))
    clips = []
    for key, label, start in windows:
        length = min(12.0, duration - start)
        output = directory / f"{key}.mp3"
        run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(path),
            "-map", "0:a:0", "-t", f"{length:.3f}", "-codec:a", "libmp3lame", "-q:a", "5", str(output),
        ], 60, "Audio preview export")
        if output.is_file() and output.stat().st_size > 0:
            clips.append({"id": key, "label": label, "start": round(start, 2), "end": round(start + length, 2),
                          "file": output.name})
    loudness_value = float(loudness[1]) if loudness else None
    return {
        "loudness_lufs": loudness_value if loudness_value is not None and loudness_value > -70 else None,
        "true_peak_dbtp": float(peak[1]) if peak else None,
        "quiet_percent": round(min(duration, silent) * 100 / duration, 1),
        "clips": clips,
    }


def speech_density(segments: list[dict], duration: float) -> int | None:
    if not segments or duration <= 0:
        return None
    units = sum(len(re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9]+", item["text"])) for item in segments)
    return round(units * 60 / duration)


def contact_sheet(directory: Path, records: list[dict]) -> Path:
    columns, tile_width, tile_height = 3, 240, 310
    rows = (len(records) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), "#172630")
    draw = ImageDraw.Draw(sheet)
    for i, record in enumerate(records):
        x, y = i % columns * tile_width, i // columns * tile_height
        with Image.open(directory / record["file"]) as original:
            frame = ImageOps.contain(original.convert("RGB"), (tile_width - 10, tile_height - 28))
        sheet.paste(frame, (x + (tile_width - frame.width) // 2, y + (tile_height - 24 - frame.height) // 2))
        draw.text((x + 10, y + tile_height - 21), f"{record['id']}  {record['second']:g}s", fill="white")
    target = directory / "contact-sheet.jpg"
    sheet.save(target, quality=88)
    return target


def transcript_segments(data: object, duration: float) -> list[dict]:
    if not isinstance(data, list):
        raise StudyError("The transcript must be an array of segments with start, end, and text fields")
    normalized = []
    for entry in data:
        if not isinstance(entry, dict):
            raise StudyError("Each transcript segment must be an object")
        start, end, text = (entry.get(field) for field in ("start", "end", "text"))
        if type(start) not in (int, float) or type(end) not in (int, float):
            raise StudyError("Transcript times must be numbers in seconds")
        if not 0 <= start < end <= duration + 2:
            raise StudyError("Transcript times are outside the media duration or end before they start")
        if isinstance(text, str) and text.strip() and start < duration:
            normalized.append({"start": start, "end": min(end, duration), "text": text.strip()})
    normalized.sort(key=lambda item: (item["start"], item["end"]))
    return [{"id": f"t{index:04}", **item} for index, item in enumerate(normalized, 1)]


def transcribe(path: Path, directory: Path, duration: float, model: Path,
               executable: str, language: str, imported: Path | None) -> list[dict]:
    if imported:
        return transcript_segments(read_json(imported), duration)
    if not model.is_file():
        raise StudyError("Local Whisper model missing. Run creator-analyzer setup-model first.")
    with TemporaryDirectory(dir=directory) as work:
        work = Path(work)
        audio, output = work / "audio.wav", work / "asr"
        run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-map", "0:a:0",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(audio),
        ], 300, "Audio extraction")
        run([
            executable, "--model", str(model), "--file", str(audio), "--language", language,
            "--output-json", "--output-file", str(output), "--no-prints",
        ], max(180, int(duration * 4)), "Local speech transcription")
        raw = read_json(output.with_suffix(".json"))
        response = raw.get("transcription")
        if not isinstance(response, list):
            raise StudyError("Whisper returned an unrecognized transcript format")
        segments = []
        for entry in response:
            offsets = entry["offsets"]
            start, end = offsets["from"] / 1000, offsets["to"] / 1000
            if start < end and start < duration and end <= duration + 2:
                segments.append({"start": start, "end": end, "text": entry["text"]})
        normalized = transcript_segments(segments, duration)
        write_json(directory / "whisper.json", raw)
        return normalized
