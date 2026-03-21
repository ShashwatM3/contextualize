"""Post-processing validation for generated context cards."""

from __future__ import annotations

from contextualize_docs.config import AppConfig
from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.output_models import ContextCard
from contextualize_docs.utils.normalization import normalize_library_name
from contextualize_docs.utils.text import truncate

logger = get_logger("pipeline.validator")


def validate_and_fix(card: ContextCard, config: AppConfig) -> tuple[ContextCard, list[str]]:
    """Apply deterministic post-processing to a generated card.

    Returns the (possibly modified) card and a list of warning strings.
    """
    warnings: list[str] = []
    updates: dict[str, object] = {}

    # --- Confidence clipping ---
    if card.confidence < 0.0:
        updates["confidence"] = 0.0
        warnings.append(f"{card.library}: confidence clipped from {card.confidence} to 0.0")
    elif card.confidence > 1.0:
        updates["confidence"] = 1.0
        warnings.append(f"{card.library}: confidence clipped from {card.confidence} to 1.0")

    # --- Normalized name ---
    expected_norm = normalize_library_name(card.library)
    if card.normalized_name != expected_norm:
        updates["normalized_name"] = expected_norm
        warnings.append(f"{card.library}: normalized_name corrected to {expected_norm}")

    # --- purpose_in_repo / why_relevant_for_task length ---
    if len(card.purpose_in_repo) > 300:
        updates["purpose_in_repo"] = truncate(card.purpose_in_repo, 300)
        warnings.append(f"{card.library}: purpose_in_repo truncated to 300 chars")
    if len(card.why_relevant_for_task) > 300:
        updates["why_relevant_for_task"] = truncate(card.why_relevant_for_task, 300)
        warnings.append(f"{card.library}: why_relevant_for_task truncated to 300 chars")

    # --- Cap relevant_apis ---
    max_apis = config.max_relevant_apis
    if len(card.relevant_apis) > max_apis:
        updates["relevant_apis"] = list(card.relevant_apis[:max_apis])
        warnings.append(f"{card.library}: relevant_apis truncated to {max_apis} entries")

    # --- Cap rules_for_agent ---
    max_rules = config.max_rules_for_agent
    if len(card.rules_for_agent) > max_rules:
        updates["rules_for_agent"] = list(card.rules_for_agent[:max_rules])
        warnings.append(f"{card.library}: rules_for_agent truncated to {max_rules} entries")

    # --- Reject empty minimal_examples code ---
    if card.minimal_examples:
        valid_examples = [ex for ex in card.minimal_examples if ex.code.strip()]
        if len(valid_examples) < len(card.minimal_examples):
            updates["minimal_examples"] = valid_examples
            warnings.append(f"{card.library}: dropped minimal_examples with empty code")

    # --- Reject empty rules_for_agent entries ---
    if card.rules_for_agent:
        valid_rules = [r for r in card.rules_for_agent if r.strip()]
        if len(valid_rules) < len(card.rules_for_agent):
            updates["rules_for_agent"] = valid_rules
            warnings.append(f"{card.library}: dropped empty rules_for_agent entries")

    # --- Ensure source_evidence has at least something ---
    se = card.source_evidence
    if not se.docs_chunk_ids and not se.repo_files and not se.source_urls:
        warnings.append(f"{card.library}: source_evidence is completely empty")

    # --- first_step_for_agent / architecture_recommendation length ---
    if len(card.first_step_for_agent) > 300:
        updates["first_step_for_agent"] = truncate(card.first_step_for_agent, 300)
        warnings.append(f"{card.library}: first_step_for_agent truncated to 300 chars")
    if len(card.architecture_recommendation) > 500:
        updates["architecture_recommendation"] = truncate(card.architecture_recommendation, 500)
        warnings.append(f"{card.library}: architecture_recommendation truncated to 500 chars")

    # --- Cap implementation_plan ---
    if len(card.implementation_plan) > 6:
        updates["implementation_plan"] = list(card.implementation_plan[:6])
        warnings.append(f"{card.library}: implementation_plan truncated to 6 entries")

    # --- Core APIs sanity checks ---
    if not card.core_apis_for_task and card.relevant_apis:
        warnings.append(f"{card.library}: no core_apis_for_task identified but relevant_apis exist")
    elif len(card.core_apis_for_task) > 5:
        updates["core_apis_for_task"] = list(card.core_apis_for_task[:5])
        warnings.append(f"{card.library}: core_apis_for_task truncated to 5 entries")

    # --- Optional APIs bounds ---
    if len(card.optional_apis_for_task) > 5:
        updates["optional_apis_for_task"] = list(card.optional_apis_for_task[:5])
        warnings.append(f"{card.library}: optional_apis_for_task truncated to 5 entries")

    # --- Upgrade path & heuristics bounds ---
    if len(card.quality_upgrade_path) > 5:
        updates["quality_upgrade_path"] = list(card.quality_upgrade_path[:5])
        warnings.append(f"{card.library}: quality_upgrade_path truncated to 5 entries")
    
    if len(card.decision_shortcuts) > 5:
        updates["decision_shortcuts"] = list(card.decision_shortcuts[:5])
        warnings.append(f"{card.library}: decision_shortcuts truncated to 5 entries")

    if updates:
        card = card.model_copy(update=updates)

    return card, warnings
