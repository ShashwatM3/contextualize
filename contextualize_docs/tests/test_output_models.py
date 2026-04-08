"""Tests for output model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contextualize_docs.models.output_models import (
    ContextCard,
    IndexFile,
    ManifestFile,
    MinimalExample,
    RelevantAPI,
    RunSummary,
    SourceEvidence,
)


def _make_card(**overrides) -> ContextCard:
    """Helper to create a valid ContextCard with sensible defaults."""
    defaults = {
        "library": "zod",
        "normalized_name": "zod",
        "version": "3.24.2",
        "task_focus": "Add password reset flow",
        "purpose_in_repo": "Used for form validation.",
        "why_relevant_for_task": "Validates reset email input.",
        "first_working_code_goal": "A simple string validation.",
        "first_step_for_agent": "Import z from zod.",
        "architecture_recommendation": "Use a central validators file.",
        "repo_pattern_status": {"has_repo_evidence": True, "message": ""},
        "integration_strategy_when_no_repo_pattern": "",
        "implementation_plan": ["Step 1", "Step 2", "Step 3"],
        "mvp_boundary": "Stop when validation passes.",
        "quality_upgrade_path": ["Add async parsing"],
        "core_apis_for_task": [{"name": "safeParse", "usage_pattern": "z.string().safeParse(x)", "why_core": "Core"}],
        "optional_apis_for_task": [{"name": "parse", "why_optional": "Throws errors"}],
        "relevant_apis": [],
        "repo_patterns": [],
        "minimal_examples": [],
        "do_not_use": ["Yup"],
        "do_not_build_yet": ["Complex async validation"],
        "common_failure_modes_for_this_task": ["Forgot to check success false"],
        "decision_shortcuts": ["If x then y"],
        "success_criteria": ["Email is validated"],
        "gotchas": [],
        "rules_for_agent": [],
        "source_evidence": {"docs_chunk_ids": [], "repo_files": [], "source_urls": []},
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return ContextCard.model_validate(defaults)


class TestContextCard:
    def test_valid_minimal(self):
        card = _make_card()
        assert card.library == "zod"
        assert card.confidence == 0.9

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            _make_card(confidence=1.5)
        with pytest.raises(ValidationError):
            _make_card(confidence=-0.1)

    def test_purpose_in_repo_max_length(self):
        with pytest.raises(ValidationError):
            _make_card(purpose_in_repo="x" * 301)

    def test_why_relevant_max_length(self):
        with pytest.raises(ValidationError):
            _make_card(why_relevant_for_task="x" * 301)

    def test_with_apis(self):
        api = RelevantAPI(
            name="safeParse",
            when_to_use="Validate without throwing",
            required_args=["data"],
        )
        card = _make_card(relevant_apis=[api.model_dump()])
        assert len(card.relevant_apis) == 1
        assert card.relevant_apis[0].name == "safeParse"

    def test_with_examples(self):
        ex = MinimalExample(title="Basic", code="z.string().email()")
        card = _make_card(minimal_examples=[ex.model_dump()])
        assert card.minimal_examples[0].code == "z.string().email()"


class TestRunSummary:
    def test_valid(self):
        s = RunSummary(
            success=True,
            dependencies_processed=2,
            cards_generated=2,
            duration_seconds=1.5,
        )
        assert s.success is True
        assert s.skipped_dependencies == []

    def test_failure(self):
        s = RunSummary(
            success=False,
            dependencies_processed=0,
            cards_generated=0,
            duration_seconds=0.1,
            validation_warnings=["No deps"],
        )
        assert s.success is False
        assert len(s.validation_warnings) == 1


class TestIndexFile:
    def test_valid(self):
        idx = IndexFile(
            task_id="t1",
            task_title="Test",
            generated_at="2025-01-01T00:00:00Z",
        )
        assert idx.cards == []


class TestManifestFile:
    def test_valid(self):
        m = ManifestFile(
            generated_at="2025-01-01T00:00:00Z",
            llm_provider="openai",
            llm_model="gpt-4.1-mini",
            input_hash="abc123",
            card_count=2,
            dependency_count=2,
            warning_count=0,
        )
        assert m.version == "1.0.0"
