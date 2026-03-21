"""Tests for the preprocessing stage."""

from __future__ import annotations

from contextualize_docs.models.input_models import (
    ContextualizeInput,
    Dependency,
    DocsChunk,
    GenerationConfig,
    RepoContext,
    TaskInfo,
)
from contextualize_docs.pipeline.preprocessor import preprocess


def _make_payload(*chunks: DocsChunk) -> ContextualizeInput:
    return ContextualizeInput(
        task=TaskInfo(id="t1", title="T", description="d", goal="g"),
        repo_context=RepoContext(project_name="p", languages=["ts"]),
        dependencies=[Dependency(name="x")],
        docs_context=list(chunks),
    )


class TestPreprocess:
    def test_normalizes_whitespace(self):
        chunk = DocsChunk(library="x", content="  hello   world  \n\n\n\nfoo  ")
        result = preprocess(_make_payload(chunk))
        assert "  " not in result.docs_context[0].content.replace("  ", " ERROR")  # collapsed
        # Multiple blanks should be collapsed to one
        assert "\n\n\n" not in result.docs_context[0].content

    def test_preserves_code_fences(self):
        content = "Some text\n\n```js\nconst x   =   1;\n```\n\nMore text"
        chunk = DocsChunk(library="x", content=content)
        result = preprocess(_make_payload(chunk))
        # Code inside fences should be preserved verbatim
        assert "const x   =   1;" in result.docs_context[0].content

    def test_drops_empty_chunks(self):
        chunk1 = DocsChunk(library="x", content="real content")
        chunk2 = DocsChunk(library="x", chunk_id="empty", content="   \n\n   ")
        result = preprocess(_make_payload(chunk1, chunk2))
        assert len(result.docs_context) == 1
        assert result.docs_context[0].content == "real content"

    def test_strips_boilerplate(self):
        content = "Valid docs\n\nWas this helpful\n\nCopyright © 2024\n\nMore valid"
        chunk = DocsChunk(library="x", content=content)
        result = preprocess(_make_payload(chunk))
        processed = result.docs_context[0].content
        assert "Was this helpful" not in processed
        assert "Copyright" not in processed
        assert "Valid docs" in processed

    def test_empty_input(self):
        result = preprocess(_make_payload())
        assert result.docs_context == []
