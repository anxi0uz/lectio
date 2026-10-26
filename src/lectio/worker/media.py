from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from lectio.core.config import get_settings
from lectio.core.media import run_command

log = structlog.get_logger(
    component="worker.media",
)


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DownloadedVideo:
    path: Path
    title: str | None
    duration: float | None


def download_video(
    url: str,
    directory: Path,
    on_progress: Callable[[float], None],
) -> DownloadedVideo:
    """Blocking; run it in a thread."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    height = get_settings().download_max_height

    def hook(status: dict[str, Any]) -> None:
        total = status.get("total_bytes") or status.get("total_bytes_estimate")

        if status.get("status") == "downloading" and total:
            on_progress(min(status.get("downloaded_bytes", 0) / total, 1.0))

    options: dict[str, Any] = {
        # Prefer H.264 + AAC in MP4: it plays in every browser.
        "format": (
            f"bv*[height<={height}][vcodec^=avc1]+ba[ext=m4a]"
            f"/b[height<={height}][ext=mp4]"
            f"/bv*[height<={height}]+ba"
            f"/b[height<={height}]/b"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(directory / "video.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [hook],
    }

    try:
        with YoutubeDL(options) as ydl:  # pyright: ignore[reportArgumentType]
            info = ydl.extract_info(url, download=True)
    except DownloadError as error:
        raise MediaError(f"Could not download video: {error}") from error

    files = sorted(
        path
        for path in directory.glob("video.*")
        if path.suffix not in (".part", ".ytdl")
    )

    if not files:
        raise MediaError("Downloaded video file not found")

    return DownloadedVideo(
        path=files[0],
        title=(info or {}).get("title"),
        duration=(info or {}).get("duration"),
    )


async def extract_audio(
    video: Path,
    audio: Path,
) -> None:
    # 16 kHz mono PCM is what Whisper consumes internally.
    await run_command(
        "ffmpeg",
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio),
    )
