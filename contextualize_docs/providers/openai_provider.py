"""OpenAI provider using Chat Completions API."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from contextualize_docs.config import AppConfig
from contextualize_docs.logging_config import get_logger
from contextualize_docs.providers.base import JSONRepairError, LLMProvider, ProviderError

logger = get_logger("providers.openai")

_OPENAI_CHAT_ENDPOINT = "https://api.openai.com/v1/chat/completions"


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1)
    text = text.strip()
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            text = text[i:]
            break
    return text


def _try_repair_json(raw: str) -> dict[str, Any]:
    repaired = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    opens = repaired.count("{") - repaired.count("}")
    repaired += "}" * max(opens, 0)
    opens_sq = repaired.count("[") - repaired.count("]")
    repaired += "]" * max(opens_sq, 0)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise JSONRepairError(f"Deterministic JSON repair failed: {exc}") from exc


class OpenAIProvider(LLMProvider):
    """LLM provider backed by OpenAI Chat Completions."""

    def __init__(self, config: AppConfig) -> None:
        if not config.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not set. Add it to .env.local or export it.")
        self._api_key = config.openai_api_key
        self._model = config.default_llm_model
        self._temperature = config.llm_temperature
        self._max_retries = config.llm_max_retries
        self._timeout = config.llm_timeout_seconds

    def set_model(self, raw_model: str) -> None:
        self._model = raw_model

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(self, system_prompt: str, user_prompt: str, temperature: float) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

    async def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None,
    ) -> str:
        temp = temperature if temperature is not None else self._temperature
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(
                        _OPENAI_CHAT_ENDPOINT,
                        headers=self._build_headers(),
                        json=self._build_body(system_prompt, user_prompt, temp),
                    )
                    if response.status_code != 200:
                        raise ProviderError(
                            f"OpenAI returned HTTP {response.status_code}: {response.text[:500]}"
                        )

                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if not content:
                        raise ProviderError("OpenAI returned an empty response content.")
                    return content

                except ProviderError:
                    raise
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exc = exc
                    logger.warning("OpenAI network error (attempt %d/%d): %s", attempt, self._max_retries, exc)
                except (KeyError, IndexError, json.JSONDecodeError) as exc:
                    raise ProviderError(f"Unexpected response shape from OpenAI: {exc}") from exc
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    logger.warning("OpenAI error (attempt %d/%d): %s", attempt, self._max_retries, exc)

                if attempt < self._max_retries:
                    await asyncio.sleep(2 ** attempt)

        raise ProviderError(f"OpenAI failed after {self._max_retries} retries: {last_exc}")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> str:
        return await self._call_with_retry(system_prompt, user_prompt, temperature)

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        raw_text = await self._call_with_retry(system_prompt, user_prompt, temperature)
        extracted = _extract_json(raw_text)
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            logger.warning("Initial JSON parse failed, attempting deterministic repair.")

        try:
            return _try_repair_json(extracted)
        except JSONRepairError:
            logger.warning("Deterministic repair failed, requesting LLM self-repair.")

        repair_prompt = (
            "The following text was supposed to be valid JSON but is malformed. "
            "Return ONLY the repaired, valid JSON with no explanation:\n\n"
            f"{extracted}"
        )
        repair_text = await self._call_with_retry(
            "You are a JSON repair tool. Output only valid JSON.",
            repair_prompt,
            temperature,
        )
        repair_extracted = _extract_json(repair_text)
        try:
            return json.loads(repair_extracted)
        except json.JSONDecodeError as exc:
            raise JSONRepairError(f"LLM JSON self-repair also failed: {exc}") from exc
