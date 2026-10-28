from uuid import uuid4

from lectio.bot.formatting import (
    MESSAGE_CHARS,
    format_answer,
    format_hits,
    markdown_to_html,
    split_message,
    strip_links,
)
from lectio.modules.search.schemas import SearchHit


def _hit(title: str, start: float, highlight: str = "текст") -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        lecture_id=uuid4(),
        lecture_title=title,
        start_seconds=start,
        end_seconds=start + 40,
        text=highlight,
        highlight=highlight,
        score=1.0,
    )


def test_markdown_to_html() -> None:
    assert markdown_to_html(
        "## Главное\n\n- **Теорема** <важна>\n  - *катет* и `a^2`\n\n\n\nКонец"
    ) == (
        "<b>Главное</b>\n\n"
        "• <b>Теорема</b> &lt;важна&gt;\n"
        "  • <i>катет</i> и <code>a^2</code>\n\n"
        "Конец"
    )


def test_split_message_keeps_paragraphs_whole() -> None:
    paragraph = "слово " * 300
    parts = split_message("\n\n".join([paragraph] * 5))

    assert all(len(part) <= MESSAGE_CHARS for part in parts)
    assert "".join(parts).replace("\n", "") == (paragraph * 5)
    assert len(split_message("x" * (MESSAGE_CHARS * 2 + 10))) == 3


def test_hits_and_answers_link_to_moments() -> None:
    hit = _hit("Пифагор & Co", 95.4, "про <mark>катет</mark>")

    found = format_hits([hit])

    assert f"/lectures/{hit.lecture_id}?t=95" in found
    assert "про <b>катет</b>" in found
    assert "Пифагор &amp; Co" in found
    assert format_hits([]).startswith("Ничего не нашлось")

    answer = format_answer("Катет — сторона [1], а не [7].", [hit])

    assert (
        f'<a href="http://localhost:5173/lectures/{hit.lecture_id}?t=95">[1]</a>'
        in answer
    )
    assert "[7]" in answer
    assert "<b>Источники</b>\n[1] " in answer
    assert "<a " not in strip_links(answer)
