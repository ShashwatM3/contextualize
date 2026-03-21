"""Abstract base for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Interface that all LLM backends must implement.

    Implementations are responsible for retry logic, timeout handling,
    and returning well-formed text or raising clear exceptions.
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> str:
        """Generate free-form text from the model.

        Returns
        -------
        str
            Raw text response from the model.

        Raises
        ------
        ProviderError
            On any non-recoverable failure after retries.
        """

    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Generate a JSON object from the model.

        The provider must parse the response and return a Python dict.
        If the model emits malformed JSON the provider should attempt
        one deterministic repair pass before raising.

        Returns
        -------
        dict
            Parsed JSON response.

        Raises
        ------
        ProviderError
            On any non-recoverable failure after retries.
        JSONRepairError
            If JSON repair also fails.
        """


class ProviderError(Exception):
    """Raised when an LLM provider encounters a non-recoverable error."""


class JSONRepairError(ProviderError):
    """Raised when the provider cannot repair malformed JSON output."""
