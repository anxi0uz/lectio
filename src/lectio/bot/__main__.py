import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from lectio.bot.handlers import router
from lectio.core.config import get_settings
from lectio.core.logger import configure_logging
from lectio.db.redis import close_redis
from lectio.db.session import dispose_engine
from lectio.ml.embedder import get_query_embedder
from lectio.ml.llm import close_llm

log = structlog.get_logger(
    component="bot",
)

COMMANDS = [
    BotCommand(command="lectures", description="Выбрать готовую лекцию"),
    BotCommand(command="search", description="Поиск по всем лекциям"),
    BotCommand(command="ask", description="Вопрос по текущей лекции"),
    BotCommand(command="all", description="Вопросы по всем лекциям"),
    BotCommand(command="help", description="Что умеет бот"),
]


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.debug)

    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    bot = Bot(
        settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    # Loaded up front so the first search does not wait for the model.
    await asyncio.to_thread(get_query_embedder)
    await bot.set_my_commands(COMMANDS)

    me = await bot.get_me()
    log.info("bot_started", username=me.username)

    try:
        await dispatcher.start_polling(bot)
    finally:
        log.info("bot_stopping")

        await bot.session.close()
        await close_llm()
        await close_redis()
        await dispose_engine()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
