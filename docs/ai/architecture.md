# Архитектура

Подробности по API — в `/docs` (OpenAPI) и README в корне. Здесь то, что
нужно держать в голове, чтобы не сломать.

## Процессы

```
браузер ── Vite :5173 (proxy /api) ── API FastAPI :8000 ── Postgres+pgvector :5432
                                          │  └─ Redis :6379 (очередь, refresh-сессии, rate limit)
                                          └─ задачи в Redis ──► воркер (python -m lectio.worker)
                                                                 ├─ yt-dlp, ffmpeg
                                                                 ├─ Whisper (faster-whisper CUDA / mlx-whisper Mac)
                                                                 ├─ BGE-M3 (эмбеддинги)
                                                                 └─ LLM по OpenAI-API (Ollama systemd :11434)
```

- API и воркер запускаются **на хосте** (`uv run`), не в контейнере: в podman
  нет доступа к GPU (нет nvidia-container-toolkit), на Mac нет Metal.
  Postgres и Redis — в podman (`podman compose up -d`).
- Воркер обрабатывает одну лекцию за раз (видеопамяти на две нет).
- Очередь — свой Redis-список (`core/jobs.py`), не arq: arq требует redis<6.
  При старте воркер переставляет в очередь лекции, застрявшие в промежуточных
  статусах; дубли безопасны (готовая лекция пропускается).

## Конвейер лекции (`worker/pipeline.py`)

`pending → downloading → extracting_audio → transcribing → indexing → summarizing → ready | failed`

- Скачивание: yt-dlp, до 720p H.264+AAC, 3 попытки с докачкой, берётся
  только склеенный `video.<ext>` (не `video.f136.mp4`).
- Перед расшифровкой и индексацией воркер просит Ollama выгрузить модель
  (`keep_alive: 0`), после этапа выгружает свою модель (`release_*`).
- Whisper отдаёт слова → `split_into_cues` собирает реплики 2–7 с (это
  сегменты субтитров) → `build_chunks` окна ~40 с с перекрытием в 1 реплику
  (единица поиска) → BGE-M3.
- Конспект — best effort: при ошибке LLM лекция всё равно `ready`, причина в
  `summary_error`. Map-reduce по частям `LLM_PART_CHARS` (9000), таймкоды
  разделов «примагничиваются» к реальным началам чанков, первый раздел = 0.
- Превью: кадр на 10% длины, JPEG, режется при обработке или лениво при
  первом запросе `/lectures/{id}/thumbnail`.
- Видео доступно сразу после скачивания, а расшифровка ещё минуты идёт —
  пользователь путал это с «повторной обработкой».

## Тест по лекции (`modules/quizzes`)

Не в конвейере, а по запросу `POST /lectures/{id}/quiz` (только тот, кто
управляет лекцией):
части расшифровки как у конспекта, берутся до 3 равномерно, 6 вопросов.
Модель отдаёт `correct` + `wrong[]`, сервер сам перемешивает варианты
(иначе маленькая модель ставит верный первым) и «примагничивает» таймкод.
Вопрос отбрасывается, если вариантов < 3 или верный в 2+ раза длиннее
неверных (выдаёт себя; обычно это цитата, а неверный — её пересказ).
Хранится в `lectures.quiz` JSONB, `GET` отдаёт последний. Ответы —
`quiz_attempts` (одна последняя попытка на пользователя, счёт считает
сервер); новый тест удаляет все попытки. Статистика теста — только
управляющему лекцией.

## Вовлечённость

Лайки (`lecture_likes`), комментарии (`comments`, необязательный
`position_seconds`; удаляет автор или управляющий лекцией),
`GET /lectures/{id}/stats` — публичные агрегаты без имён (зрители =
строки `watch_progress`). `/lectures/{id}/me` отдаёт `is_liked` и
`quiz_attempt`.

## Поиск

Гибрид: pgvector (косинус, HNSW) + Postgres FTS (`russian`, GIN) → RRF (k=60).
Реранкер (bge-reranker-v2-m3) написан, выключен (`RERANKER_MODEL` пусто).
BGE-M3 многоязычная: русский запрос находит английскую лекцию.
Подсветка `ts_headline` с предварительным экранированием HTML → фронт рендерит
`highlight` как HTML.

Подсказки в чате — `suggested_questions` лекции: модель делает их в конце
`generate_summary` (best effort), иначе `get_summary` строит запасные из
терминов и оглавления. Старые лекции: `lectio suggest-questions`.

Чат (RAG): 6 фрагментов в промпт, `[n]` → `sources[n-1]`. Потоковый
`POST /qa/stream` (SSE: `sources`, `delta`*, `done`|`error`); поиск делается
до старта потока, пока открыта сессия БД.

## Данные

`users, courses(owner_id), lectures(owner_id, course_id, status, summary,
key_terms JSONB, …), segments, chunks(embedding vector(1024), search_vector
tsvector), chapters(level 1|2), enrollments, watch_progress, favorites,
bookmarks, search_queries, lecture_likes, comments, quiz_attempts`;
`lectures.quiz` JSONB. Миграции Alembic, FK с именами (иначе откат
падает). Размерность 1024 зашита — смена модели эмбеддингов = миграция + `lectio reindex`.

Файлы: `storage/lectures/<id>/{video.*, thumbnail.jpg}`, `storage/avatars/`.
Ключ в БД (`video_path`, `avatar_path`) — путь относительно `STORAGE_DIR`,
он же ключ объекта в бакете.

## Хранилище (`core/storage.py`, `core/object_store.py`)

`STORAGE_BACKEND=local|s3`, по умолчанию local. Диск — всегда рабочая
папка: загрузка, скачивание, ffmpeg, Whisper. В режиме s3 воркер в конце
обработки переносит видео и превью в бакет (best effort: при сбое файлы
остаются на диске и работают) и удаляет папку; при переобработке скачивает
видео обратно. Отдача: локальный файл, если есть, иначе 307 на подписанную
ссылку (`S3_PUBLIC_ENDPOINT` — адрес, который видит браузер; подпись
включает хост). Превью для лекции в бакете режется ffmpeg прямо по ссылке.
Бакет создают API и воркер при старте. `lectio move-storage` переносит
старые файлы (локальная копия удаляется только после успешной загрузки).
Клиент — пакет `minio` (синхронный, вызовы в `asyncio.to_thread`).

## Telegram-бот (`lectio/bot`)

Отдельный процесс `python -m lectio.bot` (aiogram, long polling), без HTTP
к API: вызывает те же сервисы напрямую (импорт, поиск, `answer_question`,
`get_summary`). Логика — в `bot/service.py` (тестируется на настоящей БД),
оформление в Telegram HTML — `bot/formatting.py`, обработчики тонкие.
Лекции из бота без владельца (как из `lectio seed`). Текущая лекция чата —
Redis `bot:chat:<id>:lecture`. После импорта фоновая задача раз в 5 с
обновляет сообщение со статусом и присылает карточку, когда `ready`; при
перезапуске бота наблюдение теряется (лекция всё равно обработается).
Telegram может отвергнуть ссылки (например, на localhost) — тогда
сообщение уходит без ссылок. Бот грузит BGE-M3 на CPU (~2 ГБ RAM).

## Геймификация (`modules/gamification`)

Своих таблиц нет: `collect_activity` считает по пользователям просмотры,
досмотры, попытки тестов, комментарии, закладки, поиски, лайки, записи.
XP, уровень (пороги 0/100/300/600…) и ачивки — чистые функции от этих
счётчиков, поэтому новая ачивка = строка в `ACHIEVEMENTS`. Рейтинг —
только студенты, только для вошедших (показывает имена).

## Авторизация и права

JWT access 30 мин в заголовке + ротируемый refresh в HttpOnly cookie
(`/api/v1/auth`), сессии в Redis, Argon2, rate limit на вход/регистрацию —
перенесено из linkup. Роли student/teacher выбираются при регистрации.
Создавать курсы/лекции — teacher; менять — владелец; без владельца (из
`lectio seed`) — любой teacher. Видео, субтитры, превью, аватары, поиск, чат
публичны (`<video>`/`<img>` не шлют токен).

Ошибки: `DomainError` → `{"detail", "code"?}`; `code` — машинный код
(`media_no_audio`, `url_unavailable`, `llm_unavailable`, …), фронт переводит
его в русский текст (`frontend/src/api/client.ts`).

## Фронт (`frontend/`)

React 19 + TypeScript (tsc 7), Vite 8, React Router 8, TanStack Query 5,
react-markdown + KaTeX, lucide. Дизайн «Учебный плакат»: белый, чёрные
линейки, Inter Tight / Golos Text / JetBrains Mono, один акцент `#2b2bff`,
без скруглений и теней. Макет: https://claude.ai/artifact/SYTYAzWJPaUhb7fPhF2AWK
(вариант «В · Учебный плакат»). Стили — один `src/styles/index.css` с токенами.

- `api/client.ts` — fetch с авто-refresh, `uploadWithProgress` (XHR),
  `streamEvents` (SSE), перевод кодов ошибок.
- `api/hooks.ts` — все запросы; опрос статуса, пока лекция в обработке
  (и в фоне); при смене статуса `useLecture` инвалидирует зависимые данные.
- `pages/lecture/*` — главная страница продукта: свой плеер (субтитры поверх,
  главы и закладки на перемотке, ползунок громкости, горячие клавиши),
  «Сейчас говорит» + бегущая расшифровка, вкладки, чат с источниками.
- `worker/`, `scripts/`, `.openai/`, `tests/sites-worker.test.mjs` — обвязка
  хостинга Sites от Codex кореша, не трогать.

## Запуск (машина пользователя)

```bash
podman compose up -d                         # Postgres, Redis, MinIO
uv run alembic upgrade head
uv run uvicorn lectio.main:app --reload      # API
uv run python -m lectio.worker               # воркер (держать запущенным!)
npm --prefix frontend run dev                # фронт :5173
uv run python -m lectio.bot                  # Telegram-бот (нужен TELEGRAM_BOT_TOKEN)
```

В приложении Claude то же самое запускается через `.claude/launch.json`
(`api`, `web`; `api-s3` — API с `STORAGE_BACKEND=s3`). Тесты: `podman compose -f compose.test.yaml -p lectio-test up -d`,
затем `uv run pytest`. Проверки: `uv run ruff check . && uv run ruff format --check .`,
`uvx --from basedpyright basedpyright --level error src tests`,
`npm --prefix frontend run typecheck`.

Ollama — systemd-сервис, override в `/etc/systemd/system/ollama.service.d/override.conf`:
`OLLAMA_CONTEXT_LENGTH=8192`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`.
Модель `qwen3:4b-instruct` (тег `qwen3:8b-instruct` не существует).

`.env` (не в git): `SEARCH_DEVICE=cpu` (BGE-M3 API на процессоре, GPU — LLM),
`WHISPER_COMPUTE_TYPE=int8_float16`, `WHISPER_BATCH_SIZE=4`.

Демо-аккаунты на локальной базе: `demo-teacher@example.com`,
`demo-student@example.com`, пароль `demo-password`. Аккаунт пользователя —
Alexey Yuzkov (teacher).

## Соглашения по коду

Бэкенд как в `~/projects/linkup`: модули `modules/<домен>/{router,service,
schemas,exceptions}.py`, сервисы только `flush`, коммит в `get_session`;
аргументы по одному на строку; structlog с `component=`; тесты —
интеграционные на настоящих Postgres/Redis, модели подменены заглушками
(`tests/support.py`: `FakeEmbedder`, `FakeLLM`, `fake_url_probe`,
`sample_media()` генерирует настоящие крошечные видео через ffmpeg).
Комментарии в коде — по-английски, только «почему».
