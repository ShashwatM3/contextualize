"""Deduplication and compression stage for generated cards."""

from __future__ import annotations

from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.output_models import ContextCard

logger = get_logger("pipeline.deduper")


def _dedup_strings(items: list[str]) -> list[str]:
    """Remove exact-duplicate strings while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def deduplicate_card(card: ContextCard) -> ContextCard:
    """Remove duplicate entries within a single card's list fields."""
    updates: dict[str, object] = {}

    deduped_patterns = _dedup_strings(card.repo_patterns)
    if len(deduped_patterns) < len(card.repo_patterns):
        updates["repo_patterns"] = deduped_patterns

    deduped_gotchas = _dedup_strings(card.gotchas)
    if len(deduped_gotchas) < len(card.gotchas):
        updates["gotchas"] = deduped_gotchas

    deduped_rules = _dedup_strings(card.rules_for_agent)
    if len(deduped_rules) < len(card.rules_for_agent):
        updates["rules_for_agent"] = deduped_rules

    # Deduplicate examples by title
    if card.minimal_examples:
        seen_titles: set[str] = set()
        unique_examples = []
        for ex in card.minimal_examples:
            key = ex.title.strip().lower()
            if key not in seen_titles:
                seen_titles.add(key)
                unique_examples.append(ex)
        if len(unique_examples) < len(card.minimal_examples):
            updates["minimal_examples"] = unique_examples

    if updates:
        card = card.model_copy(update=updates)

    return card


def deduplicate_cards(cards: list[ContextCard]) -> list[ContextCard]:
    """Deduplicate within each card and remove whole-card duplicates by library."""
    seen_libs: set[str] = set()
    result: list[ContextCard] = []

    for card in cards:
        if card.normalized_name in seen_libs:
            logger.warning("Dropping duplicate card for %s.", card.library)
            continue
        seen_libs.add(card.normalized_name)
        result.append(deduplicate_card(card))

    return result
