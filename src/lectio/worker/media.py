import re
import time
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


# Network hiccups are common on long downloads; each retry resumes the
# partial file rather than starting over.
DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAYS = (3, 10)
# The merged result: "video.mp4", never a per-stream "video.f136.mp4".
FINAL_VIDEO = re.compile(r"^video\.[A-Za-z0-9]+$")


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DownloadedVideo:
    path: Path
    title: str | None
    duration: float | None


def _download_with_retries(
    url: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            with YoutubeDL(options) as ydl:  # pyright: ignore[reportArgumentType]
                info = ydl.extract_info(url, download=True)
                return dict(info or {})
        except DownloadError as error:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise MediaError(f"Could not download video: {error}") from error

            log.warning(
                "download_retry",
                attempt=attempt,
                error=str(error)[:300],
            )
            time.sleep(DOWNLOAD_RETRY_DELAYS[attempt - 1])

    raise AssertionError("unreachable")


def download_video(
    url: str,
    directory: Path,
    on_progress: Callable[[float], None],
) -> DownloadedVideo:
    """Blocking; run it in a thread."""
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
        "continuedl": True,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 3,
        "socket_timeout": 30,
    }

    info = _download_with_retries(url, options)

    files = sorted(path for path in directory.iterdir() if FINAL_VIDEO.match(path.name))

    if not files:
        raise MediaError("Downloaded video file not found")

    return DownloadedVideo(
        path=files[0],
        title=info.get("title"),
        duration=info.get("duration"),
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
