"""Integration test — full pipeline with mocked Gemini provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from contextualize_docs.config import AppConfig
from contextualize_docs.models.input_models import ContextualizeInput
from contextualize_docs.models.output_models import ContextCard
from contextualize_docs.pipeline.orchestrator import run_pipeline
from contextualize_docs.providers.base import LLMProvider


# ------------------------------------------------------------------ #
# Mock provider that returns realistic structured output              #
# ------------------------------------------------------------------ #

class MockGeminiProvider(LLMProvider):
    """Returns a pre-built card JSON for any request."""

    def __init__(self, card_overrides: dict[str, Any] | None = None):
        self._overrides = card_overrides or {}
        self.call_count = 0

    async def generate(self, system_prompt: str, user_prompt: str, *, temperature: float | None = None) -> str:
        raise NotImplementedError("Not used in card generation path")

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        self.call_count += 1
        base = {
            "library": "zod",
            "normalized_name": "zod",
            "version": "3.24.2",
            "task_focus": "Add password reset flow",
            "purpose_in_repo": "Used for form validation in this repo.",
            "why_relevant_for_task": "Validates the password reset email input.",
            "relevant_apis": [
                {
                    "name": "safeParse",
                    "full_signature": "schema.safeParse(data)",
                    "when_to_use": "Validate without throwing.",
                    "required_args": ["data"],
                    "optional_args": [],
                    "return_shape": "{ success: boolean, data?, error? }",
                    "constraints": [],
                    "pitfalls": ["Do not use .parse() in server actions without error handling."],
                }
            ],
            "repo_patterns": [
                "Use existing validators in lib/validators/auth.ts.",
                "Prefer safeParse over parse.",
            ],
            "minimal_examples": [
                {
                    "title": "Validate email",
                    "code": "const result = resetSchema.safeParse({ email });",
                }
            ],
            "gotchas": ["safeParse returns { success: false } instead of throwing."],
            "rules_for_agent": [
                "Reuse resetSchema from lib/validators/auth.ts.",
                "Do not introduce Yup.",
            ],
            "source_evidence": {
                "docs_chunk_ids": ["zod_001"],
                "repo_files": ["lib/validators/auth.ts"],
                "source_urls": ["https://zod.dev"],
            },
            "confidence": 0.92,
        }
        base.update(self._overrides)
        return base


# ------------------------------------------------------------------ #
# Tests                                                               #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_full_pipeline_with_mock(sample_payload: ContextualizeInput, tmp_path: Path):
    """Run the entire pipeline with a mock provider and verify output."""
    config = AppConfig(gemini_api_key="test-key")
    provider = MockGeminiProvider()

    summary = await run_pipeline(
        payload=sample_payload,
        provider=provider,
        output_dir=tmp_path,
        config=config,
    )

    assert summary.success is True
    assert summary.cards_generated >= 1
    assert provider.call_count >= 1

    # Verify artifacts on disk
    docs_dir = tmp_path / "docs"
    assert docs_dir.is_dir()

    index = json.loads((docs_dir / "index.json").read_text())
    assert index["task_id"] == "task_001"
    assert len(index["cards"]) >= 1

    manifest = json.loads((docs_dir / "manifest.json").read_text())
    assert manifest["card_count"] >= 1

    run_sum = json.loads((docs_dir / "run_summary.json").read_text())
    assert run_sum["success"] is True

    # Verify at least one card file exists and validates
    cards_dir = docs_dir / "cards"
    card_files = list(cards_dir.glob("*.json"))
    assert len(card_files) >= 1
    for card_file in card_files:
        card_data = json.loads(card_file.read_text())
        card = ContextCard.model_validate(card_data)
        assert card.confidence > 0


@pytest.mark.asyncio
async def test_pipeline_skips_low_confidence_deps(tmp_path: Path):
    """Dependencies with confidence below threshold should be skipped."""
    from contextualize_docs.models.input_models import (
        Dependency,
        DocsChunk,
        RepoContext,
        TaskInfo,
    )

    payload = ContextualizeInput(
        task=TaskInfo(id="t1", title="T", description="d", goal="g"),
        repo_context=RepoContext(project_name="p", languages=["ts"]),
        dependencies=[
            Dependency(name="low-lib", confidence=0.1),
        ],
        docs_context=[
            DocsChunk(library="low-lib", content="some docs"),
        ],
    )

    config = AppConfig(gemini_api_key="test", min_confidence_threshold=0.5)
    provider = MockGeminiProvider()

    summary = await run_pipeline(payload, provider, tmp_path, config)

    assert summary.cards_generated == 0
    assert "low-lib" in summary.skipped_dependencies
    assert provider.call_count == 0  # should not even call LLM


@pytest.mark.asyncio
async def test_pipeline_respects_max_cards(sample_payload: ContextualizeInput, tmp_path: Path):
    """Pipeline should stop generating after reaching max_cards."""
    # Override max_cards to 1
    payload = sample_payload.model_copy(
        update={"generation_config": sample_payload.generation_config.model_copy(update={"max_cards": 1})}
    )

    config = AppConfig(gemini_api_key="test")
    provider = MockGeminiProvider()

    summary = await run_pipeline(payload, provider, tmp_path, config)

    assert summary.cards_generated == 1
    assert provider.call_count == 1
