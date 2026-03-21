"""Tests for the artifact writer."""

from __future__ import annotations

import json
from pathlib import Path

from contextualize_docs.models.input_models import (
    ContextualizeInput,
    Dependency,
    RepoContext,
    TaskInfo,
)
from contextualize_docs.models.output_models import ContextCard, SourceEvidence
from contextualize_docs.pipeline.writer import write_artifacts


def _make_card(library: str, norm: str, confidence: float = 0.9) -> ContextCard:
    return ContextCard(
        library=library,
        normalized_name=norm,
        version="1.0.0",
        task_focus="Test task",
        purpose_in_repo="Testing.",
        why_relevant_for_task="Testing.",
        relevant_apis=[],
        repo_patterns=[],
        minimal_examples=[],
        gotchas=[],
        rules_for_agent=[],
        source_evidence=SourceEvidence(),
        confidence=confidence,
    )


def _make_payload() -> ContextualizeInput:
    return ContextualizeInput(
        task=TaskInfo(id="t1", title="Test Task", description="d", goal="g"),
        repo_context=RepoContext(project_name="p", languages=["py"]),
        dependencies=[Dependency(name="lib-a"), Dependency(name="lib-b")],
    )


class TestWriter:
    def test_creates_expected_structure(self, tmp_path: Path):
        cards = [_make_card("lib-a", "lib-a"), _make_card("lib-b", "lib-b")]
        payload = _make_payload()

        summary = write_artifacts(
            output_dir=tmp_path,
            payload=payload,
            cards=cards,
            warnings=["test warning"],
            duration_seconds=1.234,
            skipped=[],
        )

        docs_dir = tmp_path / "docs"
        assert docs_dir.is_dir()
        assert (docs_dir / "cards" / "lib-a.json").is_file()
        assert (docs_dir / "cards" / "lib-b.json").is_file()
        assert (docs_dir / "index.json").is_file()
        assert (docs_dir / "manifest.json").is_file()
        assert (docs_dir / "run_summary.json").is_file()

    def test_card_json_is_valid(self, tmp_path: Path):
        cards = [_make_card("lib-a", "lib-a")]
        payload = _make_payload()

        write_artifacts(tmp_path, payload, cards, [], 1.0, [])

        card_data = json.loads((tmp_path / "docs" / "cards" / "lib-a.json").read_text())
        assert card_data["library"] == "lib-a"
        assert card_data["confidence"] == 0.9

    def test_index_json_content(self, tmp_path: Path):
        cards = [_make_card("lib-a", "lib-a")]
        payload = _make_payload()

        write_artifacts(tmp_path, payload, cards, ["w1"], 1.0, [])

        index = json.loads((tmp_path / "docs" / "index.json").read_text())
        assert index["task_id"] == "t1"
        assert len(index["cards"]) == 1
        assert index["cards"][0]["library"] == "lib-a"
        assert index["warnings"] == ["w1"]

    def test_manifest_json_content(self, tmp_path: Path):
        cards = [_make_card("lib-a", "lib-a")]
        payload = _make_payload()

        write_artifacts(tmp_path, payload, cards, [], 1.0, [])

        manifest = json.loads((tmp_path / "docs" / "manifest.json").read_text())
        assert manifest["version"] == "1.0.0"
        assert manifest["card_count"] == 1
        assert manifest["dependency_count"] == 2
        assert len(manifest["artifacts"]) > 0
        # Check that hashes are hex strings
        for artifact in manifest["artifacts"]:
            assert len(artifact["sha256"]) == 64

    def test_run_summary_content(self, tmp_path: Path):
        cards = [_make_card("lib-a", "lib-a")]
        payload = _make_payload()

        summary = write_artifacts(tmp_path, payload, cards, ["w1"], 1.5, ["lib-b"])

        assert summary.success is True
        assert summary.cards_generated == 1
        assert summary.dependencies_processed == 2
        assert summary.skipped_dependencies == ["lib-b"]
        assert summary.validation_warnings == ["w1"]

    def test_no_cards(self, tmp_path: Path):
        payload = _make_payload()
        summary = write_artifacts(tmp_path, payload, [], [], 0.5, ["lib-a", "lib-b"])
        assert summary.cards_generated == 0
        assert (tmp_path / "docs" / "index.json").is_file()
