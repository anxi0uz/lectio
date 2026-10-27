import bisect
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import structlog
from pydantic import ValidationError

from lectio.ml.llm import LLMClient, LLMUnavailableError
from lectio.models import Chunk
from lectio.modules.summaries.prompts import (
    OUTLINE_SYSTEM,
    PART_SYSTEM,
    SUMMARY_SYSTEM,
)
from lectio.modules.summaries.schemas import (
    KeyTerm,
    Outline,
    OutlineSection,
    PartDigest,
)

log = structlog.get_logger(
    component="summaries.generator",
)

MAX_KEY_TERMS = 20
PART_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class GeneratedSummary:
    summary: str
    sections: list[OutlineSection]
    key_terms: list[KeyTerm]


def split_into_parts(
    chunks: Sequence[Chunk],
    part_chars: int,
) -> list[list[Chunk]]:
    parts: list[list[Chunk]] = []
    current: list[Chunk] = []
    size = 0

    for chunk in chunks:
        if current and size + len(chunk.text) > part_chars:
            parts.append(current)
            current, size = [], 0

        current.append(chunk)
        size += len(chunk.text)

    if current:
        parts.append(current)

    return parts


def format_part(chunks: Sequence[Chunk]) -> str:
    return "\n".join(f"[{int(chunk.start_seconds)}] {chunk.text}" for chunk in chunks)


async def generate_summary(
    llm: LLMClient,
    title: str,
    chunks: Sequence[Chunk],
    part_chars: int,
    on_progress: Callable[[float], None] | None = None,
) -> GeneratedSummary:
    parts = split_into_parts(chunks, part_chars)
    # Map, reduce summary, reduce outline.
    total_steps = len(parts) + 2
    digests: list[PartDigest] = []

    def report(step: int) -> None:
        if on_progress is not None:
            on_progress(step / total_steps)

    for index, part in enumerate(parts, start=1):
        digest = await _digest_part(
            llm,
            title,
            part,
            index,
            len(parts),
        )

        if digest is not None:
            digests.append(digest)

        report(index)

    if not digests:
        raise LLMUnavailableError(
            "Language model did not return a usable summary",
        )

    summary = await llm.complete(
        SUMMARY_SYSTEM,
        [
            {
                "role": "user",
                "content": f"Лекция «{title}».\n\n"
                + "\n\n".join(
                    f"Часть {number}: {digest.summary}"
                    for number, digest in enumerate(digests, start=1)
                ),
            }
        ],
    )
    report(len(parts) + 1)

    known_starts = sorted(chunk.start_seconds for chunk in chunks)
    draft = [section for digest in digests for section in digest.sections]
    sections = await _merge_outline(llm, draft) if len(digests) > 1 else draft
    report(total_steps)

    return GeneratedSummary(
        summary=summary,
        sections=normalize_outline(sections, known_starts),
        key_terms=locate_terms(
            [term for digest in digests for term in digest.terms],
            chunks,
        ),
    )


async def _digest_part(
    llm: LLMClient,
    title: str,
    part: Sequence[Chunk],
    index: int,
    total: int,
) -> PartDigest | None:
    prompt = f"Лекция «{title}», часть {index} из {total}.\n\n{format_part(part)}"

    for attempt in range(1, PART_ATTEMPTS + 1):
        try:
            payload = await llm.complete_json(PART_SYSTEM, prompt)
            return PartDigest.model_validate(payload)
        except (LLMUnavailableError, ValidationError) as error:
            log.warning(
                "summary_part_failed",
                part=index,
                attempt=attempt,
                error=str(error),
            )

    return None


async def _merge_outline(
    llm: LLMClient,
    draft: list[OutlineSection],
) -> list[OutlineSection]:
    lines: list[str] = []

    for section in draft:
        lines.append(f"- [{int(section.start)}] {section.title}")
        lines.extend(
            f"  - [{int(sub.start)}] {sub.title}" for sub in section.subsections
        )

    try:
        payload = await llm.complete_json(
            OUTLINE_SYSTEM,
            "\n".join(lines),
        )
        merged = Outline.model_validate(payload).sections
    except (LLMUnavailableError, ValidationError) as error:
        log.warning(
            "outline_merge_failed",
            error=str(error),
        )
        return draft

    return merged or draft


def snap_to_known(value: float, known: Sequence[float]) -> float:
    """Move a model-produced time to the nearest real chunk start."""
    index = bisect.bisect_left(known, value)
    candidates = known[max(index - 1, 0) : index + 1]

    return min(candidates, key=lambda start: abs(start - value))


def normalize_outline(
    sections: Sequence[OutlineSection],
    known_starts: Sequence[float],
) -> list[OutlineSection]:
    if not known_starts:
        return []

    snapped = sorted(
        (
            section.model_copy(
                update={
                    "title": section.title.strip()[:300],
                    "start": snap_to_known(section.start, known_starts),
                }
            )
            for section in sections
            if section.title.strip()
        ),
        key=lambda section: section.start,
    )

    result: list[OutlineSection] = []

    for index, section in enumerate(snapped):
        if result and result[-1].start == section.start:
            continue

        next_start = (
            snapped[index + 1].start if index + 1 < len(snapped) else float("inf")
        )
        subsections = sorted(
            (
                sub.model_copy(
                    update={
                        "title": sub.title.strip()[:300],
                        "start": snap_to_known(sub.start, known_starts),
                    }
                )
                for sub in section.subsections
                if sub.title.strip()
            ),
            key=lambda sub: sub.start,
        )
        section.subsections = [
            sub for sub in subsections if section.start <= sub.start < next_start
        ]
        result.append(section)

    # The model tends to skip the introduction; the contents should cover
    # the lecture from its first second.
    if result:
        result[0].start = known_starts[0]

    return result


def _stem(word: str) -> str:
    """Crude stemming: Russian inflection mostly changes the last letters."""
    if len(word) <= 4:
        return word

    return word[: max(4, len(word) - 2)]


def locate_terms(
    terms: Sequence[KeyTerm],
    chunks: Sequence[Chunk],
) -> list[KeyTerm]:
    seen: set[str] = set()
    located: list[KeyTerm] = []

    for term in terms:
        name = term.term.strip()
        key = name.casefold()

        if not name or key in seen:
            continue

        seen.add(key)
        stems = [_stem(word) for word in key.split()]
        start = next(
            (
                chunk.start_seconds
                for chunk in chunks
                if all(stem in chunk.text.casefold() for stem in stems)
            ),
            None,
        )

        located.append(
            KeyTerm(
                term=name,
                definition=term.definition.strip(),
                start_seconds=start,
            )
        )

        if len(located) == MAX_KEY_TERMS:
            break

    return located
