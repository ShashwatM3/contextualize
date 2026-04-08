"""Pydantic models for the input payload from the Node.js CLI."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TaskInfo(BaseModel):
    """Description of the coding task that needs agent-native context."""

    id: str
    title: str
    description: str
    goal: str = "Generate task-scoped agent-native docs for the coding agent."
    task_type: Literal["feature", "bugfix", "refactor", "docs", "test", "other"] = "feature"
    relevant_paths: list[str] = Field(default_factory=list)
    relevant_symbols: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Repo context
# ---------------------------------------------------------------------------

class RelevantFile(BaseModel):
    """A file in the repo that is relevant to the task."""

    path: str
    reason: str = ""


class UsageSnippet(BaseModel):
    """An existing usage of a library within the repo."""

    library: str
    file: str
    symbol: str = ""
    code: str


class RepoContext(BaseModel):
    """Metadata about the repository being analysed."""

    project_name: str
    languages: list[str]
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    detected_patterns: list[str] = Field(default_factory=list)
    relevant_files: list[RelevantFile] = Field(default_factory=list)
    usage_snippets: list[UsageSnippet] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dependencies & docs chunks
# ---------------------------------------------------------------------------

class Dependency(BaseModel):
    """A dependency (library/package) relevant to the task."""

    name: str
    version: str = ""
    category: str = ""
    used_in_task: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class DocsChunk(BaseModel):
    """A chunk of documentation content for a library."""

    library: str
    source_type: str = "official_docs"
    source_url: str = ""
    title: str = ""
    chunk_id: str = ""
    content: str


# ---------------------------------------------------------------------------
# Generation config
# ---------------------------------------------------------------------------

class GenerationConfig(BaseModel):
    """Controls how context cards are generated."""

    output_format: str = "context_card_json"
    max_cards: int = Field(default=5, ge=1, le=20)
    include_examples: bool = True
    include_gotchas: bool = True
    task_scope_strict: bool = True
    prefer_repo_patterns_over_generic_docs: bool = True
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"


# ---------------------------------------------------------------------------
# Top-level input
# ---------------------------------------------------------------------------

class ContextualizeInput(BaseModel):
    """Top-level input schema consumed by the docs compiler pipeline."""

    task: TaskInfo
    repo_context: RepoContext
    dependencies: list[Dependency]
    docs_context: list[DocsChunk] = Field(default_factory=list)
    generation_config: GenerationConfig = Field(default_factory=GenerationConfig)
