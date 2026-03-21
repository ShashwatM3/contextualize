"""CLI regression tests."""

from __future__ import annotations

from contextualize_docs.config import AppConfig
from contextualize_docs.providers.gemini_provider import GeminiProvider
from contextualize_docs.providers.vercel_gateway_provider import VercelGatewayProvider


def test_gemini_provider_set_model_normalizes_gateway_prefix() -> None:
    provider = GeminiProvider(AppConfig(gemini_api_key="test-key"))

    provider.set_model("google/gemini-2.5-flash")

    assert provider._model == "gemini-2.5-flash"  # noqa: SLF001


def test_vercel_provider_set_model_preserves_gateway_model_id() -> None:
    provider = VercelGatewayProvider(AppConfig(vercel_gateway_key="test-key"))

    provider.set_model("google/gemini-2.5-flash")

    assert provider._model == "google/gemini-2.5-flash"  # noqa: SLF001
