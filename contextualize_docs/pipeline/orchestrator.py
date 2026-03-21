"""Pipeline orchestrator — coordinates all stages end-to-end."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from contextualize_docs.config import AppConfig
from contextualize_docs.logging_config import get_logger
from contextualize_docs.pipeline.card_generator import generate_card
from contextualize_docs.pipeline.deduper import deduplicate_cards
from contextualize_docs.pipeline.grouper import group_evidence
from contextualize_docs.pipeline.preprocessor import preprocess
from contextualize_docs.pipeline.validator import validate_and_fix
from contextualize_docs.pipeline.writer import write_artifacts
from contextualize_docs.providers.base import LLMProvider

if TYPE_CHECKING:
    from contextualize_docs.models.input_models import ContextualizeInput
    from contextualize_docs.models.output_models import ContextCard, RunSummary

logger = get_logger("pipeline.orchestrator")


async def run_pipeline(
    payload: ContextualizeInput,
    provider: LLMProvider,
    output_dir: Path,
    config: AppConfig,
) -> RunSummary:
    """Run the full docs-compilation pipeline.

    Stages:
    1. Preprocess input
    2. Group evidence by dependency
    3. Generate cards (LLM)
    4. Validate + post-process
    5. Deduplicate
    6. Write artifacts

    Returns the ``RunSummary`` that should be emitted on stdout.
    """
    start = time.monotonic()
    all_warnings: list[str] = []
    skipped: list[str] = []

    # ---- 1. Preprocess ----
    logger.info("Stage 1/6: Preprocessing…")
    payload = preprocess(payload)

    # ---- 2. Group evidence ----
    logger.info("Stage 2/6: Grouping evidence…")
    bundles = group_evidence(payload)

    # ---- 3. Generate cards ----
    logger.info("Stage 3/6: Generating cards…")
    max_cards = payload.generation_config.max_cards
    raw_cards: list[ContextCard] = []

    for bundle in bundles:
        if len(raw_cards) >= max_cards:
            logger.info("Reached max_cards=%d, stopping generation.", max_cards)
            break

        if not bundle.has_evidence:
            skipped.append(bundle.dependency.name)
            all_warnings.append(f"Skipped {bundle.dependency.name}: no evidence available.")
            continue

        if bundle.dependency.confidence < config.min_confidence_threshold:
            skipped.append(bundle.dependency.name)
            all_warnings.append(
                f"Skipped {bundle.dependency.name}: confidence "
                f"{bundle.dependency.confidence:.2f} below threshold "
                f"{config.min_confidence_threshold:.2f}."
            )
            continue

        card = await generate_card(provider, payload, bundle)
        if card is not None:
            raw_cards.append(card)
        else:
            skipped.append(bundle.dependency.name)

    if not raw_cards:
        all_warnings.append("No cards were generated — all dependencies skipped or failed.")

    # ---- 4. Validate + post-process ----
    logger.info("Stage 4/6: Validating cards…")
    validated: list[ContextCard] = []
    for card in raw_cards:
        card, card_warnings = validate_and_fix(card, config)
        all_warnings.extend(card_warnings)

        # Drop cards with confidence below threshold after LLM generation
        if card.confidence < config.min_confidence_threshold:
            skipped.append(card.library)
            all_warnings.append(
                f"Dropped {card.library}: post-generation confidence "
                f"{card.confidence:.2f} below threshold."
            )
            continue
        validated.append(card)

    # ---- 5. Deduplicate ----
    logger.info("Stage 5/6: Deduplicating…")
    final_cards = deduplicate_cards(validated)

    # ---- 6. Write artifacts ----
    logger.info("Stage 6/6: Writing artifacts…")
    duration = time.monotonic() - start
    summary = write_artifacts(
        output_dir=output_dir,
        payload=payload,
        cards=final_cards,
        warnings=all_warnings,
        duration_seconds=duration,
        skipped=skipped,
    )

    logger.info(
        "Pipeline complete: %d cards generated, %d skipped, %d warnings in %.2fs.",
        summary.cards_generated,
        len(skipped),
        len(all_warnings),
        duration,
    )
    return summary
