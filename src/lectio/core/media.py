import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STDERR_TAIL_CHARS = 2000


class MediaCommandError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MediaInfo:
    duration: float | None
    has_audio: bool
    has_video: bool


@dataclass(frozen=True, slots=True)
class RemoteVideo:
    title: str | None
    duration: float | None
    is_live: bool


class UrlProbeError(RuntimeError):
    pass


async def run_command(*command: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise MediaCommandError(
            f"{command[0]} failed: "
            f"{stderr.decode(errors='replace')[-STDERR_TAIL_CHARS:]}",
        )

    return stdout.decode()


async def probe_media(path: Path) -> MediaInfo | None:
    """Streams and length of a media file; None if ffprobe cannot read it."""
    try:
        output = await run_command(
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        )
        payload = json.loads(output)
    except (MediaCommandError, json.JSONDecodeError):
        return None

    streams = payload.get("streams", [])
    kinds = {stream.get("codec_type") for stream in streams}
    # Cover art in audio files is a "video" stream of one frame.
    has_video = any(
        stream.get("codec_type") == "video"
        and not stream.get("disposition", {}).get("attached_pic")
        for stream in streams
    )

    try:
        duration = float(payload.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        duration = None

    return MediaInfo(
        duration=duration,
        has_audio="audio" in kinds,
        has_video=has_video,
    )


async def extract_frame(
    video: Path | str,
    at_seconds: float,
    output: Path,
    width: int = 640,
) -> None:
    """Save one frame as a JPEG. Written aside and renamed, so a reader
    never sees a half-written file."""
    partial = output.with_name(f".{output.stem}-{os.getpid()}{output.suffix}")

    try:
        await run_command(
            "ffmpeg",
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            # -ss before -i seeks by keyframes: fast even deep into a long file.
            "-ss",
            f"{at_seconds:.2f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "4",
            str(partial),
        )
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)


def probe_url(url: str) -> RemoteVideo:
    """Metadata of a video page without downloading it. Blocking."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }

    try:
        with YoutubeDL(options) as ydl:  # pyright: ignore[reportArgumentType]
            info = ydl.extract_info(url, download=False)
    except DownloadError as error:
        raise UrlProbeError(str(error)) from error

    if not info:
        raise UrlProbeError("No video found at the URL")

    if info.get("_type") == "playlist":
        raise UrlProbeError("The URL is a playlist")

    return RemoteVideo(
        title=info.get("title"),
        duration=info.get("duration"),
        is_live=bool(info.get("is_live")),
    )
