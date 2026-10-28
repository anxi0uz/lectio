"""Telegram HTML for bot replies: Telegram knows only a few tags."""

import html
import re
from collections.abc import Sequence
from uuid import UUID

from lectio.core.config import get_settings
from lectio.models.enums import LectureStatus
from lectio.modules.qa.service import format_timestamp
from lectio.modules.search.schemas import SearchHit
from lectio.modules.summaries.schemas import ChapterResponse

# Telegram's limit is 4096 characters; leave room for tags.
MESSAGE_CHARS = 3800

HEADING = re.compile(r"^#{1,6}\s+(.*)$")
BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![\w*])[*_](?![\s*_])(.+?)(?<![\s*_])[*_](?![\w*])")
CODE = re.compile(r"`([^`]+)`")
CITATION = re.compile(r"\[(\d+)\]")
LINK = re.compile(r'<a href="[^"]*">(.*?)</a>', re.DOTALL)

STATUS_LABELS = {
    LectureStatus.PENDING: "в очереди",
    LectureStatus.DOWNLOADING: "скачиваю видео",
    LectureStatus.EXTRACTING_AUDIO: "извлекаю звук",
    LectureStatus.TRANSCRIBING: "расшифровываю",
    LectureStatus.INDEXING: "строю поисковый индекс",
    LectureStatus.SUMMARIZING: "пишу конспект",
    LectureStatus.READY: "готово",
    LectureStatus.FAILED: "не удалось обработать",
}

ERROR_MESSAGES = {
    "url_unavailable": (
        "По ссылке не нашлось видео. Проверьте, что оно открыто для всех."
    ),
    "url_live_stream": "Прямые трансляции не поддерживаются — дождитесь записи.",
    "media_too_long": "Запись слишком длинная: до 4 часов.",
    "llm_unavailable": "Языковая модель сейчас недоступна, поиск при этом работает.",
}


def lecture_url(
    lecture_id: UUID,
    seconds: float | None = None,
) -> str:
    url = f"{get_settings().public_web_url.rstrip('/')}/lectures/{lecture_id}"

    return f"{url}?t={int(seconds)}" if seconds else url


def link(text: str, url: str) -> str:
    return f'<a href="{html.escape(url)}">{text}</a>'


def strip_links(text: str) -> str:
    """Fallback when Telegram rejects a link, e.g. one to localhost."""
    return LINK.sub(r"\1", text)


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = CODE.sub(r"<code>\1</code>", text)
    text = BOLD.sub(r"<b>\1</b>", text)

    return ITALIC.sub(r"<i>\1</i>", text)


def markdown_to_html(text: str) -> str:
    """The subset of Markdown our summaries and answers use."""
    lines: list[str] = []

    for line in text.splitlines():
        if heading := HEADING.match(line.strip()):
            lines.append(f"<b>{_inline(heading[1])}</b>")
        elif bullet := BULLET.match(line):
            indent = "  " * (len(bullet[1]) // 2)
            lines.append(f"{indent}• {_inline(bullet[2])}")
        else:
            lines.append(_inline(line))

    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def split_message(text: str) -> list[str]:
    """Split at paragraph breaks, so no tag is cut in half."""
    parts: list[str] = []
    current = ""

    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= MESSAGE_CHARS:
            current = candidate
            continue

        if current:
            parts.append(current)

        # A single paragraph over the limit goes by lines.
        while len(paragraph) > MESSAGE_CHARS:
            cut = paragraph.rfind("\n", 0, MESSAGE_CHARS)
            cut = cut if cut > 0 else MESSAGE_CHARS
            parts.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip("\n")

        current = paragraph

    if current:
        parts.append(current)

    return parts


def format_chapters(
    lecture_id: UUID,
    chapters: Sequence[ChapterResponse],
) -> str:
    lines = ["<b>Оглавление</b>"]

    for number, chapter in enumerate(chapters, start=1):
        time = link(
            format_timestamp(chapter.start_seconds),
            lecture_url(lecture_id, chapter.start_seconds),
        )
        lines.append(f"{number}. {time} {html.escape(chapter.title)}")

        lines.extend(
            "    "
            + link(
                format_timestamp(sub.start_seconds),
                lecture_url(lecture_id, sub.start_seconds),
            )
            + f" {html.escape(sub.title)}"
            for sub in chapter.subsections
        )

    return "\n".join(lines)


def format_hits(hits: Sequence[SearchHit]) -> str:
    if not hits:
        return "Ничего не нашлось. Попробуйте сформулировать иначе."

    blocks = []

    for hit in hits:
        # The highlight is escaped HTML with <mark>, which Telegram lacks.
        snippet = hit.highlight.replace("<mark>", "<b>").replace("</mark>", "</b>")
        time = link(
            format_timestamp(hit.start_seconds),
            lecture_url(hit.lecture_id, hit.start_seconds),
        )
        blocks.append(f"▶ {time} · <b>{html.escape(hit.lecture_title)}</b>\n{snippet}")

    return "\n\n".join(blocks)


def format_answer(
    answer: str,
    sources: Sequence[SearchHit],
) -> str:
    def cite(match: re.Match[str]) -> str:
        index = int(match[1]) - 1

        if not 0 <= index < len(sources):
            return match[0]

        hit = sources[index]

        return link(
            f"[{match[1]}]",
            lecture_url(hit.lecture_id, hit.start_seconds),
        )

    body = CITATION.sub(cite, markdown_to_html(answer))

    if not sources:
        return body

    lines = [
        f"[{number}] "
        + link(
            format_timestamp(hit.start_seconds),
            lecture_url(hit.lecture_id, hit.start_seconds),
        )
        + f" · {html.escape(hit.lecture_title)}"
        for number, hit in enumerate(sources, start=1)
    ]

    return body + "\n\n<b>Источники</b>\n" + "\n".join(lines)
