"""Shared test fixtures and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contextualize_docs.config import AppConfig
from contextualize_docs.models.input_models import ContextualizeInput

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_input_path() -> Path:
    return FIXTURES_DIR / "sample_input.json"


@pytest.fixture()
def sample_input_json(sample_input_path: Path) -> dict:
    return json.loads(sample_input_path.read_text(encoding="utf-8"))


@pytest.fixture()
def sample_payload(sample_input_json: dict) -> ContextualizeInput:
    return ContextualizeInput.model_validate(sample_input_json)


@pytest.fixture()
def app_config() -> AppConfig:
    """Return a config that does NOT require a real API key."""
    return AppConfig(openai_api_key="test-key-not-real")
