"""Card generation stage — call LLM to produce context cards."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.output_models import ContextCard
from contextualize_docs.prompts.card_prompt import build_card_prompt
from contextualize_docs.prompts.system_prompt import SYSTEM_PROMPT
from contextualize_docs.providers.base import LLMProvider, ProviderError
from contextualize_docs.utils.normalization import normalize_library_name

if TYPE_CHECKING:
    from contextualize_docs.models.input_models import ContextualizeInput
    from contextualize_docs.pipeline.grouper import DependencyBundle

logger = get_logger("pipeline.card_generator")


async def generate_card(
    provider: LLMProvider,
    payload: ContextualizeInput,
    bundle: DependencyBundle,
) -> ContextCard | None:
    """Generate a single context card for a dependency bundle.

    Returns *None* (with a logged warning) when:
    - The bundle has no evidence at all.
    - The LLM provider fails after retries.
    - The LLM output cannot be parsed into a valid ``ContextCard``.
    """
    dep = bundle.dependency
    dep_display = dep.name

    if not bundle.has_evidence:
        logger.warning("Skipping %s — no docs chunks or usage snippets.", dep_display)
        return None

    prompt = build_card_prompt(payload, dep, bundle.docs_chunks, bundle.usage_snippets)

    try:
        raw = await provider.generate_json(SYSTEM_PROMPT, prompt)
    except ProviderError as exc:
        logger.error("LLM generation failed for %s: %s", dep_display, exc)
        return None

    # Inject / override fields we know deterministically
    raw.setdefault("library", dep.name)
    raw["normalized_name"] = normalize_library_name(dep.name)
    if dep.version:
        raw.setdefault("version", dep.version)
    raw.setdefault("task_focus", payload.task.title)

    # Validate via Pydantic
    try:
        card = ContextCard.model_validate(raw)
    except ValidationError as exc:
        logger.error("Card validation failed for %s: %s", dep_display, exc)
        return None

    logger.info("Generated card for %s (confidence=%.2f).", dep_display, card.confidence)
    return card
