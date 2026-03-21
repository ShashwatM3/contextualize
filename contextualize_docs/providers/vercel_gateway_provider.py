"""Vercel AI Gateway provider — OpenAI-compatible endpoint for Gemini models.

The Vercel AI Gateway exposes an OpenAI-compatible Chat Completions API:
    POST https://ai-gateway.vercel.sh/v1/chat/completions
    Authorization: Bearer <VERCEL_AI_GATEWAY_KEY>
    Model: "google/gemini-2.5-flash" (or any other supported model)

This lets us call Gemini without the google-genai SDK, using a single
unified gateway that handles auth, rate-limiting, and routing.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from contextualize_docs.config import AppConfig
from contextualize_docs.logging_config import get_logger
from contextualize_docs.providers.base import JSONRepairError, LLMProvider, ProviderError

logger = get_logger("providers.vercel_gateway")

_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
_CHAT_ENDPOINT = f"{_GATEWAY_BASE_URL}/chat/completions"


def _extract_json(text: str) -> str:
    """Strip markdown fences and leading/trailing noise to isolate JSON."""
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
    """Attempt basic deterministic repairs on malformed JSON."""
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


class VercelGatewayProvider(LLMProvider):
    """LLM provider backed by the Vercel AI Gateway (OpenAI-compatible)."""

    def __init__(self, config: AppConfig) -> None:
        if not config.vercel_gateway_key:
            raise ProviderError(
                "VERCEL_AI_GATEWAY_KEY is not set. Add it to .env.local or export it."
            )
        self._api_key = config.vercel_gateway_key
        self._model = config.default_llm_model  # e.g. "google/gemini-2.5-flash"
        self._temperature = config.llm_temperature
        self._max_retries = config.llm_max_retries
        self._timeout = config.llm_timeout_seconds

    def set_model(self, raw_model: str) -> None:
        """Update the gateway model id."""
        self._model = raw_model

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> dict[str, Any]:
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
        """POST to Vercel AI Gateway with exponential-backoff retries."""
        temp = temperature if temperature is not None else self._temperature
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(
                        _CHAT_ENDPOINT,
                        headers=self._build_headers(),
                        json=self._build_body(system_prompt, user_prompt, temp),
                    )

                    if response.status_code != 200:
                        raise ProviderError(
                            f"Vercel AI Gateway returned HTTP {response.status_code}: {response.text[:500]}"
                        )

                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if not content:
                        raise ProviderError("Vercel AI Gateway returned an empty response content.")

                    logger.debug("Gateway call succeeded (attempt %d).", attempt)
                    return content

                except ProviderError:
                    raise
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exc = exc
                    logger.warning(
                        "Gateway network error (attempt %d/%d): %s", attempt, self._max_retries, exc
                    )
                except (KeyError, IndexError, json.JSONDecodeError) as exc:
                    raise ProviderError(f"Unexpected response shape from gateway: {exc}") from exc
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    logger.warning(
                        "Gateway error (attempt %d/%d): %s", attempt, self._max_retries, exc
                    )

                if attempt < self._max_retries:
                    await asyncio.sleep(2 ** attempt)

        raise ProviderError(
            f"Vercel AI Gateway failed after {self._max_retries} retries: {last_exc}"
        )

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

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

        # LLM self-repair pass
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
