FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 \
    /uv \
    /uvx \
    /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_NO_DEV=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync \
    --locked \
    --no-install-project

COPY alembic.ini ./
COPY src ./src

RUN uv sync \
    --locked

RUN useradd \
    --system \
    --uid 10001 \
    --create-home \
    appuser \
    && mkdir -p /data \
    && chown appuser /data

USER appuser

EXPOSE 8000

CMD ["uvicorn", "lectio.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
