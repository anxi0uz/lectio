import json
import re
from functools import cache
from typing import Any

import httpx
import structlog
from openai import APIError, AsyncOpenAI

from lectio.core.config import get_settings
from lectio.core.exceptions import ServiceUnavailableError

log = structlog.get_logger(
    component="ml.llm",
)

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class LLMUnavailableError(ServiceUnavailableError):
    default_detail = "Language model is unavailable"


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()

        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
        )
        self._base_url = settings.llm_base_url.rstrip("/")
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._system_suffix = "\n/no_think" if settings.llm_no_think else ""

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        json_mode: bool = False,
    ) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system + self._system_suffix},
                    *messages,  # pyright: ignore[reportArgumentType]
                ],
                temperature=self._temperature,
                response_format=(
                    {"type": "json_object"} if json_mode else {"type": "text"}
                ),
            )
        except APIError as error:
            log.warning(
                "llm_request_failed",
                model=self._model,
                error=str(error),
            )
            raise LLMUnavailableError(
                f"Language model request failed: {error}",
            ) from error
        except OSError as error:
            raise LLMUnavailableError from error

        content = response.choices[0].message.content or ""

        # Reasoning models put their chain of thought inline.
        return THINK_BLOCK.sub("", content).strip()

    async def complete_json(
        self,
        system: str,
        user: str,
    ) -> dict[str, Any]:
        raw = await self.complete(
            system,
            [{"role": "user", "content": user}],
            json_mode=True,
        )

        try:
            payload = json.loads(JSON_FENCE.sub("", raw))
        except json.JSONDecodeError as error:
            raise LLMUnavailableError(
                "Language model returned invalid JSON",
            ) from error

        if not isinstance(payload, dict):
            raise LLMUnavailableError(
                "Language model returned unexpected JSON",
            )

        return payload

    async def unload(self) -> None:
        """Ask Ollama to free the model's GPU memory right away.

        Ollama keeps a model loaded for minutes after a request; on a small
        card that leaves no room for Whisper. Other servers do not have this
        endpoint, and a failure here is harmless.
        """
        native_url = self._base_url.removesuffix("/v1") + "/api/generate"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    native_url,
                    json={"model": self._model, "keep_alive": 0},
                )
        except httpx.HTTPError as error:
            log.debug("llm_unload_skipped", error=str(error))
            return

        log.info(
            "llm_unloaded",
            model=self._model,
            status_code=response.status_code,
        )

    async def close(self) -> None:
        await self._client.close()


@cache
def get_llm() -> LLMClient:
    return LLMClient()


async def close_llm() -> None:
    if get_llm.cache_info().currsize:
        await get_llm().close()

    get_llm.cache_clear()
