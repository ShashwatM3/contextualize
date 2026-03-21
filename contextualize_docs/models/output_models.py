"""Pydantic models for generated output artifacts."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Context card components
# ---------------------------------------------------------------------------

class RelevantAPI(BaseModel):
    """A single API / function relevant to the task."""

    name: str
    full_signature: str = ""
    when_to_use: str
    required_args: list[str] = Field(default_factory=list)
    optional_args: list[str] = Field(default_factory=list)
    return_shape: str = ""
    constraints: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)


class CoreAPI(BaseModel):
    """An API strictly required for the MVP of the task."""
    
    name: str
    usage_pattern: str
    why_core: str


class OptionalAPI(BaseModel):
    """An API that is useful but not required for the MVP."""
    
    name: str
    why_optional: str


class RepoPatternStatus(BaseModel):
    """Describes whether repo-specific usage patterns were found."""
    
    has_repo_evidence: bool
    message: str


class MinimalExample(BaseModel):
    """A short, canonical code example."""

    title: str
    code: str


class SourceEvidence(BaseModel):
    """Provenance links back to input data."""

    docs_chunk_ids: list[str] = Field(default_factory=list)
    repo_files: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Context card (the primary output artefact)
# ---------------------------------------------------------------------------

class ContextCard(BaseModel):
    """A structured, agent-native context card for one library/dependency."""

    library: str
    normalized_name: str
    version: str = ""
    task_focus: str
    purpose_in_repo: str = Field(
        ...,
        max_length=300,
        description="Max 2 sentences. How this lib is used in the repo.",
    )
    why_relevant_for_task: str = Field(
        ...,
        max_length=300,
        description="Max 2 sentences. Why the agent needs this lib for the current task.",
    )
    first_working_code_goal: str = Field(
        ...,
        description="The smallest correct working outcome. Must be concrete and testable."
    )
    first_step_for_agent: str = Field(
        ..., 
        description="A single concrete, actionable instruction for how to begin."
    )
    architecture_recommendation: str = Field(
        ...,
        description="Short recommendation of how to structure the implementation."
    )
    repo_pattern_status: RepoPatternStatus
    integration_strategy_when_no_repo_pattern: str = Field(
        default="",
        description="How to integrate safely when no precedent exists, emphasizing minimal coupling."
    )
    implementation_plan: list[str] = Field(
        ...,
        description="Ordered list of 3-6 steps representing a minimal working path."
    )
    mvp_boundary: str = Field(
        ...,
        description="Explicit stopping rule for initial implementation to prevent premature complexity."
    )
    quality_upgrade_path: list[str] = Field(
        default_factory=list,
        description="Ordered improvements after MVP works, not overlapping with implementation_plan."
    )
    core_apis_for_task: list[CoreAPI] = Field(
        default_factory=list,
        description="Subset of relevant_apis strictly needed for this task."
    )
    optional_apis_for_task: list[OptionalAPI] = Field(
        default_factory=list,
        description="APIs that are useful but not required for MVP."
    )
    relevant_apis: list[RelevantAPI] = Field(
        default_factory=list,
        description="Max 5 entries unless clearly justified. Superset of core APIs.",
    )
    repo_patterns: list[str] = Field(default_factory=list)
    minimal_examples: list[MinimalExample] = Field(default_factory=list)
    do_not_use: list[str] = Field(
        default_factory=list,
        description="Incorrect APIs, SDKs, or approaches for this task with reasons."
    )
    do_not_build_yet: list[str] = Field(
        default_factory=list,
        description="Things that would be overengineering for this task."
    )
    common_failure_modes_for_this_task: list[str] = Field(default_factory=list)
    decision_shortcuts: list[str] = Field(
        default_factory=list,
        description="Fast rules to help agent choose between alternatives."
    )
    success_criteria: list[str] = Field(default_factory=list)
    gotchas: list[str] = Field(default_factory=list)
    rules_for_agent: list[str] = Field(
        default_factory=list,
        description="Max 6 actionable imperative rules.",
    )
    source_evidence: SourceEvidence = Field(default_factory=SourceEvidence)
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Index file
# ---------------------------------------------------------------------------

class CardEntry(BaseModel):
    """Pointer to a generated card file."""

    library: str
    normalized_name: str
    card_path: str
    confidence: float


class IndexFile(BaseModel):
    """Links task metadata to generated cards."""

    task_id: str
    task_title: str
    generated_at: str  # ISO 8601
    cards: list[CardEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class ArtifactHash(BaseModel):
    """Checksum entry for a single artifact file."""

    path: str
    sha256: str


class ManifestFile(BaseModel):
    """Build manifest with hashes and metadata."""

    version: str = "1.0.0"
    generated_at: str
    llm_provider: str
    llm_model: str
    input_hash: str
    artifacts: list[ArtifactHash] = Field(default_factory=list)
    card_count: int
    dependency_count: int
    warning_count: int


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------

class RunSummary(BaseModel):
    """Emitted on stdout for the calling CLI."""

    success: bool
    dependencies_processed: int
    cards_generated: int
    skipped_dependencies: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    provider_metadata: dict[str, object] = Field(default_factory=dict)
    duration_seconds: float
