"""Preprocessing stage — normalize and clean docs chunks before grouping."""

from __future__ import annotations

from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.input_models import ContextualizeInput, DocsChunk
from contextualize_docs.utils.text import normalize_whitespace, strip_boilerplate

logger = get_logger("pipeline.preprocessor")


def preprocess(payload: ContextualizeInput) -> ContextualizeInput:
    """Return a new payload with cleaned docs chunks.

    Mutations:
    - Normalize whitespace in ``content`` (preserving code fences).
    - Strip common documentation boilerplate.
    - Drop chunks whose content is empty after cleaning.
    """
    cleaned: list[DocsChunk] = []

    for chunk in payload.docs_context:
        content = normalize_whitespace(chunk.content)
        content = strip_boilerplate(content)

        if not content:
            logger.info("Dropping empty docs chunk: chunk_id=%s, library=%s", chunk.chunk_id, chunk.library)
            continue

        cleaned.append(chunk.model_copy(update={"content": content}))

    dropped = len(payload.docs_context) - len(cleaned)
    if dropped:
        logger.info("Preprocessing: dropped %d empty chunks out of %d.", dropped, len(payload.docs_context))

    return payload.model_copy(update={"docs_context": cleaned})
