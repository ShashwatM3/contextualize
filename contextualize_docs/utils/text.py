"""Text processing utilities."""

from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace (except inside code fences) and strip."""
    lines = text.splitlines()
    result: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            result.append(line)
            continue

        if in_fence:
            # Preserve code blocks verbatim
            result.append(line)
        else:
            # Collapse multiple blank lines into one
            if not stripped:
                if result and result[-1].strip() == "":
                    continue
            # Collapse inline whitespace runs
            result.append(re.sub(r"[ \t]+", " ", line).rstrip())

    return "\n".join(result).strip()


_BOILERPLATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*#{1,3}\s*(Table of Contents|TOC)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*-\s*\[.*?\]\(#.*?\)\s*$", re.MULTILINE),  # TOC links
    re.compile(r"^\s*>?\s*\*?(Was this helpful|Edit this page|Report an issue)\*?\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Cookie|Privacy|Terms of Service\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Copyright ©.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*All rights reserved\.?\s*$", re.IGNORECASE | re.MULTILINE),
]


def strip_boilerplate(text: str) -> str:
    """Remove common documentation boilerplate lines while preserving content."""
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def truncate(text: str, max_length: int) -> str:
    """Truncate text to *max_length* chars, appending '…' if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"
