"""Tests for input model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contextualize_docs.models.input_models import (
    ContextualizeInput,
    Dependency,
    DocsChunk,
    GenerationConfig,
    RepoContext,
    TaskInfo,
)


class TestTaskInfo:
    def test_valid(self):
        t = TaskInfo(id="t1", title="Test", description="desc", goal="g")
        assert t.id == "t1"
        assert t.task_type == "feature"  # default

    def test_invalid_task_type(self):
        with pytest.raises(ValidationError):
            TaskInfo(id="t1", title="T", description="d", goal="g", task_type="invalid")

    def test_defaults(self):
        t = TaskInfo(id="t1", title="T", description="d", goal="g")
        assert t.relevant_paths == []
        assert t.relevant_symbols == []


class TestDependency:
    def test_valid(self):
        d = Dependency(name="zod", version="3.0.0", confidence=0.9)
        assert d.used_in_task is True

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            Dependency(name="x", confidence=1.5)
        with pytest.raises(ValidationError):
            Dependency(name="x", confidence=-0.1)


class TestDocsChunk:
    def test_requires_content(self):
        with pytest.raises(ValidationError):
            DocsChunk(library="x")  # missing content

    def test_valid(self):
        c = DocsChunk(library="x", content="some docs")
        assert c.source_type == "official_docs"


class TestGenerationConfig:
    def test_defaults(self):
        g = GenerationConfig()
        assert g.max_cards == 5
        assert g.llm_provider == "gemini"
        assert g.include_examples is True

    def test_max_cards_bounds(self):
        with pytest.raises(ValidationError):
            GenerationConfig(max_cards=0)
        with pytest.raises(ValidationError):
            GenerationConfig(max_cards=25)


class TestContextualizeInput:
    def test_valid_from_fixture(self, sample_input_json):
        payload = ContextualizeInput.model_validate(sample_input_json)
        assert payload.task.id == "task_001"
        assert len(payload.dependencies) == 2
        assert len(payload.docs_context) == 2

    def test_missing_task(self, sample_input_json):
        del sample_input_json["task"]
        with pytest.raises(ValidationError):
            ContextualizeInput.model_validate(sample_input_json)

    def test_missing_dependencies(self, sample_input_json):
        del sample_input_json["dependencies"]
        with pytest.raises(ValidationError):
            ContextualizeInput.model_validate(sample_input_json)

    def test_defaults_applied(self):
        minimal = {
            "task": {"id": "1", "title": "t", "description": "d", "goal": "g"},
            "repo_context": {"project_name": "p", "languages": ["py"]},
            "dependencies": [],
        }
        payload = ContextualizeInput.model_validate(minimal)
        assert payload.generation_config.llm_provider == "gemini"
        assert payload.docs_context == []
