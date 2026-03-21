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
  "purpose_in_repo": "<max 2 sentences — MUST reference repo context if available>",
  "why_relevant_for_task": "<max 2 sentences — MUST be strictly task-specific>",
  "first_working_code_goal": "<Concrete, testable, smallest correct working outcome>",
  "first_step_for_agent": "<A single concrete, actionable instruction for how to begin implementation>",
  "architecture_recommendation": "<short recommendation of how to structure the implementation in this repo>",
  "repo_pattern_status": {
    "has_repo_evidence": true,
    "message": "<If false, explain: No existing usage found; default to minimal isolated integration.>"
  },
  "integration_strategy_when_no_repo_pattern": "<How to integrate safely when no precedent exists, emphasizing minimal coupling. Leave empty if repo_pattern_status is true.>",
  "implementation_plan": [
    "<Step 1: concrete action>",
    "<Step 2: concrete action>"
  ],
  "mvp_boundary": "<Explicit stopping rule for initial implementation to prevent premature complexity.>",
  "quality_upgrade_path": [
    "<Improvement 1 after MVP works, MUST NOT overlap with implementation_plan>"
  ],
  "core_apis_for_task": [
    {
      "name": "<strictly required API for MVP>",
      "usage_pattern": "<real code shape showing how to instantiate/call it>",
      "why_core": "<why this is core for THIS task>"
    }
  ],
  "optional_apis_for_task": [
    {
      "name": "<useful API but not required for MVP>",
      "why_optional": "<why this is optional>"
    }
  ],
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
  "do_not_use": [
    "<incorrect API, SDK, or approach for this task - include reasoning>"
  ],
  "do_not_build_yet": [
    "<overengineering thing to explicitly avoid for this MVP>"
  ],
  "common_failure_modes_for_this_task": [
    "<realistic mistake the agent might make specifically for THIS task>"
  ],
  "decision_shortcuts": [
    "<fast rules to help choose between alternatives>"
  ],
  "success_criteria": [
    "<observable condition that indicates the task is complete>"
  ],
  "gotchas": ["<gotcha>"],
  "rules_for_agent": ["<imperative, implementation-focused rule (no generic descriptions)>"],
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
- Write a task-specific execution pack for a coding agent about to implement this task. Not for a human readers.
- Tell the agent WHAT TO DO NEXT, not just what it should know. Fields MUST resemble actual code usage wherever possible.
- Identify the MINIMAL APIs needed (core_apis_for_task) with concrete `usage_pattern`s and explicitly segregate optional ones (optional_apis_for_task).
- first_working_code_goal must be the smallest correct working outcome.
- explicit MVP vs Quality separation: do not mix first_working_code_goal and quality_upgrade_path.
- implementation_plan MUST be an ordered list of 3-6 steps representing a minimal working path, not full feature coverage.
- explicitly forbid INCORRECT approaches in do_not_use.
- explicitly forbid OVERBUILDING in do_not_build_yet. Define mvp_boundary clearly to prevent premature complexity.
- Define success_criteria as observable conditions.
- Specify a first_step_for_agent to get the agent moving immediately.
- If repo evidence is missing, do NOT silently leave repo_patterns empty. Set repo_pattern_status.has_repo_evidence to false, provide a message, AND fill integration_strategy_when_no_repo_pattern.
- Rules MUST be imperative and implementation-focused (e.g. "Do X", "Call Y"). 
- {"Include minimal canonical code examples." if include_examples else "Omit minimal_examples (return empty list)."}
- {"Include gotchas and pitfalls." if include_gotchas else "Omit gotchas (return empty list)."}
- Do NOT fabricate APIs not present in the evidence above.
- Set confidence between 0 and 1 — reduce confidence if documentation is incomplete.
- Return ONLY the following JSON structure, no extra text:

{_OUTPUT_SCHEMA}
"""
