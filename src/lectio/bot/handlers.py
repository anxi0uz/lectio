import asyncio
import html
import re
from uuid import UUID

import structlog
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender

from lectio.bot.formatting import ERROR_MESSAGES, STATUS_LABELS, strip_links
from lectio.bot.service import (
    LectureCard,
    answer_messages,
    get_current_lecture,
    import_lecture,
    lecture_card,
    pop_pending_link,
    recent_lectures,
    search_messages,
    set_current_lecture,
    set_pending_link,
    suggested_question,
)
from lectio.core.exceptions import DomainError
from lectio.core.jobs import JobKind, enqueue_job
from lectio.db.redis import get_redis_client
from lectio.db.session import get_session_factory
from lectio.ml.embedder import get_query_embedder
from lectio.ml.llm import get_llm
from lectio.ml.reranker import get_reranker
from lectio.models import Lecture
from lectio.models.enums import LectureStatus
from lectio.modules.lectures.exceptions import DuplicateLectureError

log = structlog.get_logger(
    component="bot.handlers",
)

router = Router()

URL = re.compile(r"https?://\S+")
POLL_SECONDS = 5.0
# Longest lectures take about this long on a small GPU.
WATCH_SECONDS = 4 * 60 * 60

HELP = (
    "<b>Lectio</b> — смысловой поиск по видеолекциям.\n\n"
    "• Пришлите <b>ссылку</b> на лекцию (YouTube, Vimeo…) — расшифрую и пришлю "
    "конспект с оглавлением.\n"
    "• Напишите <b>вопрос</b> со знаком «?» — отвечу по текущей лекции со "
    "ссылками на моменты видео.\n"
    "• Напишите <b>что угодно ещё</b> — найду по смыслу во всех лекциях.\n\n"
    "/lectures — выбрать готовую лекцию\n"
    "/search текст — поиск по всем лекциям\n"
    "/ask вопрос — вопрос по текущей лекции\n"
    "/all — вопросы по всем лекциям сразу"
)

# Watchers outlive their handler; keep references so they are not collected.
_watchers: set[asyncio.Task[None]] = set()


async def send_parts(
    bot: Bot,
    chat_id: int,
    parts: list[str],
) -> None:
    for part in parts:
        try:
            await bot.send_message(chat_id, part)
        except TelegramBadRequest as error:
            # Telegram refuses some links, e.g. to localhost; keep the text.
            log.warning("telegram_rejected_message", error=str(error))
            await bot.send_message(chat_id, strip_links(part))


async def send_card(
    bot: Bot,
    chat_id: int,
    card: LectureCard,
) -> None:
    await send_parts(bot, chat_id, card.messages)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=question,
                    callback_data=f"ask:{card.lecture_id}:{index}",
                )
            ]
            for index, question in enumerate(card.questions)
        ]
    )

    await bot.send_message(
        chat_id,
        "Спросите что-нибудь по этой лекции — нажмите вопрос или напишите свой:",
        reply_markup=keyboard,
    )


def _error_text(error: DomainError) -> str:
    return ERROR_MESSAGES.get(error.code or "", f"Не получилось: {error.detail}")


def _status_text(lecture: Lecture) -> str:
    label = STATUS_LABELS[lecture.status]

    if lecture.status == LectureStatus.FAILED:
        return f"❌ «{html.escape(lecture.title)}»: {label}."

    if lecture.status == LectureStatus.READY:
        return f"✅ «{html.escape(lecture.title)}»: {label}."

    progress = f" — {int(lecture.progress * 100)}%" if lecture.progress else ""

    return f"⏳ «{html.escape(lecture.title)}»: {label}{progress}"


async def watch_processing(
    bot: Bot,
    chat_id: int,
    message_id: int,
    lecture_id: UUID,
) -> None:
    """Keep the status message current and send the card when done."""
    shown = ""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + WATCH_SECONDS

    while loop.time() < deadline:
        await asyncio.sleep(POLL_SECONDS)

        async with get_session_factory()() as db:
            lecture = await db.get(Lecture, lecture_id)

            if lecture is None:
                return

            text = _status_text(lecture)

            if text != shown:
                shown = text
                try:
                    await bot.edit_message_text(
                        text,
                        chat_id=chat_id,
                        message_id=message_id,
                    )
                except TelegramBadRequest as error:
                    log.debug("status_edit_skipped", error=str(error))

            if lecture.status == LectureStatus.FAILED:
                return

            if lecture.status == LectureStatus.READY:
                await send_card(bot, chat_id, await lecture_card(db, lecture_id))
                return


@router.message(CommandStart())
@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("lectures"))
async def lectures_handler(message: Message) -> None:
    async with get_session_factory()() as db:
        lectures = await recent_lectures(db)

    if not lectures:
        await message.answer("Готовых лекций пока нет — пришлите ссылку.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=lecture.title[:60],
                    callback_data=f"lecture:{lecture.id}",
                )
            ]
            for lecture in lectures
        ]
    )

    await message.answer("Выберите лекцию:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("lecture:"))
async def lecture_chosen_handler(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()

    if callback.message is None or callback.data is None:
        return

    lecture_id = UUID(callback.data.removeprefix("lecture:"))
    chat_id = callback.message.chat.id

    await set_current_lecture(get_redis_client(), chat_id, lecture_id)

    async with get_session_factory()() as db:
        try:
            card = await lecture_card(db, lecture_id)
        except DomainError as error:
            await bot.send_message(chat_id, _error_text(error))
            return

    await send_card(bot, chat_id, card)


@router.callback_query(F.data.startswith("ask:"))
async def suggested_question_handler(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()

    if callback.message is None or callback.data is None:
        return

    _, lecture_id, index = callback.data.split(":")
    chat_id = callback.message.chat.id

    async with get_session_factory()() as db:
        question = await suggested_question(db, UUID(lecture_id), int(index))

    if question is None:
        return

    # A button answers about its own lecture, whatever the chat chose since.
    await set_current_lecture(get_redis_client(), chat_id, UUID(lecture_id))
    await bot.send_message(chat_id, f"❓ <i>{html.escape(question)}</i>")
    await _ask(bot, chat_id, question)


@router.message(Command("all"))
async def all_lectures_handler(message: Message) -> None:
    await set_current_lecture(get_redis_client(), message.chat.id, None)
    await message.answer("Теперь отвечаю по всем лекциям сразу.")


@router.message(Command("search"))
async def search_command_handler(
    message: Message,
    command: CommandObject,
    bot: Bot,
) -> None:
    if not command.args:
        await message.answer("Напишите запрос после команды: /search теорема Пифагора")
        return

    await _search(message, bot, command.args)


@router.message(Command("ask"))
async def ask_command_handler(
    message: Message,
    command: CommandObject,
    bot: Bot,
) -> None:
    if not command.args:
        await message.answer("Напишите вопрос после команды: /ask что такое катет?")
        return

    await _ask(bot, message.chat.id, command.args)


@router.message(F.text.regexp(URL))
async def link_handler(message: Message, bot: Bot) -> None:
    match = URL.search(message.text or "")

    if match is None:
        return

    await _start_import(bot, message.chat.id, match[0])


@router.callback_query(F.data == "reimport")
async def reimport_handler(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()

    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    url = await pop_pending_link(get_redis_client(), chat_id)

    if url is None:
        await bot.send_message(chat_id, "Пришлите ссылку ещё раз.")
        return

    await _start_import(bot, chat_id, url, allow_duplicate=True)


async def _start_import(
    bot: Bot,
    chat_id: int,
    url: str,
    allow_duplicate: bool = False,
) -> None:
    redis = get_redis_client()

    async with get_session_factory()() as db:
        try:
            lecture = await import_lecture(
                db,
                url,
                allow_duplicate=allow_duplicate,
            )
        except DuplicateLectureError as error:
            await _offer_existing(bot, chat_id, url, error)
            return
        except DomainError as error:
            await bot.send_message(chat_id, _error_text(error))
            return

        await db.commit()

    # After the commit, so the worker finds the row.
    await enqueue_job(redis, JobKind.PROCESS, lecture.id)
    await set_current_lecture(redis, chat_id, lecture.id)

    status = await bot.send_message(chat_id, _status_text(lecture))
    task = asyncio.create_task(
        watch_processing(bot, chat_id, status.message_id, lecture.id),
    )
    _watchers.add(task)
    task.add_done_callback(_watchers.discard)


async def _offer_existing(
    bot: Bot,
    chat_id: int,
    url: str,
    error: DuplicateLectureError,
) -> None:
    await set_pending_link(get_redis_client(), chat_id, url)

    title = html.escape(error.extra["title"])
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть лекцию",
                    callback_data=f"lecture:{error.lecture_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Всё равно обработать заново",
                    callback_data="reimport",
                ),
            ],
        ],
    )

    await bot.send_message(
        chat_id,
        f"Эта лекция уже есть: «{title}». Открыть её или обработать заново?",
        reply_markup=keyboard,
    )


@router.message(F.text)
async def text_handler(message: Message, bot: Bot) -> None:
    text = (message.text or "").strip()

    if text.endswith("?"):
        await _ask(bot, message.chat.id, text)
    else:
        await _search(message, bot, text)


async def _search(message: Message, bot: Bot, query: str) -> None:
    async with get_session_factory()() as db:
        parts = await search_messages(
            db,
            get_query_embedder(),
            get_reranker(),
            query,
        )

    await send_parts(bot, message.chat.id, parts)


async def _ask(bot: Bot, chat_id: int, question: str) -> None:
    lecture_id = await get_current_lecture(get_redis_client(), chat_id)

    async with (
        ChatActionSender.typing(bot=bot, chat_id=chat_id),
        get_session_factory()() as db,
    ):
        try:
            parts = await answer_messages(
                db,
                get_query_embedder(),
                get_reranker(),
                get_llm(),
                question,
                lecture_id,
            )
        except DomainError as error:
            await bot.send_message(chat_id, _error_text(error))
            return

    await send_parts(bot, chat_id, parts)
