"""Fetches documentation for a library from the npm registry and other sources.

Strategy (in order of preference):
1. npm registry JSON  → README field  (works for all npm packages, JS/TS)
2. PyPI JSON API      → description + project_urls (for Python packages)
3. GitHub README      → raw README.md from the default branch (fallback)

Each source returns raw markdown/text that goes through the preprocessor
before being passed to the card generator.
"""

from __future__ import annotations

import asyncio
import html
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import httpx

from contextualize_docs.logging_config import get_logger

logger = get_logger("fetcher.doc_fetcher")

_NPM_REGISTRY = "https://registry.npmjs.org"
_PYPI_API = "https://pypi.org/pypi"
# npm root endpoint responses can be several MB for large packages — use a generous read timeout
_FETCH_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)


@dataclass
class FetchedDocs:
    """Raw documentation fetched for a single library."""

    library: str
    source_type: str          # "npm_readme", "pypi_description", "github_readme"
    source_url: str
    title: str
    raw_content: str          # raw markdown or plaintext
    version: str = ""
    chunks: list[str] = field(default_factory=list)  # populated after chunking


async def _search_npm_for_name(client: httpx.AsyncClient, query: str) -> str | None:
    """Use the npm search API to find the best matching package name for a fuzzy query.

    Returns the top result's package name, or None if nothing found.
    Example: "Vapi" → "@vapi-ai/web"
    """
    search_url = f"{_NPM_REGISTRY}/-/v1/search"
    try:
        resp = await client.get(search_url, params={"text": query, "size": 3})
        if resp.status_code != 200:
            return None
        data = resp.json()
        objects = data.get("objects", [])
        if not objects:
            return None
        top_name: str = objects[0]["package"]["name"]
        logger.info("npm search: '%s' → '%s' (top result)", query, top_name)
        return top_name
    except (httpx.HTTPError, ValueError, KeyError):
        return None


async def _fetch_npm(client: httpx.AsyncClient, name: str) -> FetchedDocs | None:
    """Fetch README and metadata from the npm registry.

    Falls back to npm search when the exact name returns 404,
    so fuzzy names like 'Vapi' resolve to '@vapi-ai/web' automatically.
    """
    async def _fetch_exact(pkg_name: str) -> FetchedDocs | None:
        encoded = pkg_name.replace("/", "%2F")
        # Root endpoint (no /latest) returns the full README in the top-level "readme" key.
        url = f"{_NPM_REGISTRY}/{encoded}"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data: dict[str, Any] = resp.json()

            # Full README at top level; fall back to version description
            readme = data.get("readme", "")
            if not readme:
                dist_tags = data.get("dist-tags", {})
                latest = dist_tags.get("latest", "")
                version_data = data.get("versions", {}).get(latest, {})
                readme = version_data.get("description") or data.get("description") or ""

            if not readme:
                logger.debug("No readme for %s from npm.", pkg_name)
                return None

            dist_tags = data.get("dist-tags", {})
            version = dist_tags.get("latest", "")
            homepage = data.get("homepage") or f"https://www.npmjs.com/package/{pkg_name}"
            logger.info("Fetched npm docs for %s (%s, %d chars).", pkg_name, version, len(readme))
            return FetchedDocs(
                library=name,          # preserve original requested name for pipeline matching
                source_type="npm_readme",
                source_url=homepage,
                title=f"{pkg_name} — npm README",
                raw_content=readme,
                version=version,
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("npm fetch failed for %s: %s", pkg_name, exc)
            return None

    # 1. Try exact name first
    result = await _fetch_exact(name)
    if result:
        return result

    # 2. Exact name failed — try npm search to find the real package name
    logger.info("Exact npm match failed for '%s', trying npm search…", name)
    resolved_name = await _search_npm_for_name(client, name)
    if resolved_name and resolved_name != name:
        return await _fetch_exact(resolved_name)

    return None



async def _fetch_pypi(client: httpx.AsyncClient, name: str) -> FetchedDocs | None:
    """Fetch description from PyPI."""
    url = f"{_PYPI_API}/{name}/json"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        info = data.get("info", {})
        description = info.get("description") or info.get("summary") or ""
        if not description:
            return None
        version = info.get("version", "")
        project_url = info.get("project_url") or f"https://pypi.org/project/{name}/"
        logger.info("Fetched PyPI docs for %s (%s, %d chars).", name, version, len(description))
        return FetchedDocs(
            library=name,
            source_type="pypi_description",
            source_url=project_url,
            title=f"{name} — PyPI description",
            raw_content=description,
            version=version,
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("PyPI fetch failed for %s: %s", name, exc)
        return None


# --------------------------------------------------------------------------- #
# HTML -> text helper                                                          #
# --------------------------------------------------------------------------- #

_BLOCK_TAGS = re.compile(
    r"<(script|style|nav|footer|header|aside|noscript)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_TAG = re.compile(r"<[^>]+>")
_MULTI_BLANK = re.compile(r"\n{3,}")


def _html_to_text(html_bytes: str) -> str:
    """Strip HTML to readable plaintext — no external deps, good enough for docs pages."""
    text = _BLOCK_TAGS.sub(" ", html_bytes)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    # Collapse whitespace
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


async def _fetch_web_url(
    client: httpx.AsyncClient,
    url: str,
    library_name: str,
) -> FetchedDocs | None:
    """Fetch any URL and strip HTML to readable text.

    Used when the user supplies an explicit docs_url, or when we follow the
    npm homepage URL to get richer official documentation.
    """
    try:
        resp = await client.get(url, headers={"Accept": "text/html,*/*"})
        if resp.status_code != 200:
            logger.debug("Web fetch returned %d for %s", resp.status_code, url)
            return None
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type or "text/plain" in content_type:
            text = _html_to_text(resp.text)
        else:
            text = resp.text  # assume markdown / plain text
        if len(text) < 200:
            logger.debug("Web content too short (%d chars) at %s — skipping", len(text), url)
            return None
        logger.info("Fetched web docs for %s from %s (%d chars).", library_name, url, len(text))
        return FetchedDocs(
            library=library_name,
            source_type="web_scrape",
            source_url=url,
            title=f"{library_name} — official docs",
            raw_content=text,
        )
    except (httpx.HTTPError, UnicodeDecodeError) as exc:
        logger.warning("Web fetch failed for %s @ %s: %s", library_name, url, exc)
        return None


async def _search_web_for_docs(
    client: httpx.AsyncClient,
    library_name: str,
) -> FetchedDocs | None:
    """Use DuckDuckGo HTML search to find the official docs page for a library."""
    query = f"{library_name} npm documentation OR {library_name} python documentation"
    search_url = "https://html.duckduckgo.com/html/"
    try:
        resp = await client.post(
            search_url,
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        if resp.status_code != 200:
            return None
        
        # Super simple regex to extract the first search result link
        match = re.search(r'class="result__url"[^>]*href="([^"]+)"', resp.text)
        if not match:
            return None
            
        top_url = html.unescape(match.group(1))
        # DuckDuckGo prepends their redirector
        if top_url.startswith("//duckduckgo.com/l/?uddg="):
            top_url = top_url.split("uddg=")[1].split("&")[0]
            top_url = urllib.parse.unquote(top_url)
            
        logger.info("Web search found docs candidate for %s: %s", library_name, top_url)
        return await _fetch_web_url(client, top_url, library_name)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Web search failed for %s: %s", library_name, exc)
        return None


async def fetch_docs_for_library(
    name: str,
    *,
    docs_url: str = "",
    prefer_pypi: bool = False,
) -> list[FetchedDocs]:
    """Fetch documentation for a single library from MULTIPLE sources.

    Instead of bailing early on the first hit, we aggregate:
    1. Explicit docs_url (if provided)
    2. DuckDuckGo search top result
    3. npm registry README
    4. npm homepage URL
    
    This ensures the LLM gets both conceptual overviews (from web) AND
    deep code examples/signatures (from GitHub/npm READMEs).
    """
    results: list[FetchedDocs] = []
    seen_urls: set[str] = set()

    def _add(doc: FetchedDocs | None):
        if doc and doc.source_url not in seen_urls and len(doc.raw_content) > 100:
            results.append(doc)
            seen_urls.add(doc.source_url)

    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
        # 1. Explicit docs URL
        if docs_url:
            _add(await _fetch_web_url(client, docs_url, name))

        # 2. Autonomous Web Search (find official docs)
        _add(await _search_web_for_docs(client, name))

        # 3. Registry (PyPI or npm)
        if prefer_pypi:
            _add(await _fetch_pypi(client, name))
            _add(await _fetch_npm(client, name))
        else:
            npm_result = await _fetch_npm(client, name)
            _add(npm_result)
            if npm_result and npm_result.source_url:
                homepage = npm_result.source_url
                if "npmjs.com" not in homepage:
                    _add(await _fetch_web_url(client, homepage, name))
            _add(await _fetch_pypi(client, name))

    if not results:
        logger.warning("All fetch strategies failed for %s.", name)
    else:
        logger.info("Aggregated %d doc sources for %s (total chars: %d).", 
                    len(results), name, sum(len(r.raw_content) for r in results))
    return results


async def fetch_docs_for_all(
    entries: list,  # list[DepEntry]
    *,
    concurrency: int = 5,
) -> list[FetchedDocs]:
    """Fetch docs for multiple libraries concurrently, up to `concurrency` at once."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(entry: Any) -> list[FetchedDocs]:
        async with semaphore:
            name = entry.name if hasattr(entry, "name") else entry
            docs_url = entry.docs_url if hasattr(entry, "docs_url") else ""
            return await fetch_docs_for_library(name, docs_url=docs_url)

    results_of_lists = await asyncio.gather(*[_bounded(e) for e in entries])
    
    fetched = []
    failed = []
    
    for entry, docs_list in zip(entries, results_of_lists):
        if not docs_list:
            failed.append(entry.name if hasattr(entry, "name") else entry)
        else:
            fetched.extend(docs_list)

    if failed:
        logger.warning(
            "Could not fetch docs for %d libraries: %s",
            len(failed),
            ", ".join(failed),
        )

    unique_libraries = len({f.library for f in fetched})
    logger.info("Fetched docs for %d/%d libraries.", unique_libraries, len(entries))
    return fetched
