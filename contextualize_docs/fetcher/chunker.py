"""Chunks raw fetched documentation into manageable pieces.

READMEs can be very long (5000-20000 tokens). We split on section headers
(# / ## headings) and hard-truncate individual chunks to avoid blowing the
context window. We produce multiple DocsChunk objects per library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from contextualize_docs.fetcher.doc_fetcher import FetchedDocs
from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.input_models import DocsChunk

logger = get_logger("fetcher.chunker")

# ~3000 chars ≈ ~750 tokens — safe limit per chunk for context
_MAX_CHUNK_CHARS = 3_000

# Sections to skip — they're noise for an agent
_SKIP_SECTION_PATTERNS = re.compile(
    r"^#{1,3}\s*(changelog|change\s*log|license|contributing|credits|acknowledgements"
    r"|migration|upgrade|breaking change|roadmap|todo|sponsors|backers|badge)",
    re.IGNORECASE,
)


def _split_on_headings(text: str) -> list[str]:
    """Split markdown text on level 1-3 headings, keeping the heading with its section."""
    parts = re.split(r"(?m)^(?=#{1,3}\s)", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_fetched_docs(
    fetched: FetchedDocs,
    max_chunks: int = 8,
) -> list[DocsChunk]:
    """Convert a FetchedDocs into a list of DocsChunk objects ready for the pipeline.

    Steps:
    1. Split raw content on markdown headings
    2. Drop noisy/irrelevant sections (changelog, license etc.)
    3. Truncate individual chunks to MAX_CHUNK_CHARS
    4. Cap the number of chunks at max_chunks (keep early sections — usually API reference)
    """
    sections = _split_on_headings(fetched.raw_content)
    chunks: list[DocsChunk] = []

    for i, section in enumerate(sections):
        # Drop noise sections
        first_line = section.splitlines()[0] if section else ""
        if _SKIP_SECTION_PATTERNS.match(first_line):
            logger.debug("Skipping section for %s: %r", fetched.library, first_line[:60])
            continue

        # Truncate to max chars
        if len(section) > _MAX_CHUNK_CHARS:
            section = section[:_MAX_CHUNK_CHARS] + "\n…[truncated]"

        chunk = DocsChunk(
            library=fetched.library,
            source_type=fetched.source_type,
            source_url=fetched.source_url,
            title=f"{fetched.title} (section {i + 1})",
            chunk_id=f"{fetched.library}_{i:03d}",
            content=section,
        )
        chunks.append(chunk)

        if len(chunks) >= max_chunks:
            logger.debug(
                "Capped chunks for %s at %d (had %d sections).",
                fetched.library, max_chunks, len(sections),
            )
            break

    logger.info(
        "Chunked %s → %d chunks (from %d sections).",
        fetched.library, len(chunks), len(sections),
    )
    return chunks
