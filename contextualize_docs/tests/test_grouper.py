"""Tests for the evidence grouping stage."""

from __future__ import annotations

from contextualize_docs.models.input_models import (
    ContextualizeInput,
    Dependency,
    DocsChunk,
    RepoContext,
    TaskInfo,
    UsageSnippet,
)
from contextualize_docs.pipeline.grouper import group_evidence


def _make_payload(
    deps: list[Dependency],
    chunks: list[DocsChunk] | None = None,
    snippets: list[UsageSnippet] | None = None,
) -> ContextualizeInput:
    return ContextualizeInput(
        task=TaskInfo(id="t1", title="T", description="d", goal="g"),
        repo_context=RepoContext(
            project_name="p",
            languages=["ts"],
            usage_snippets=snippets or [],
        ),
        dependencies=deps,
        docs_context=chunks or [],
    )


class TestGroupEvidence:
    def test_basic_grouping(self):
        deps = [Dependency(name="zod"), Dependency(name="@supabase/supabase-js")]
        chunks = [
            DocsChunk(library="zod", content="zod docs"),
            DocsChunk(library="@supabase/supabase-js", content="supabase docs"),
        ]
        bundles = group_evidence(_make_payload(deps, chunks))
        assert len(bundles) == 2
        names = {b.dependency.name for b in bundles}
        assert names == {"zod", "@supabase/supabase-js"}

    def test_multiple_chunks_per_dep(self):
        deps = [Dependency(name="zod")]
        chunks = [
            DocsChunk(library="zod", content="chunk 1"),
            DocsChunk(library="zod", content="chunk 2"),
        ]
        bundles = group_evidence(_make_payload(deps, chunks))
        assert len(bundles) == 1
        assert len(bundles[0].docs_chunks) == 2

    def test_snippet_assignment(self):
        deps = [Dependency(name="zod")]
        snippets = [
            UsageSnippet(library="zod", file="f.ts", code="z.string()"),
        ]
        bundles = group_evidence(_make_payload(deps, snippets=snippets))
        assert len(bundles[0].usage_snippets) == 1

    def test_unmatched_chunk_creates_implicit_bundle(self):
        deps = [Dependency(name="zod")]
        chunks = [
            DocsChunk(library="some-unknown-lib", content="docs"),
        ]
        bundles = group_evidence(_make_payload(deps, chunks))
        # zod + implicit bundle for some-unknown-lib
        assert len(bundles) == 2

    def test_empty_deps(self):
        bundles = group_evidence(_make_payload([]))
        assert len(bundles) == 0

    def test_has_evidence_flag(self):
        deps = [Dependency(name="zod")]
        bundles = group_evidence(_make_payload(deps))
        assert len(bundles) == 1
        assert bundles[0].has_evidence is False

        chunks = [DocsChunk(library="zod", content="docs")]
        bundles = group_evidence(_make_payload(deps, chunks))
        assert bundles[0].has_evidence is True

    def test_normalized_matching(self):
        """@scope/lib-name should match docs that reference @scope/lib-name."""
        deps = [Dependency(name="@tanstack/react-query")]
        chunks = [DocsChunk(library="@tanstack/react-query", content="docs")]
        bundles = group_evidence(_make_payload(deps, chunks))
        assert len(bundles) == 1
        assert bundles[0].has_evidence is True
