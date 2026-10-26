from functools import cache
from threading import Lock

import structlog

from lectio.core.config import Device, get_settings
from lectio.ml.device import free_accelerator_memory, resolve_device

log = structlog.get_logger(
    component="ml.embedder",
)


class Embedder:
    def __init__(self, requested_device: Device) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        device = resolve_device(requested_device)

        # Loading straight in fp16 halves VRAM; converting after loading
        # leaves the fp32 copy in the CUDA allocator cache.
        self._model = SentenceTransformer(
            settings.embedding_model,
            device=device,
            model_kwargs=({"dtype": torch.float16} if device != "cpu" else None),
        )

        self._batch_size = settings.embedding_batch_size
        # Inference is called from worker threads; one batch at a time keeps
        # memory usage predictable.
        self._lock = Lock()

        log.info(
            "embedder_loaded",
            model=settings.embedding_model,
            device=device,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        with self._lock:
            vectors = self._model.encode(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


@cache
def get_embedder() -> Embedder:
    """Embedder for indexing transcripts in the worker."""
    settings = get_settings()

    return Embedder(settings.embedding_device or settings.device)


@cache
def get_query_embedder() -> Embedder:
    """Embedder for search queries in the API."""
    settings = get_settings()

    return Embedder(
        settings.search_device or settings.embedding_device or settings.device,
    )


def release_embedder() -> None:
    get_embedder.cache_clear()
    free_accelerator_memory()
