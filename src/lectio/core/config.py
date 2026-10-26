from functools import cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Device = Literal["auto", "cuda", "mps", "cpu"]


class Settings(BaseSettings):
    app_name: str = "Lectio"
    debug: bool = False

    database_url: str
    redis_url: str
    sql_echo: bool = False

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    storage_dir: Path = Path("storage")
    max_upload_mb: int = 4096
    download_max_height: int = 720

    device: Device = "auto"
    # Loaded once at API startup so the first search is not slow.
    preload_models: bool = True
    # Free GPU memory between pipeline stages; needed on small cards where
    # Whisper, the embedder and a local LLM do not fit at the same time.
    release_models_between_stages: bool = True

    whisper_backend: Literal["faster_whisper", "mlx"] = "faster_whisper"
    whisper_model: str = "large-v3-turbo"
    whisper_compute_type: str = "default"
    whisper_batch_size: int = 8
    whisper_language: str | None = None

    embedding_model: str = "BAAI/bge-m3"
    # Device for indexing in the worker.
    embedding_device: Device | None = None
    # Device for query embeddings and reranking in the API. A single query
    # takes ~100 ms on a CPU, and keeping the API off a small GPU leaves the
    # whole card to the LLM.
    search_device: Device | None = None
    embedding_batch_size: int = 16

    reranker_model: str | None = None

    chunk_target_seconds: float = 40.0
    chunk_max_seconds: float = 70.0

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen3:4b-instruct"
    llm_timeout_seconds: float = 300.0
    llm_temperature: float = 0.2
    # Appends Qwen3's /no_think switch: hybrid models answer without a long
    # reasoning preamble, several times faster.
    llm_no_think: bool = False
    # Transcript characters sent per summarization call; raise it for models
    # with a long context window.
    llm_part_chars: int = 9000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
