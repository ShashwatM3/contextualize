"""Library name normalization for safe filenames and matching."""

from __future__ import annotations

import re


def normalize_library_name(name: str) -> str:
    """Convert a library/package name into a safe, normalized filename stem.

    Examples
    --------
    >>> normalize_library_name("@supabase/supabase-js")
    'supabase-js'
    >>> normalize_library_name("next/image")
    'next-image'
    >>> normalize_library_name("React")
    'react'
    >>> normalize_library_name("@tanstack/react-query")
    'react-query'
    """
    # Strip npm scopes:  @scope/name  →  name
    stripped = re.sub(r"^@[^/]+/", "", name)
    # Replace non-alphanumeric (except hyphen) with hyphens
    stripped = re.sub(r"[^a-zA-Z0-9-]", "-", stripped)
    # Collapse consecutive hyphens and strip edges
    stripped = re.sub(r"-+", "-", stripped).strip("-")
    return stripped.lower()


def names_match(a: str, b: str) -> bool:
    """Return *True* if two library names resolve to the same normalized form."""
    return normalize_library_name(a) == normalize_library_name(b)
