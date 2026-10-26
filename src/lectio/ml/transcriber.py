import wave
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Protocol

import numpy as np
import structlog

from lectio.core.config import get_settings
from lectio.ml.device import free_accelerator_memory, resolve_device

log = structlog.get_logger(
    component="ml.transcriber",
)

ProgressCallback = Callable[[float], None]

# Subtitle cue limits: short enough to read along, long enough not to flicker.
CUE_MAX_SECONDS = 7.0
CUE_MIN_SECONDS = 1.5
CUE_MAX_CHARS = 90
CUE_SENTENCE_SLACK = 2.0
CUE_SENTENCE_SLACK_CHARS = 25
SENTENCE_END = (".", "?", "!", "…")


@dataclass(frozen=True, slots=True)
class TranscribedSegment:
    start: float
    end: float
    text: str


# Words carry their leading space, as Whisper emits them.
TranscribedWord = TranscribedSegment


def split_into_cues(
    words: Sequence[TranscribedWord],
) -> list[TranscribedSegment]:
    """Regroup word timings into subtitle-sized segments.

    Whisper segments run up to 30 s in batched mode, far too long for
    subtitles and for jumping to a precise moment.
    """
    cues: list[TranscribedSegment] = []
    current: list[TranscribedWord] = []

    def flush() -> None:
        text = "".join(word.text for word in current).strip()

        if text:
            cues.append(
                TranscribedSegment(
                    start=current[0].start,
                    end=current[-1].end,
                    text=text,
                )
            )

        current.clear()

    for word in words:
        ends_sentence = word.text.rstrip().endswith(SENTENCE_END)
        # A cue may run slightly long rather than leave the last word of a
        # sentence alone on screen.
        max_seconds = CUE_MAX_SECONDS + (CUE_SENTENCE_SLACK if ends_sentence else 0)
        max_chars = CUE_MAX_CHARS + (CUE_SENTENCE_SLACK_CHARS if ends_sentence else 0)

        if current and (
            word.end - current[0].start > max_seconds
            or sum(len(item.text) for item in current) + len(word.text) > max_chars
        ):
            flush()

        current.append(word)

        if ends_sentence and word.end - current[0].start >= CUE_MIN_SECONDS:
            flush()

    if current:
        flush()

    return cues


@dataclass(frozen=True, slots=True)
class Transcript:
    language: str | None
    duration: float | None
    segments: list[TranscribedSegment]


class Transcriber(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        on_progress: ProgressCallback,
    ) -> Transcript: ...


def read_pcm_wav(path: Path) -> np.ndarray:
    """Load the 16 kHz mono PCM WAV produced by ffmpeg as float32 samples.

    faster-whisper would decode it with PyAV, whose API keeps changing; the
    file is already in the exact format Whisper needs.
    """
    with wave.open(str(path), "rb") as audio:
        frames = audio.readframes(audio.getnframes())

    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


class FasterWhisperTranscriber:
    def __init__(self) -> None:
        settings = get_settings()
        device = resolve_device(settings.device)

        # CTranslate2 has no Metal backend.
        if device == "mps":
            device = "cpu"

        # torch preloads the cuBLAS/cuDNN wheels it ships with, so CTranslate2
        # finds them without LD_LIBRARY_PATH tweaks.
        import torch  # noqa: F401
        from faster_whisper import BatchedInferencePipeline, WhisperModel

        model = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=settings.whisper_compute_type,
        )
        self._pipeline = BatchedInferencePipeline(model)
        self._batch_size = settings.whisper_batch_size
        self._language = settings.whisper_language or None

        log.info(
            "whisper_loaded",
            backend="faster_whisper",
            model=settings.whisper_model,
            device=device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(
        self,
        audio_path: Path,
        on_progress: ProgressCallback,
    ) -> Transcript:
        raw_segments, info = self._pipeline.transcribe(
            read_pcm_wav(audio_path),
            batch_size=self._batch_size,
            language=self._language,
            word_timestamps=True,
        )

        segments: list[TranscribedSegment] = []

        for raw in raw_segments:
            segments.extend(
                split_into_cues(
                    [
                        TranscribedWord(
                            start=word.start,
                            end=word.end,
                            text=word.word,
                        )
                        for word in raw.words or []
                    ]
                    or [TranscribedWord(raw.start, raw.end, raw.text)],
                )
            )

            if info.duration:
                on_progress(min(raw.end / info.duration, 1.0))

        return Transcript(
            language=info.language,
            duration=info.duration,
            segments=segments,
        )


class MlxWhisperTranscriber:
    def __init__(self) -> None:
        settings = get_settings()
        model = settings.whisper_model

        if "/" not in model:
            model = f"mlx-community/whisper-{model}"

        self._model = model
        self._language = settings.whisper_language or None

        log.info(
            "whisper_configured",
            backend="mlx",
            model=model,
        )

    def transcribe(
        self,
        audio_path: Path,
        on_progress: ProgressCallback,
    ) -> Transcript:
        import mlx_whisper  # pyright: ignore[reportMissingImports]

        # mlx-whisper reports no progress, only the final result.
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=self._model,
            language=self._language,
            word_timestamps=True,
            verbose=None,
        )
        on_progress(1.0)

        segments: list[TranscribedSegment] = []

        for raw in result["segments"]:
            segments.extend(
                split_into_cues(
                    [
                        TranscribedWord(
                            start=float(word["start"]),
                            end=float(word["end"]),
                            text=word["word"],
                        )
                        for word in raw.get("words", [])
                    ]
                    or [
                        TranscribedWord(
                            float(raw["start"]),
                            float(raw["end"]),
                            raw["text"],
                        )
                    ],
                )
            )

        return Transcript(
            language=result.get("language"),
            duration=segments[-1].end if segments else None,
            segments=segments,
        )


@cache
def get_transcriber() -> Transcriber:
    if get_settings().whisper_backend == "mlx":
        return MlxWhisperTranscriber()

    return FasterWhisperTranscriber()


def release_transcriber() -> None:
    get_transcriber.cache_clear()
    free_accelerator_memory()
