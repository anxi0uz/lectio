from lectio.ml.chunking import TextChunk, build_chunks
from lectio.ml.llm import ThinkFilter
from lectio.ml.transcriber import TranscribedSegment, split_into_cues
from lectio.modules.summaries.generator import locate_terms, normalize_outline
from lectio.modules.summaries.schemas import KeyTerm, OutlineSection
from lectio.modules.transcripts.service import format_vtt_timestamp


def _segments(*bounds: tuple[float, float]) -> list[TranscribedSegment]:
    return [
        TranscribedSegment(start, end, f"s{index}")
        for index, (start, end) in enumerate(bounds)
    ]


def test_chunks_overlap_by_one_segment() -> None:
    segments = _segments((0, 10), (10, 20), (20, 30), (30, 40), (40, 50))

    chunks = build_chunks(segments, target_seconds=20, max_seconds=30)

    assert chunks == [
        TextChunk(0, 20, "s0 s1"),
        TextChunk(10, 30, "s1 s2"),
        TextChunk(20, 40, "s2 s3"),
        TextChunk(30, 50, "s3 s4"),
    ]


def test_chunks_respect_max_length_and_skip_empty_tail() -> None:
    segments = _segments((0, 5), (5, 60), (60, 61))

    chunks = build_chunks(segments, target_seconds=40, max_seconds=50)

    assert [chunk.text for chunk in chunks] == ["s0", "s1", "s1 s2"]
    assert build_chunks([], target_seconds=40, max_seconds=50) == []


def test_cues_break_on_sentences_and_length() -> None:
    words = [
        TranscribedSegment(index * 0.5, index * 0.5 + 0.4, f" w{index}")
        for index in range(20)
    ]
    words[3] = TranscribedSegment(1.5, 1.9, " конец.")

    cues = split_into_cues(words)

    assert cues[0].text == "w0 w1 w2 конец."
    assert all(cue.end - cue.start <= 7.0 for cue in cues)
    assert " ".join(cue.text for cue in cues).split() == [
        word.text.strip() for word in words
    ]


def test_cue_keeps_last_word_of_sentence() -> None:
    words = [
        TranscribedSegment(index * 0.5, index * 0.5 + 0.4, f" w{index}")
        for index in range(14)
    ] + [TranscribedSegment(7.0, 7.4, " итог.")]

    cues = split_into_cues(words)

    assert len(cues) == 1
    assert cues[0].text.endswith("итог.")


def test_outline_is_snapped_sorted_and_deduplicated() -> None:
    sections = [
        OutlineSection.model_validate(
            {
                "title": "Второй",
                "start": 61,
                "subsections": [
                    {"title": "Внутри", "start": 95},
                    {"title": "Чужой", "start": 10},
                ],
            }
        ),
        OutlineSection(title="Первый", start=3),
        OutlineSection(title="Дубль", start=1),
        OutlineSection(title="  ", start=0),
    ]

    result = normalize_outline(sections, [0, 30, 60, 90])

    assert [(section.title, section.start) for section in result] == [
        ("Первый", 0),
        ("Второй", 60),
    ]

    assert [(sub.title, sub.start) for sub in result[1].subsections] == [
        ("Внутри", 90),
    ]


def test_outline_starts_at_lecture_start() -> None:
    result = normalize_outline(
        [OutlineSection(title="Основная часть", start=40)],
        [0, 30, 60],
    )

    assert result[0].start == 0


def test_terms_are_deduplicated_and_located() -> None:
    class FakeChunk:
        def __init__(self, start: float, text: str) -> None:
            self.start_seconds = start
            self.text = text

    chunks = [
        FakeChunk(0, "Вступление"),
        FakeChunk(30, "Определим гипотенузу треугольника"),
        FakeChunk(60, "Теорема Пифагора о прямоугольном треугольнике"),
    ]
    terms = [
        KeyTerm(term="Гипотенуза", definition="Сторона против прямого угла"),
        KeyTerm(term="гипотенуза", definition="Повтор"),
        KeyTerm(term="Катет", definition="Сторона у прямого угла"),
        KeyTerm(term="теорема Пифагора", definition="a² + b² = c²"),
    ]

    located = locate_terms(terms, chunks)  # pyright: ignore[reportArgumentType]

    assert [(term.term, term.start_seconds) for term in located] == [
        ("Гипотенуза", 30),
        ("Катет", None),
        ("теорема Пифагора", 60),
    ]


def test_vtt_timestamp() -> None:
    assert format_vtt_timestamp(0) == "00:00:00.000"
    assert format_vtt_timestamp(3725.4567) == "01:02:05.457"


def test_think_blocks_are_dropped_from_a_stream() -> None:
    think = ThinkFilter()
    pieces = ["<thi", "nk>reasoning", " goes </th", "ink>\n\nОтвет", " <", "b>да</b>"]

    streamed = "".join(think.feed(piece) for piece in pieces) + think.flush()

    assert streamed == "Ответ <b>да</b>"
