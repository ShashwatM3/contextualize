"""CLI regression tests."""

from __future__ import annotations

from contextualize_docs.config import AppConfig
from contextualize_docs.providers.openai_provider import OpenAIProvider


def test_openai_provider_set_model_uses_exact_model_id() -> None:
    provider = OpenAIProvider(AppConfig(openai_api_key="test-key"))

    provider.set_model("gpt-4.1-mini")

    assert provider._model == "gpt-4.1-mini"  # noqa: SLF001
