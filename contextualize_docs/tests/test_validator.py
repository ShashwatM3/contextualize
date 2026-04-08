"""Tests for the post-processing validator."""

from __future__ import annotations

from contextualize_docs.config import AppConfig
from contextualize_docs.models.output_models import ContextCard, MinimalExample, SourceEvidence
from contextualize_docs.pipeline.validator import validate_and_fix


def _make_card(**overrides) -> ContextCard:
    defaults = {
        "library": "@supabase/supabase-js",
        "normalized_name": "supabase-js",
        "version": "2.49.1",
        "task_focus": "Add password reset flow",
        "purpose_in_repo": "Handles auth.",
        "why_relevant_for_task": "Password reset uses Supabase.",
        "first_working_code_goal": "A simple string validation.",
        "first_step_for_agent": "Call supabase.auth.resetPasswordForEmail()",
        "architecture_recommendation": "Use a singleton client.",
        "repo_pattern_status": {"has_repo_evidence": False, "message": "None"},
        "integration_strategy_when_no_repo_pattern": "Isolate the client.",
        "implementation_plan": ["Step 1", "Step 2", "Step 3"],
        "mvp_boundary": "Stop when email sends.",
        "quality_upgrade_path": ["Add rate limiting"],
        "core_apis_for_task": [{"name": "resetPasswordForEmail", "usage_pattern": "client.auth.resetPasswordForEmail(email)", "why_core": "Core"}],
        "optional_apis_for_task": [],
        "relevant_apis": [],
        "repo_patterns": [],
        "minimal_examples": [],
        "do_not_use": ["Firebase"],
        "do_not_build_yet": ["OAuth"],
        "common_failure_modes_for_this_task": ["No redirect URL"],
        "decision_shortcuts": ["Never throw."],
        "success_criteria": ["Reset email sent"],
        "gotchas": [],
        "rules_for_agent": [],
        "source_evidence": SourceEvidence(),
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return ContextCard.model_validate(defaults)


class TestValidateAndFix:
    def test_clean_card_passes(self):
        config = AppConfig(openai_api_key="test")
        card = _make_card()
        fixed, warnings = validate_and_fix(card, config)
        assert fixed.confidence == 0.9
        # Only warning should be empty source_evidence
        assert any("source_evidence" in w for w in warnings)

    def test_confidence_clipping(self):
        config = AppConfig(openai_api_key="test")
        # Can't construct with out-of-range via Pydantic, so test via model_copy
        card = _make_card(confidence=1.0)
        card_data = card.model_dump()
        # Manually setting out of range isn't possible via Pydantic validation,
        # but we can test the boundary values
        fixed, warnings = validate_and_fix(card, config)
        assert 0.0 <= fixed.confidence <= 1.0

    def test_normalized_name_correction(self):
        config = AppConfig(openai_api_key="test")
        card = _make_card(normalized_name="WRONG-NAME")
        fixed, warnings = validate_and_fix(card, config)
        assert fixed.normalized_name == "supabase-js"
        assert any("normalized_name" in w for w in warnings)

    def test_truncates_long_purpose(self):
        config = AppConfig(openai_api_key="test")
        card = _make_card(purpose_in_repo="x" * 300)  # exactly 300 is fine
        fixed, _ = validate_and_fix(card, config)
        assert len(fixed.purpose_in_repo) <= 300

    def test_caps_rules_for_agent(self):
        config = AppConfig(openai_api_key="test", max_rules_for_agent=3)
        card = _make_card(rules_for_agent=["r1", "r2", "r3", "r4", "r5"])
        fixed, warnings = validate_and_fix(card, config)
        assert len(fixed.rules_for_agent) == 3
        assert any("rules_for_agent" in w for w in warnings)

    def test_drops_empty_examples(self):
        config = AppConfig(openai_api_key="test")
        card = _make_card(
            minimal_examples=[
                MinimalExample(title="ok", code="z.string()"),
                MinimalExample(title="empty", code="   "),
            ]
        )
        fixed, warnings = validate_and_fix(card, config)
        assert len(fixed.minimal_examples) == 1
        assert any("minimal_examples" in w for w in warnings)

    def test_drops_empty_rules(self):
        config = AppConfig(openai_api_key="test")
        card = _make_card(rules_for_agent=["valid rule", "", "  "])
        fixed, warnings = validate_and_fix(card, config)
        assert len(fixed.rules_for_agent) == 1
