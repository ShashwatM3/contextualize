"""End-to-end test — sample fixture JSON → CLI → .contextualize/ files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from contextualize_docs.models.output_models import ContextCard, IndexFile, ManifestFile, RunSummary


def _run_cli(input_path: Path, output_dir: Path) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "contextualize_docs", "--input", str(input_path), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parents[2]),  # repo root
    )


class TestE2EWithMockedProvider:
    """E2E that monkeypatches the provider to avoid needing real API keys."""

    @pytest.mark.asyncio
    async def test_e2e_pipeline(self, sample_input_path: Path, sample_payload, tmp_path: Path):
        """Run orchestrator directly (simulating CLI flow) with mocked provider."""
        from contextualize_docs.config import AppConfig
        from contextualize_docs.pipeline.orchestrator import run_pipeline
        from contextualize_docs.tests.test_integration import MockGeminiProvider

        config = AppConfig(gemini_api_key="test-key")
        provider = MockGeminiProvider()

        summary = await run_pipeline(
            payload=sample_payload,
            provider=provider,
            output_dir=tmp_path,
            config=config,
        )

        # ---- Verify run summary ----
        assert summary.success is True
        assert summary.cards_generated >= 1
        assert summary.duration_seconds >= 0

        # ---- Verify file structure ----
        docs_dir = tmp_path / "docs"
        assert (docs_dir / "index.json").is_file()
        assert (docs_dir / "manifest.json").is_file()
        assert (docs_dir / "run_summary.json").is_file()
        assert (docs_dir / "cards").is_dir()

        # ---- Validate index.json against schema ----
        index_data = json.loads((docs_dir / "index.json").read_text())
        index = IndexFile.model_validate(index_data)
        assert index.task_id == "task_001"
        assert index.task_title == "Add password reset flow"

        # ---- Validate manifest.json against schema ----
        manifest_data = json.loads((docs_dir / "manifest.json").read_text())
        manifest = ManifestFile.model_validate(manifest_data)
        assert manifest.card_count >= 1
        assert len(manifest.input_hash) == 64  # SHA-256

        # ---- Validate each card against schema ----
        cards_dir = docs_dir / "cards"
        card_files = list(cards_dir.glob("*.json"))
        assert len(card_files) >= 1

        for card_file in card_files:
            card_data = json.loads(card_file.read_text())
            card = ContextCard.model_validate(card_data)
            assert card.task_focus == "Add password reset flow"
            assert 0.0 <= card.confidence <= 1.0
            assert card.normalized_name  # not empty

        # ---- Validate run_summary.json against schema ----
        summary_data = json.loads((docs_dir / "run_summary.json").read_text())
        run_summary = RunSummary.model_validate(summary_data)
        assert run_summary.success is True
        assert run_summary.dependencies_processed == 2

        # ---- Cross-validation: index cards match card files ----
        index_card_names = {c.normalized_name for c in index.cards}
        file_card_names = {f.stem for f in card_files}
        assert index_card_names == file_card_names

        # ---- Cross-validation: manifest artifact count ----
        # Cards + index + (manifest is not self-referential)
        # At minimum: N cards + 1 index
        assert len(manifest.artifacts) >= len(card_files) + 1
