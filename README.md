<div align="center">

# Lectio

**Семантический поиск, субтитры и конспекты для видеолекций.**

Загружаете лекцию файлом или ссылкой — сервис расшифровывает речь, строит
смысловой индекс и конспект с оглавлением. Ищете «объяснение теоремы
Пифагора» — получаете фрагменты с таймкодами, даже если таких слов в лекции
не было.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![Whisper](https://img.shields.io/badge/Whisper-large--v3--turbo-412991)

</div>

## Возможности

- загрузка видео (MP4, WebM, MOV, MKV, аудиофайлы) или импорт по ссылке с
  YouTube, Vimeo и других сайтов через yt-dlp;
- автоматическое извлечение аудио и расшифровка Whisper с таймкодами слов;
- субтитры в WebVTT, нарезанные по предложениям, — подключаются к плееру
  одним тегом `<track>`;
- гибридный поиск: векторы BGE-M3 + полнотекстовый поиск PostgreSQL по
  русской морфологии, объединённые Reciprocal Rank Fusion; опционально —
  переранжирование кросс-энкодером;
- поиск по одной лекции, по курсу или по всей базе;
- конспект лекции в Markdown, оглавление с разделами и подразделами,
  ключевые термины с моментом первого упоминания;
- глоссарий: термины всех лекций в одном месте, с определениями из каждой
  лекции и ссылкой на момент; обновляется сам вместе с конспектами;
- тест по лекции: преподаватель составляет его одной кнопкой, студенты
  проходят, а преподаватель видит статистику ответов по каждому вопросу;
- чат «вопрос-ответ» по лекции или курсу со ссылками на фрагменты;
- видео отдаётся с поддержкой HTTP Range — перемотка работает сразу;
- фоновая обработка с этапами и прогрессом, перезапуск после сбоя;
- личный кабинет: роли студента и преподавателя, запись на курсы, прогресс
  просмотра с продолжением с того же места, избранное, закладки с заметками
  на таймкодах, история поиска и дашборд;
- обсуждение под лекцией с привязкой к моменту, лайки, статистика лекции,
  уровни, достижения и рейтинг студентов;
- одно видео обрабатывается один раз: повторная ссылка (в любой форме) или
  тот же файл предлагают открыть готовую лекцию;
- Telegram-бот: ссылка на лекцию, поиск и вопросы прямо в чате;
- видео, превью и аватары — в локальной папке или в S3-совместимом
  хранилище (MinIO в `compose.yaml`);
- полностью офлайн: все модели локальные, LLM — через Ollama;
- один код для Linux + NVIDIA и macOS на Apple Silicon, модели выбираются
  в `.env`.

## Стек

| Область | Технология |
| --- | --- |
| API | FastAPI, Pydantic, Uvicorn |
| Окружение | Python 3.13, uv |
| База данных | PostgreSQL 18, pgvector, async SQLAlchemy, psycopg |
| Миграции | Alembic |
| Очередь | Redis 8 |
| Распознавание речи | faster-whisper (CUDA/CPU), mlx-whisper (Apple Silicon) |
| Эмбеддинги | sentence-transformers, BAAI/bge-m3 |
| Конспекты и чат | любая OpenAI-совместимая LLM: Ollama, LM Studio, vLLM, API |
| Медиа | ffmpeg, yt-dlp |
| Авторизация | JWT access-токены, ротируемые refresh-токены в Redis, Argon2 |
| Логи | structlog, request ID в логах и заголовках |
| Контейнеры | Podman Compose, Dockerfile |

## Как это работает

```text
         POST /lectures            ┌────────────┐
  ─────────────────────────────►   │    API     │──── поиск, чат, субтитры,
         POST /lectures/import     │  FastAPI   │     конспект, видео
                                   └─────┬──────┘
                                         │ задача в Redis
                                   ┌─────▼──────┐
                                   │   Worker   │
                                   └─────┬──────┘
 downloading → extracting_audio → transcribing → indexing → summarizing → ready
    yt-dlp          ffmpeg          Whisper        BGE-M3        LLM
```

1. **Расшифровка.** Whisper выдаёт слова с таймкодами; они собираются в
   реплики по 2–7 секунд по границам предложений — это сегменты субтитров.
2. **Индекс.** Соседние реплики объединяются в окна по ~40 секунд с
   перекрытием в одну реплику, чтобы мысль на стыке не потерялась. Для каждого
   окна хранятся эмбеддинг (HNSW-индекс) и `tsvector` (GIN-индекс).
3. **Поиск.** Запрос ищется двумя способами — по смыслу и по словам с учётом
   морфологии; списки объединяются через RRF. Смысловой поиск находит
   перефразировки, полнотекстовый — точные термины и формулы.
4. **Конспект.** Расшифровка режется на части под контекст модели; по каждой
   LLM пишет краткое изложение, разделы и термины (map), затем изложения
   сводятся в конспект, а разделы — в итоговое оглавление (reduce). Таймкоды
   разделов привязываются к реальным началам фрагментов.

Если LLM недоступна, лекция всё равно становится `ready`: поиск и субтитры
работают, а в `summary.error` будет причина.

## Структура

```text
src/lectio/
├── api/            # зависимости, обработчик ошибок, middleware, роутер
├── core/           # настройки, исключения, очередь задач, файловое хранилище
├── db/             # SQLAlchemy и Redis
├── ml/             # Whisper, эмбеддинги, реранкер, LLM-клиент, нарезка
├── models/         # ORM-модели
├── modules/
│   ├── auth/       # регистрация, вход, токены, роли и права
│   ├── users/      # профиль и аватар
│   ├── courses/
│   ├── lectures/   # загрузка, импорт, статусы, отдача видео
│   ├── transcripts/# сегменты и WebVTT
│   ├── search/     # индексация и гибридный поиск
│   ├── summaries/  # конспект, оглавление, термины
│   ├── qa/         # вопрос-ответ
│   ├── enrollments/# запись на курсы и прогресс по курсу
│   ├── progress/   # позиция просмотра, «продолжить просмотр»
│   ├── favorites/
│   ├── bookmarks/  # закладки с заметками на таймкодах
│   ├── glossary/   # термины всех лекций
│   ├── quizzes/    # тест по лекции, попытки и статистика
│   ├── comments/   # обсуждение под лекцией
│   ├── likes/
│   ├── gamification/# уровни, достижения, рейтинг
│   └── dashboard/  # сводка личного кабинета
├── bot/            # Telegram-бот
├── worker/         # конвейер обработки
└── cli.py          # seed / reindex / resummarize
```

## Запуск

Нужны [uv](https://docs.astral.sh/uv/), ffmpeg, Podman (или Docker) и
[Ollama](https://ollama.com) для конспектов.

```bash
cp .env.example .env
podman compose up -d                  # PostgreSQL, Redis, MinIO
uv sync
uv run alembic upgrade head
ollama pull qwen3:4b-instruct
```

В двух терминалах:

```bash
uv run uvicorn lectio.main:app --reload
```

```bash
uv run python -m lectio.worker
```

Документация API: http://localhost:8000/docs. Модели скачиваются с Hugging Face
при первом запуске (Whisper turbo ~1.6 ГБ, BGE-M3 ~2.3 ГБ).

API и воркер запускаются на хосте, а не в контейнере, чтобы модели работали на
GPU: в контейнере на Linux для этого нужен nvidia-container-toolkit, а на
macOS Metal из контейнера недоступен вовсе.

### Linux + NVIDIA

Настройки по умолчанию рассчитаны на это. torch ставится с CUDA 12.6, и
CTranslate2 использует те же библиотеки cuBLAS/cuDNN.

На картах с 6 ГБ: `WHISPER_COMPUTE_TYPE=int8_float16`, `WHISPER_BATCH_SIZE=4`,
LLM на 4B. Воркер выгружает Whisper и эмбеддер перед этапом конспекта
(`RELEASE_MODELS_BETWEEN_STAGES=true`), чтобы освободить память для Ollama,
а перед расшифровкой и индексацией сам просит Ollama выгрузить модель, которую
мог оставить в памяти чат.
API держит свой экземпляр BGE-M3 для запросов; `SEARCH_DEVICE=cpu` убирает
его с видеокарты: поиск медленнее на ~40 мс, зато LLM помещается на GPU
целиком и работает почти вдвое быстрее (на 1660 Super — 68 против 39
токенов в секунду). Для Ollama на маленькой карте полезны
`OLLAMA_FLASH_ATTENTION=1` и `OLLAMA_KV_CACHE_TYPE=q8_0` — кеш контекста
занимает вдвое меньше.

### macOS на Apple Silicon

```env
WHISPER_BACKEND=mlx
WHISPER_MODEL=large-v3-turbo        # или large-v3
WHISPER_COMPUTE_TYPE=default
WHISPER_BATCH_SIZE=8
RELEASE_MODELS_BETWEEN_STAGES=false
LLM_MODEL=qwen3:8b                  # с 16 ГБ памяти; модели 14B уже не влезут
LLM_NO_THINK=true                   # qwen3:8b рассуждает вслух, это отключает
LLM_PART_CHARS=20000                # если увеличили контекст Ollama
```

Whisper работает через MLX, эмбеддинги — через MPS. Podman на macOS запускает
контейнеры в виртуальной машине: `podman machine init && podman machine start`.

Чтобы Ollama принимала длинные части расшифровки, поднимите контекст:
`OLLAMA_CONTEXT_LENGTH=16384 ollama serve`.

### Telegram-бот

```bash
uv run python -m lectio.bot
```

Нужен `TELEGRAM_BOT_TOKEN` в `.env` (токен от @BotFather) и запущенный
воркер. Бот принимает ссылку на лекцию и присылает конспект с оглавлением,
когда обработка закончится; вопрос со знаком «?» — ответ по текущей лекции
со ссылками на моменты; любой другой текст — поиск по всем лекциям.
Команды: `/lectures`, `/search`, `/ask`, `/all`. Ссылки ведут на
`PUBLIC_WEB_URL`.

### Хранилище видео

По умолчанию (`STORAGE_BACKEND=local`) видео, превью и аватары лежат в
`STORAGE_DIR`. С `STORAGE_BACKEND=s3` готовые файлы уезжают в бакет
S3-совместимого хранилища (MinIO из `compose.yaml`, консоль —
http://localhost:9001), а API отвечает редиректом на подписанную ссылку:
перемотку видео отдаёт сам бакет. Пока лекция обрабатывается, видео
отдаётся с диска; после обработки воркер переносит его в бакет и чистит
локальную папку.

Перенести уже обработанные лекции и аватары с диска в бакет:

```bash
STORAGE_BACKEND=s3 uv run lectio move-storage
```

Официальные образы MinIO больше не публикуются, в compose — поддерживаемая
сообществом сборка `pgsty/minio`; подойдёт любое S3-хранилище.

### Полностью в контейнерах

```bash
podman compose --profile full up -d --build
```

Поднимает API, воркер и миграции; модели работают на CPU, LLM ищется на
хосте (`host.containers.internal:11434`). Медленно, но без установки Python.

## Демо-данные

Файл со ссылками, по одной на строку, `URL | Название` (название
необязательно):

```text
https://www.youtube.com/watch?v=IzihUqWMg3g | Доказательство теоремы Пифагора
```

```bash
uv run lectio seed lectures.txt --course "Геометрия"
uv run lectio resummarize     # перегенерировать конспекты (например, после смены LLM)
uv run lectio reindex         # пересчитать эмбеддинги
```

База через git не переносится — на новой машине прогоните `seed` заново.

Для демо на локальной базе заведены два аккаунта с паролем `demo-password`:
`demo-teacher@example.com` (преподаватель) и `demo-student@example.com`
(студент). На новой машине их нужно зарегистрировать заново через
`POST /auth/register`.

## Пользователи и права

Две роли, выбираются при регистрации: **студент** (по умолчанию) и
**преподаватель**.

- Курсы и лекции создают только преподаватели и становятся их владельцами;
  менять и удалять их может только владелец. Лекции и курсы без владельца
  (импортированные через `lectio seed`) доступны всем преподавателям.
- Просмотр, поиск, субтитры, конспекты и чат открыты без входа: `<video>` и
  `<track>` не умеют отправлять заголовок `Authorization`.
- Личные данные — прогресс, избранное, закладки, история поиска — требуют
  входа. Поиск работает и анонимно, а для вошедшего пользователя запрос
  сохраняется в историю.

Access-токен передаётся в заголовке `Authorization: Bearer …` и живёт 30
минут. Refresh-токен лежит в HttpOnly-cookie на пути `/api/v1/auth`;
`POST /auth/refresh` выдаёт новую пару, старый refresh-токен при этом
перестаёт действовать. Фронту на другом порту нужен `credentials: "include"`.

## API

Подробная справка по контрактам всех ручек, ограничениям и возможностям для
фронтенда: [BACKEND_API.md](BACKEND_API.md).

Все пути с префиксом `/api/v1`. 🔒 — нужен вход, 🎓 — нужна роль
преподавателя.

| Метод | Путь | Что делает |
| --- | --- | --- |
| `POST` | `/auth/register` | регистрация `{email, password, first_name, last_name, role?}` |
| `POST` | `/auth/login` | вход, отдаёт access-токен и ставит refresh-cookie |
| `POST` | `/auth/refresh` | новый access-токен по cookie |
| `POST` | `/auth/logout` | выход на этом устройстве |
| `POST` | `/auth/logout-all` 🔒 | выход на всех устройствах |
| `GET` | `/auth/me` 🔒 | текущий пользователь |
| `PATCH` | `/users/me` 🔒 | изменить имя |
| `PUT/DELETE` | `/users/me/avatar` 🔒 | загрузить (PNG, JPEG, WebP до 5 МБ) или удалить аватар |
| `GET` | `/users/{id}` | публичный профиль, например преподавателя |
| `GET` | `/users/{id}/avatar` | картинка аватара |
| `POST` | `/lectures` 🎓 | загрузить файл (`multipart`: `file`, `title?`, `course_id?`) |
| `POST` | `/lectures/import` 🎓 | импорт по ссылке `{url, title?, course_id?, allow_duplicate?}`; на то же видео — `409 lecture_duplicate` с `lecture_id` |
| `GET` | `/lectures` | список (`course_id`, `owner_id`, `status`, `limit`, `offset`) |
| `GET` | `/lectures/{id}` | лекция со статусом и прогрессом |
| `PATCH` | `/lectures/{id}` 🎓 | переименовать, перенести в курс |
| `DELETE` | `/lectures/{id}` 🎓 | удалить вместе с файлами |
| `POST` | `/lectures/{id}/reprocess` 🎓 | обработать заново |
| `GET` | `/lectures/{id}/video` | видео с поддержкой Range |
| `GET` | `/lectures/{id}/thumbnail` | превью-кадр JPEG |
| `GET` | `/lectures/{id}/segments` | реплики расшифровки с таймкодами |
| `GET` | `/lectures/{id}/subtitles.vtt` | субтитры WebVTT |
| `GET` | `/lectures/{id}/summary` | конспект, оглавление, термины |
| `POST` | `/lectures/{id}/summary` 🎓 | перегенерировать конспект |
| `GET` | `/glossary` | термины всех лекций (`q`, `course_id`) |
| `GET` | `/lectures/{id}/quiz` | тест по лекции |
| `POST` | `/lectures/{id}/quiz` 🎓 | составить тест (языковой моделью) |
| `PUT` | `/lectures/{id}/quiz/attempt` 🔒 | ответы студента, результат с пояснениями |
| `GET` | `/lectures/{id}/quiz/stats` 🎓 | статистика ответов по вопросам |
| `GET` | `/lectures/{id}/stats` | статистика лекции |
| `GET` | `/lectures/{id}/comments` | обсуждение, новые сверху |
| `POST` | `/lectures/{id}/comments` 🔒 | комментарий `{text, position_seconds?}` |
| `DELETE` | `/lectures/{id}/comments/{comment_id}` 🔒 | удалить свой комментарий; преподаватель лекции — любой |
| `PUT/DELETE` | `/lectures/{id}/like` 🔒 | поставить или убрать лайк |
| `GET` | `/me/achievements` 🔒 | уровень, XP и достижения |
| `GET` | `/leaderboard` 🔒 | рейтинг студентов |
| `GET` | `/search?q=` | поиск (`lecture_id`, `course_id`, `limit`) |
| `POST` | `/qa` | вопрос `{question, lecture_id?, course_id?, history?}` |
| `POST` | `/qa/stream` | тот же ответ потоком (SSE): `sources`, затем `delta` по кусочкам, `done` или `error` |
| `GET` | `/courses` | курсы с числом лекций и общей длительностью (`owner_id`) |
| `POST` | `/courses` 🎓 | создать курс |
| `GET` | `/courses/{id}` | курс |
| `DELETE` | `/courses/{id}` 🎓 | удалить курс, лекции остаются без курса |
| `PUT/DELETE` | `/courses/{id}/enrollment` 🔒 | записаться на курс или отписаться |
| `GET` | `/me/courses` 🔒 | мои курсы с прогрессом прохождения |
| `GET/PUT` | `/lectures/{id}/progress` 🔒 | позиция просмотра `{position_seconds, completed?}` |
| `GET` | `/me/continue-watching` 🔒 | недосмотренные лекции |
| `PUT/DELETE` | `/lectures/{id}/favorite` 🔒 | добавить в избранное или убрать |
| `GET` | `/me/favorites` 🔒 | избранные лекции |
| `POST/GET` | `/lectures/{id}/bookmarks` 🔒 | закладки в лекции `{position_seconds, note?}` |
| `PATCH/DELETE` | `/bookmarks/{id}` 🔒 | изменить или удалить закладку |
| `GET` | `/me/bookmarks` 🔒 | все закладки |
| `GET/DELETE` | `/me/search-history` 🔒 | недавние запросы, очистка |
| `GET` | `/me/dashboard` 🔒 | сводка: статистика, «продолжить», недавние поиски |
| `GET` | `/lectures/{id}/me` 🔒 | всё о лекции для текущего пользователя одним запросом |

Статусы лекции: `pending → downloading → extracting_audio → transcribing →
indexing → summarizing → ready` или `failed` (причина в `error`). `progress` —
доля выполнения текущего этапа от 0 до 1. Расшифровка и поиск доступны уже на
этапе `summarizing`.

Перед постановкой в очередь загрузка проверяется: файл через ffprobe (читается
ли, есть ли звук, не длиннее 4 часов), ссылка через yt-dlp без скачивания
(видео доступно, это не трансляция). Отказ приходит сразу со статусом 422 и
машинным кодом в поле `code`: `media_unreadable`, `media_no_audio`,
`media_too_long`, `url_unavailable`, `url_live_stream`; по ссылке название и
длительность известны сразу, ещё до скачивания.

Прогресс просмотра стоит отправлять каждые несколько секунд во время
воспроизведения и на паузе. Лекция считается просмотренной, когда позиция
доходит до 90%; перемотка назад отметку не снимает, снять её можно явно
через `completed: false`.

`highlight` в результатах поиска — HTML, где совпавшие слова обёрнуты в
`<mark>`; остальной текст экранирован.

## Тесты

```bash
podman compose -f compose.test.yaml up -d
uv run pytest
```

Интеграционные тесты используют настоящие PostgreSQL с pgvector, Redis и MinIO, а
модели заменены детерминированными заглушками — скачивать ничего не нужно.

```bash
uv run ruff check .
uv run ruff format --check .
```
