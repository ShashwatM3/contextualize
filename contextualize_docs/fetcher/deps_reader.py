"""Reads a JSON deps file and returns a list of DepEntry objects.

Supported JSON formats:

1. Simple array of strings:
   ["@supabase/supabase-js", "zod", "Vapi"]

2. Array of objects (with optional docs_url and category):
   [
     {"name": "@supabase/supabase-js", "category": "database"},
     {"name": "Vapi", "docs_url": "https://docs.vapi.ai/introduction", "category": "voice-ai"}
   ]

3. Object with a "libraries" or "dependencies" key (either format above):
   {
     "libraries": [
       {"name": "zod", "category": "validation"},
       {"name": "next", "docs_url": "https://nextjs.org/docs"}
     ]
   }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from contextualize_docs.logging_config import get_logger

logger = get_logger("fetcher.deps_reader")


@dataclass
class DepEntry:
    """A single dependency with its name and optional metadata."""
    name: str
    docs_url: str = ""       # if set, fetch from this URL directly instead of npm/search
    category: str = ""       # e.g. "auth", "validation", "voice-ai", "database", "ui"


def read_dependencies(deps_file: Path) -> list[DepEntry]:
    """Parse a deps JSON file into a list of DepEntry objects.

    Also accepts the legacy plain-text format (one name per line) for backwards compat.
    """
    if not deps_file.is_file():
        raise FileNotFoundError(
            f"Dependencies file not found at {deps_file}. "
            "Run `contextualize scan` first, or create it manually."
        )

    raw = deps_file.read_text(encoding="utf-8").strip()

    # ---- Try JSON first ----
    if raw.startswith(("{", "[")):
        entries = _parse_json(raw, deps_file)
    else:
        # Legacy plain-text fallback
        entries = _parse_plaintext(raw, deps_file)

    logger.info("Read %d dependencies from %s.", len(entries), deps_file)
    return entries


def _parse_json(raw: str, source: Path) -> list[DepEntry]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {source}: {exc}") from exc

    # Unwrap wrapper object → list
    if isinstance(data, dict):
        data = data.get("libraries") or data.get("dependencies") or []

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array (or object with 'libraries' key) in {source}.")

    entries: list[DepEntry] = []
    for item in data:
        if isinstance(item, str):
            entries.append(DepEntry(name=item.strip()))
        elif isinstance(item, dict):
            name = (item.get("name") or "").strip()
            if not name:
                continue
            entries.append(DepEntry(
                name=name,
                docs_url=item.get("docs_url", ""),
                category=item.get("category", ""),
            ))
        else:
            logger.warning("Skipping unrecognised deps entry: %r", item)
    return entries


def _parse_plaintext(raw: str, source: Path) -> list[DepEntry]:
    """Legacy one-name-per-line parser."""
    entries: list[DepEntry] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip().strip('"\'').rstrip(",").strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line.startswith("@"):
            line = line.split(":")[0].strip().strip('"\'')
        if line.startswith("@"):
            parts = line[1:].split("@", 1)
            line = "@" + parts[0]
        else:
            line = line.split("@")[0]
        line = line.strip()
        if line:
            entries.append(DepEntry(name=line))
    logger.info("Parsed %d entries from plain-text format in %s.", len(entries), source)
    return entries
