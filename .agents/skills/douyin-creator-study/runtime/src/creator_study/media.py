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
                raise StudyError("默认 Whisper 模型校验失败")
            temp.replace(path)
        except OSError as exc:
            raise StudyError(f"下载本地 Whisper 模型失败。可从 {MODEL_URL} 下载后使用 --model 指定路径。") from exc


def run(command: list[str], timeout: int, label: str, *, diagnostics: bool = False) -> str:
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise StudyError(f"缺少依赖 {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise StudyError(f"{label}超时") from exc
    if result.returncode:
        raise StudyError(f"{label}失败（退出码 {result.returncode}）")
    return result.stderr if diagnostics else result.stdout


def probe(path: Path) -> tuple[float, bool]:
    data = json.loads(run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
        "-of", "json", str(path),
    ], 30, "媒体校验"))
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, ValueError, TypeError) as exc:
        raise StudyError("无法读取视频时长") from exc
    types = {s["codec_type"] for s in data.get("streams", [])}
    if "video" not in types or not 0 < duration < 86400:
        raise StudyError("文件没有有效的视频流或时长")
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
            run(command + options, 360, "抖音视频下载")
        except StudyError:
            if downloader != "auto" or cookies:
                raise
            # The stock extractor currently fails for some public Douyin works.
            for entry in temp.iterdir():
                if entry.is_file():
                    entry.unlink()
            run(["uvx", "--from", DOUYIN_YTDLP, "yt-dlp", *options], 360, "抖音视频下载（备用下载器）")
        files = [p for p in temp.iterdir() if p.suffix.lower() in MEDIA_SUFFIXES]
        if len(files) != 1:
            raise StudyError("下载器没有返回一个视频文件")
        data = read_json(temp / "video.info.json")
        post_id = douyin_id(url)
        if str(data.get("id")) != post_id:
            raise StudyError("下载器返回的作品 ID 与请求不一致")
        if expected_author and data.get("channel_id") != expected_author:
            raise StudyError("作品作者未能与目标博主核验一致")
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
        ], 45, "抽帧")
        if target.is_file() and target.stat().st_size > 0:
            records.append({"id": f"f{index:02}", "second": second, "file": target.name})
    if not records:
        raise StudyError("未提取到画面")
    return records


def audio_evidence(path: Path, directory: Path, duration: float) -> dict:
    # Metrics refer to the mixed soundtrack, including possible music or effects.
    log = run([
        "ffmpeg", "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a:0",
        "-af", "ebur128=peak=true,silencedetect=noise=-35dB:d=0.30", "-f", "null", "-",
    ], max(90, int(duration * .75)), "音轨测量", diagnostics=True)
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
        ], 60, "导出听音片段")
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
        raise StudyError("转写必须是包含 start、end、text 的数组")
    normalized = []
    for entry in data:
        if not isinstance(entry, dict):
            raise StudyError("转写片段必须是对象")
        start, end, text = (entry.get(field) for field in ("start", "end", "text"))
        if type(start) not in (int, float) or type(end) not in (int, float):
            raise StudyError("转写时间需使用数值秒")
        if not 0 <= start < end <= duration + 2:
            raise StudyError("转写时间超出媒体范围或结束早于开始")
        if isinstance(text, str) and text.strip() and start < duration:
            normalized.append({"start": start, "end": min(end, duration), "text": text.strip()})
    normalized.sort(key=lambda item: (item["start"], item["end"]))
    return [{"id": f"t{index:04}", **item} for index, item in enumerate(normalized, 1)]


def transcribe(path: Path, directory: Path, duration: float, model: Path,
               executable: str, language: str, imported: Path | None) -> list[dict]:
    if imported:
        return transcript_segments(read_json(imported), duration)
    if not model.is_file():
        raise StudyError("缺少本地 Whisper 模型。先运行 creator-study setup-model")
    with TemporaryDirectory(dir=directory) as work:
        work = Path(work)
        audio, output = work / "audio.wav", work / "asr"
        run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-map", "0:a:0",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(audio),
        ], 300, "提取音轨")
        run([
            executable, "--model", str(model), "--file", str(audio), "--language", language,
            "--output-json", "--output-file", str(output), "--no-prints",
        ], max(180, int(duration * 4)), "本地语音转写")
        raw = read_json(output.with_suffix(".json"))
        response = raw.get("transcription")
        if not isinstance(response, list):
            raise StudyError("Whisper 返回了无法识别的转写格式")
        segments = []
        for entry in response:
            offsets = entry["offsets"]
            start, end = offsets["from"] / 1000, offsets["to"] / 1000
            if start < end and start < duration and end <= duration + 2:
                segments.append({"start": start, "end": end, "text": entry["text"]})
        normalized = transcript_segments(segments, duration)
        write_json(directory / "whisper.json", raw)
        return normalized
