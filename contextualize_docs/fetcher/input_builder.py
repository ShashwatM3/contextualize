"""Builds a ContextualizeInput from a list of library names + optional repo context.

This is the bridge between the fetcher (raw docs) and the pipeline (card generation).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from contextualize_docs.fetcher.chunker import chunk_fetched_docs
from contextualize_docs.fetcher.doc_fetcher import FetchedDocs, fetch_docs_for_all
from contextualize_docs.logging_config import get_logger
from contextualize_docs.models.input_models import (
    ContextualizeInput,
    Dependency,
    GenerationConfig,
    RepoContext,
    TaskInfo,
)

logger = get_logger("fetcher.input_builder")


def _infer_repo_context(project_root: Path) -> RepoContext:
    """Infer basic repo context from the project root directory."""
    name = project_root.resolve().name

    # Detect language/framework from marker files
    languages: list[str] = []
    frameworks: list[str] = []

    if (project_root / "package.json").exists():
        languages.append("TypeScript" if (project_root / "tsconfig.json").exists() else "JavaScript")
        pkg = (project_root / "package.json").read_text()
        if "next" in pkg:
            frameworks.append("Next.js")
        if "react" in pkg:
            frameworks.append("React")

    if (project_root / "pyproject.toml").exists() or (project_root / "setup.py").exists():
        languages.append("Python")

    if not languages:
        languages = ["Unknown"]

    return RepoContext(
        project_name=name,
        languages=languages,
        frameworks=frameworks,
    )


async def build_input_from_deps(
    library_entries: list,  # list[DepEntry]
    task_title: str,
    task_description: str,
    project_root: Path,
    llm_provider: str = "vercel",
    llm_model: str = "google/gemini-2.5-flash",
    max_cards: int = 10,
) -> ContextualizeInput:
    """Fetch docs for all libraries and build a ContextualizeInput payload.

    Args:
        library_entries: list of DepEntry objects
        task_title: short title describing what the agent will do
        task_description: longer description of the coding task
        project_root: path to the root of the project being analysed
        llm_provider: which LLM provider to use
        llm_model: which model to send to the provider
        max_cards: maximum cards to generate

    Returns:
        A fully-formed ContextualizeInput ready for the pipeline.
    """
    logger.info("Fetching docs for %d libraries…", len(library_entries))
    fetched_list: list[FetchedDocs] = await fetch_docs_for_all(library_entries)

    # Map library name → fetched docs for quick lookup
    fetched_map: dict[str, FetchedDocs] = {f.library: f for f in fetched_list}

    # Build Dependency objects
    dependencies: list[Dependency] = []
    for entry in library_entries:
        name = entry.name if hasattr(entry, "name") else entry
        category = entry.category if hasattr(entry, "category") else ""
        
        fetched = fetched_map.get(name)
        dependencies.append(Dependency(
            name=name,
            version=fetched.version if fetched else "",
            used_in_task=True,
            confidence=0.9 if fetched else 0.5,
            # Pass category if the input_models.Dependency supports it.
            # (If it doesn't currently support `category`, ignoring it for now is safe).
        ))

    # Build DocsChunk objects
    all_chunks = []
    for fetched in fetched_list:
        chunks = chunk_fetched_docs(fetched)
        all_chunks.extend(chunks)

    logger.info(
        "Built %d deps, %d doc chunks from %d fetched sources.",
        len(dependencies), len(all_chunks), len(fetched_list),
    )

    repo_context = _infer_repo_context(project_root)

    return ContextualizeInput(
        task=TaskInfo(
            id="auto",
            title=task_title,
            description=task_description,
            goal=f"Generate agent-native context cards for: {task_title}",
        ),
        repo_context=repo_context,
        dependencies=dependencies,
        docs_context=all_chunks,
        generation_config=GenerationConfig(
            max_cards=max_cards,
            llm_provider=llm_provider,
            llm_model=llm_model,
        ),
    )
