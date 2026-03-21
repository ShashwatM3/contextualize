"""Artifact writer — writes context cards and metadata to .contextualize/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.output_models import (
    ArtifactHash,
    CardEntry,
    IndexFile,
    ManifestFile,
    RunSummary,
)
from contextualize_docs.utils.hashing import sha256_file, sha256_str

if TYPE_CHECKING:
    from contextualize_docs.models.input_models import ContextualizeInput
    from contextualize_docs.models.output_models import ContextCard

logger = get_logger("pipeline.writer")


def _write_json(path: Path, data: dict) -> None:
    """Atomically write JSON — write to tmp then rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.rename(path)


def write_artifacts(
    output_dir: Path,
    payload: ContextualizeInput,
    cards: list[ContextCard],
    warnings: list[str],
    duration_seconds: float,
    skipped: list[str],
    provider_metadata: dict[str, object] | None = None,
) -> RunSummary:
    """Write all output artifacts to ``output_dir/docs/``.

    Returns
    -------
    RunSummary
        The summary that should be emitted on stdout for the calling CLI.
    """
    docs_dir = output_dir / "docs"
    cards_dir = docs_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    artifact_hashes: list[ArtifactHash] = []

    # ------------------------------------------------------------------ #
    # 1.  Per-library card files                                          #
    # ------------------------------------------------------------------ #
    card_entries: list[CardEntry] = []

    for card in cards:
        card_filename = f"{card.normalized_name}.json"
        card_path = cards_dir / card_filename
        _write_json(card_path, card.model_dump())
        artifact_hashes.append(
            ArtifactHash(path=f"docs/cards/{card_filename}", sha256=sha256_file(card_path))
        )
        card_entries.append(
            CardEntry(
                library=card.library,
                normalized_name=card.normalized_name,
                card_path=f"docs/cards/{card_filename}",
                confidence=card.confidence,
            )
        )
        logger.info("Wrote card: %s", card_path)

    # ------------------------------------------------------------------ #
    # 2.  index.json                                                      #
    # ------------------------------------------------------------------ #
    index = IndexFile(
        task_id=payload.task.id,
        task_title=payload.task.title,
        generated_at=now_iso,
        cards=card_entries,
        warnings=warnings,
    )
    index_path = docs_dir / "index.json"
    _write_json(index_path, index.model_dump())
    artifact_hashes.append(
        ArtifactHash(path="docs/index.json", sha256=sha256_file(index_path))
    )
    logger.info("Wrote index: %s", index_path)

    # ------------------------------------------------------------------ #
    # 3.  manifest.json                                                   #
    # ------------------------------------------------------------------ #
    input_json = payload.model_dump_json()
    manifest = ManifestFile(
        version="1.0.0",
        generated_at=now_iso,
        llm_provider=payload.generation_config.llm_provider,
        llm_model=payload.generation_config.llm_model,
        input_hash=sha256_str(input_json),
        artifacts=artifact_hashes,
        card_count=len(cards),
        dependency_count=len(payload.dependencies),
        warning_count=len(warnings),
    )
    manifest_path = docs_dir / "manifest.json"
    _write_json(manifest_path, manifest.model_dump())
    logger.info("Wrote manifest: %s", manifest_path)

    # ------------------------------------------------------------------ #
    # 4.  run_summary.json                                                #
    # ------------------------------------------------------------------ #
    summary = RunSummary(
        success=True,
        dependencies_processed=len(payload.dependencies),
        cards_generated=len(cards),
        skipped_dependencies=skipped,
        validation_warnings=warnings,
        provider_metadata=provider_metadata or {},
        duration_seconds=round(duration_seconds, 3),
    )
    summary_path = docs_dir / "run_summary.json"
    _write_json(summary_path, summary.model_dump())
    logger.info("Wrote run summary: %s", summary_path)

    return summary
