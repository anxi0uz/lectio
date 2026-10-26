from functools import cache
from threading import Lock

import structlog

from lectio.core.config import get_settings
from lectio.ml.device import resolve_device

log = structlog.get_logger(
    component="ml.reranker",
)


class Reranker:
    def __init__(self, model_name: str) -> None:
        import torch
        from sentence_transformers import CrossEncoder

        settings = get_settings()
        device = resolve_device(
            settings.search_device or settings.embedding_device or settings.device,
        )

        self._model = CrossEncoder(
            model_name,
            device=device,
            model_kwargs=({"dtype": torch.float16} if device != "cpu" else None),
        )

        self._lock = Lock()

        log.info(
            "reranker_loaded",
            model=model_name,
            device=device,
        )

    def score(
        self,
        query: str,
        texts: list[str],
    ) -> list[float]:
        if not texts:
            return []

        with self._lock:
            scores = self._model.predict(
                [(query, text) for text in texts],
                show_progress_bar=False,
            )

        return [float(score) for score in scores]


@cache
def get_reranker() -> Reranker | None:
    model_name = get_settings().reranker_model

    if not model_name:
        return None

    return Reranker(model_name)
