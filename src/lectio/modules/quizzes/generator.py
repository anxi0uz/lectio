import math
import random
from collections.abc import Sequence
from typing import Any

import structlog
from pydantic import ValidationError

from lectio.ml.llm import LLMClient, LLMUnavailableError
from lectio.models import Chunk
from lectio.modules.quizzes.prompts import QUIZ_SYSTEM
from lectio.modules.quizzes.schemas import DraftQuestion, QuizQuestion
from lectio.modules.summaries.generator import (
    format_part,
    snap_to_known,
    split_into_parts,
)

log = structlog.get_logger(
    component="quizzes.generator",
)

QUIZ_SIZE = 6
# Each part is one model call; a long lecture is sampled, not read whole.
MAX_PARTS = 3
MAX_OPTIONS = 4
# A right answer much longer than every wrong one gives itself away, and is
# usually a quote while a wrong option paraphrases the same fact.
MAX_ANSWER_LENGTH_RATIO = 2.0


def pick_parts(
    parts: Sequence[list[Chunk]],
    count: int,
) -> list[list[Chunk]]:
    """Evenly spaced parts, so questions cover the whole lecture."""
    if len(parts) <= count:
        return list(parts)

    step = len(parts) / count

    return [parts[int(index * step + step / 2)] for index in range(count)]


def build_question(
    draft: DraftQuestion,
    known_starts: Sequence[float],
) -> QuizQuestion | None:
    correct = draft.correct.strip()
    options = [correct]
    seen = {correct.casefold()}

    for option in draft.wrong:
        option = option.strip()

        if option and option.casefold() not in seen:
            seen.add(option.casefold())
            options.append(option)

    options = options[:MAX_OPTIONS]
    longest_wrong = max((len(option) for option in options[1:]), default=0)

    if len(options) < 3 or len(correct) > longest_wrong * MAX_ANSWER_LENGTH_RATIO:
        return None

    # Small models tend to put the right answer first.
    random.shuffle(options)

    return QuizQuestion(
        question=draft.question.strip(),
        options=options,
        answer=options.index(correct),
        explanation=draft.explanation.strip(),
        start_seconds=(
            snap_to_known(draft.start, known_starts)
            if draft.start is not None and known_starts
            else None
        ),
    )


def parse_questions(
    payload: dict[str, Any],
    known_starts: Sequence[float],
) -> list[QuizQuestion]:
    items = payload.get("questions")

    if not isinstance(items, list):
        return []

    questions: list[QuizQuestion] = []

    # One malformed question should not cost the rest of the part.
    for item in items:
        try:
            draft = DraftQuestion.model_validate(item)
        except ValidationError:
            continue

        if question := build_question(draft, known_starts):
            questions.append(question)

    return questions


async def generate_quiz(
    llm: LLMClient,
    title: str,
    chunks: Sequence[Chunk],
    part_chars: int,
) -> list[QuizQuestion]:
    parts = pick_parts(split_into_parts(chunks, part_chars), MAX_PARTS)
    per_part = math.ceil(QUIZ_SIZE / len(parts)) if parts else 0
    questions: list[QuizQuestion] = []

    for index, part in enumerate(parts, start=1):
        known_starts = [chunk.start_seconds for chunk in part]
        prompt = (
            f"Лекция «{title}». Составь {per_part} вопроса(ов) по этой части."
            f"\n\n{format_part(part)}"
        )

        try:
            payload = await llm.complete_json(QUIZ_SYSTEM, prompt)
        except LLMUnavailableError as error:
            log.warning(
                "quiz_part_failed",
                part=index,
                error=str(error),
            )
            continue

        questions.extend(parse_questions(payload, known_starts)[:per_part])

    if not questions:
        raise LLMUnavailableError(
            "Language model did not return a usable quiz",
        )

    return questions[:QUIZ_SIZE]
