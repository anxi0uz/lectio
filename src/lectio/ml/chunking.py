from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class TimedText(Protocol):
    @property
    def start(self) -> float: ...

    @property
    def end(self) -> float: ...

    @property
    def text(self) -> str: ...


@dataclass(frozen=True, slots=True)
class TextChunk:
    start: float
    end: float
    text: str


def build_chunks(
    segments: Sequence[TimedText],
    target_seconds: float,
    max_seconds: float,
) -> list[TextChunk]:
    """Group consecutive segments into search windows.

    Each window after the first repeats the previous window's last segment,
    so a thought split across a boundary is still found as a whole.
    """
    chunks: list[TextChunk] = []
    window: list[TimedText] = []
    has_new_text = False

    def flush() -> None:
        chunks.append(
            TextChunk(
                start=window[0].start,
                end=window[-1].end,
                text=" ".join(segment.text for segment in window),
            )
        )

    for segment in segments:
        if has_new_text and segment.end - window[0].start > max_seconds:
            flush()
            overlap = window[-1]
            fits = segment.end - overlap.start <= max_seconds
            window = [overlap] if fits else []
            has_new_text = False

        window.append(segment)
        has_new_text = True

        if window[-1].end - window[0].start >= target_seconds:
            flush()
            window = [window[-1]]
            has_new_text = False

    if has_new_text:
        flush()

    return chunks
