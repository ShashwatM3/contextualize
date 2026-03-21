"""Google Gemini LLM provider using the official ``google-genai`` SDK."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from google import genai
from google.genai import types as genai_types

from contextualize_docs.config import AppConfig
from contextualize_docs.logging_config import get_logger
from contextualize_docs.providers.base import JSONRepairError, LLMProvider, ProviderError

logger = get_logger("providers.gemini")


def _normalize_model_name(raw_model: str) -> str:
    """Convert gateway-style Gemini model ids into SDK-compatible names."""
    return raw_model.split("/", 1)[-1] if "/" in raw_model else raw_model


def _extract_json(text: str) -> str:
    """Strip markdown fences and leading/trailing noise to isolate JSON."""
    # Remove ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1)
    text = text.strip()
    # Ensure we start at the first { or [
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            text = text[i:]
            break
    return text


def _try_repair_json(raw: str) -> dict[str, Any]:
    """Attempt basic deterministic repairs on malformed JSON.

    Handles:
    - trailing commas before } or ]
    - single quotes → double quotes (outside of values)
    - truncated tail — try closing open braces/brackets
    """
    # Remove trailing commas
    repaired = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Try closing unclosed braces/brackets
    opens = repaired.count("{") - repaired.count("}")
    repaired += "}" * max(opens, 0)
    opens_sq = repaired.count("[") - repaired.count("]")
    repaired += "]" * max(opens_sq, 0)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise JSONRepairError(f"Deterministic JSON repair failed: {exc}") from exc


class GeminiProvider(LLMProvider):
    """Concrete provider backed by Google Gemini via ``google-genai``."""

    def __init__(self, config: AppConfig) -> None:
        if not config.gemini_api_key:
            raise ProviderError(
                "GEMINI_API_KEY is not set. Add it to .env.local or export it."
            )
        self._client = genai.Client(api_key=config.gemini_api_key)
        self._model = _normalize_model_name(config.default_llm_model)
        self._temperature = config.llm_temperature
        self._max_retries = config.llm_max_retries
        self._timeout = config.llm_timeout_seconds

    def set_model(self, raw_model: str) -> None:
        """Update the SDK model, accepting either raw or normalized ids."""
        self._model = _normalize_model_name(raw_model)

    # --------------------------------------------------------------------- #
    # Internal helpers                                                       #
    # --------------------------------------------------------------------- #

    async def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None,
    ) -> str:
        """Call Gemini with exponential-backoff retries."""
        temp = temperature if temperature is not None else self._temperature
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.models.generate_content,
                        model=self._model,
                        contents=user_prompt,
                        config=genai_types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=temp,
                        ),
                    ),
                    timeout=self._timeout,
                )
                text = response.text
                if text is None:
                    raise ProviderError("Gemini returned an empty response.")
                return text

            except asyncio.TimeoutError:
                last_exc = ProviderError(
                    f"Gemini request timed out after {self._timeout}s (attempt {attempt})"
                )
                logger.warning("%s", last_exc)
            except ProviderError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("Gemini API error (attempt %d/%d): %s", attempt, self._max_retries, exc)

            # Exponential backoff: 2s, 4s, 8s …
            if attempt < self._max_retries:
                await asyncio.sleep(2 ** attempt)

        raise ProviderError(f"Gemini failed after {self._max_retries} retries: {last_exc}")

    # --------------------------------------------------------------------- #
    # Public API                                                             #
    # --------------------------------------------------------------------- #

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

        # First parse attempt
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            logger.warning("Initial JSON parse failed, attempting deterministic repair.")

        # Deterministic repair
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
            raise JSONRepairError(
                f"LLM JSON self-repair also failed: {exc}"
            ) from exc
