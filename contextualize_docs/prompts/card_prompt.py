"""User prompt builder for per-dependency card generation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextualize_docs.models.input_models import (
        ContextualizeInput,
        Dependency,
        DocsChunk,
        UsageSnippet,
    )


# The desired output shape is embedded in the prompt so the LLM knows the
# exact JSON structure we expect.
_OUTPUT_SCHEMA = """\
{
  "library": "<original library name>",
  "normalized_name": "<lowercase, scope-stripped safe name>",
  "version": "<version string>",
  "task_focus": "<task title>",
  "purpose_in_repo": "<max 2 sentences — how the repo uses this lib>",
  "why_relevant_for_task": "<max 2 sentences — why this lib matters for the task>",
  "relevant_apis": [
    {
      "name": "<function/method name>",
      "full_signature": "<call signature>",
      "when_to_use": "<one-liner>",
      "required_args": ["<arg>"],
      "optional_args": ["<arg>"],
      "return_shape": "<return type description>",
      "constraints": ["<constraint>"],
      "pitfalls": ["<pitfall>"]
    }
  ],
  "repo_patterns": ["<pattern the agent should follow>"],
  "minimal_examples": [
    {
      "title": "<example title>",
      "code": "<canonical code snippet>"
    }
  ],
  "gotchas": ["<gotcha>"],
  "rules_for_agent": ["<imperative rule>"],
  "source_evidence": {
    "docs_chunk_ids": ["<chunk_id>"],
    "repo_files": ["<file path>"],
    "source_urls": ["<url>"]
  },
  "confidence": 0.0
}"""


def build_card_prompt(
    payload: ContextualizeInput,
    dependency: Dependency,
    docs_chunks: list[DocsChunk],
    usage_snippets: list[UsageSnippet],
) -> str:
    """Build the user-facing prompt for generating one context card."""

    task_block = json.dumps(
        {
            "id": payload.task.id,
            "title": payload.task.title,
            "description": payload.task.description,
            "task_type": payload.task.task_type,
            "relevant_paths": payload.task.relevant_paths,
            "relevant_symbols": payload.task.relevant_symbols,
        },
        indent=2,
    )

    repo_block = json.dumps(
        {
            "project_name": payload.repo_context.project_name,
            "languages": payload.repo_context.languages,
            "frameworks": payload.repo_context.frameworks,
            "detected_patterns": payload.repo_context.detected_patterns,
        },
        indent=2,
    )

    dep_block = json.dumps(
        {
            "name": dependency.name,
            "version": dependency.version,
            "category": dependency.category,
            "used_in_task": dependency.used_in_task,
            "confidence": dependency.confidence,
        },
        indent=2,
    )

    docs_block = json.dumps(
        [
            {
                "chunk_id": c.chunk_id,
                "title": c.title,
                "source_url": c.source_url,
                "content": c.content,
            }
            for c in docs_chunks
        ],
        indent=2,
    )

    snippets_block = json.dumps(
        [
            {
                "file": s.file,
                "symbol": s.symbol,
                "code": s.code,
            }
            for s in usage_snippets
        ],
        indent=2,
    )

    include_examples = payload.generation_config.include_examples
    include_gotchas = payload.generation_config.include_gotchas

    return f"""\
Generate one agent-native context card for the dependency described below.

=== TASK ===
{task_block}

=== REPOSITORY ===
{repo_block}

=== DEPENDENCY ===
{dep_block}

=== DOCUMENTATION CHUNKS ===
{docs_block}

=== REPO USAGE SNIPPETS ===
{snippets_block}

=== INSTRUCTIONS ===
- Write for a coding agent about to implement this task. Not for a human.
- Prefer repo-local patterns over generic documentation advice.
- Include only APIs relevant to the task.
- {"Include minimal canonical code examples." if include_examples else "Omit minimal_examples (return empty list)."}
- {"Include gotchas and pitfalls." if include_gotchas else "Omit gotchas (return empty list)."}
- Do NOT fabricate APIs not present in the evidence above.
- Set confidence between 0 and 1 — lower when evidence is sparse.
- Return ONLY the following JSON structure, no extra text:

{_OUTPUT_SCHEMA}
"""
