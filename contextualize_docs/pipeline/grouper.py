"""Grouping stage — bundle evidence by dependency."""

from __future__ import annotations

from dataclasses import dataclass, field

from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.input_models import (
    ContextualizeInput,
    Dependency,
    DocsChunk,
    UsageSnippet,
)
from contextualize_docs.utils.normalization import normalize_library_name

logger = get_logger("pipeline.grouper")


@dataclass
class DependencyBundle:
    """All evidence for a single dependency, ready for card generation."""

    dependency: Dependency
    docs_chunks: list[DocsChunk] = field(default_factory=list)
    usage_snippets: list[UsageSnippet] = field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return bool(self.docs_chunks) or bool(self.usage_snippets)


def group_evidence(payload: ContextualizeInput) -> list[DependencyBundle]:
    """Group docs chunks and usage snippets by dependency.

    Matching is done on normalized library names so that e.g.
    ``@supabase/supabase-js`` matches snippets referencing
    ``@supabase/supabase-js``.
    """
    # Build a lookup: normalized_name → bundle
    bundles: dict[str, DependencyBundle] = {}
    norm_to_orig: dict[str, str] = {}

    for dep in payload.dependencies:
        norm = normalize_library_name(dep.name)
        bundles[norm] = DependencyBundle(dependency=dep)
        norm_to_orig[norm] = dep.name

    # Assign docs chunks
    for chunk in payload.docs_context:
        norm = normalize_library_name(chunk.library)
        if norm in bundles:
            bundles[norm].docs_chunks.append(chunk)
        else:
            # Fallback: create an implicit bundle for unmatched docs
            logger.warning(
                "Docs chunk library=%r (norm=%r) does not match any declared dependency. "
                "Creating implicit bundle.",
                chunk.library,
                norm,
            )
            dep = Dependency(name=chunk.library, used_in_task=False, confidence=0.5)
            bundles[norm] = DependencyBundle(dependency=dep, docs_chunks=[chunk])
            norm_to_orig[norm] = chunk.library

    # Assign usage snippets
    for snippet in payload.repo_context.usage_snippets:
        norm = normalize_library_name(snippet.library)
        if norm in bundles:
            bundles[norm].usage_snippets.append(snippet)
        else:
            logger.debug(
                "Usage snippet library=%r has no matching dependency bundle; skipping.",
                snippet.library,
            )

    result = list(bundles.values())
    logger.info(
        "Grouped evidence into %d bundles (%d with evidence, %d empty).",
        len(result),
        sum(1 for b in result if b.has_evidence),
        sum(1 for b in result if not b.has_evidence),
    )
    return result
