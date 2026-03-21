"""CLI entrypoint for the docs compiler.

Two modes:
    compile              — reads pre-built input JSON, runs pipeline
    compile-from-deps    — reads dependencies.json, fetches real docs, runs pipeline

Usage::

    python -m contextualize_docs compile \\
        --input payload.json --output-dir .contextualize

    python -m contextualize_docs compile-from-deps \\
        --deps-file .contextualize/scan/dependencies.json \\
        --output-dir .contextualize \\
        --task "Add password reset flow"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from contextualize_docs.config import AppConfig
from contextualize_docs.logging_config import get_logger, setup_logging
from contextualize_docs.models.input_models import ContextualizeInput
from contextualize_docs.pipeline.orchestrator import run_pipeline
from contextualize_docs.providers.base import LLMProvider, ProviderError

logger = get_logger("cli")


# ------------------------------------------------------------------ #
# Argument parser                                                      #
# ------------------------------------------------------------------ #

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="contextualize-docs",
        description="Compile agent-native context cards from task + docs + repo evidence.",
    )
    sub = p.add_subparsers(dest="command")

    # ---- compile: pre-built input JSON ----
    from_input = sub.add_parser(
        "compile",
        help="Compile cards from a pre-built input JSON.",
    )
    from_input.add_argument(
        "--input", type=Path, default=None,
        help="Path to input JSON file. Reads stdin if omitted.",
    )
    from_input.add_argument(
        "--output-dir", type=Path, required=True,
        help="Root output directory (typically .contextualize).",
    )
    from_input.add_argument("--verbose", "-v", action="store_true", default=False)

    # ---- compile-from-deps: auto-fetch from dependencies.txt ----
    from_deps = sub.add_parser(
        "compile-from-deps",
        help="Read dependencies.txt, fetch real docs, compile cards automatically.",
    )
    from_deps.add_argument(
        "--deps-file", type=Path,
        default=Path(".contextualize/scan/dependencies.json"),
        help="Path to dependencies.json.",
    )
    from_deps.add_argument(
        "--output-dir", type=Path, required=True,
        help="Root output directory (typically .contextualize).",
    )
    from_deps.add_argument(
        "--task", type=str, default="Implement feature",
        help="Short task title, e.g. 'Add password reset flow'.",
    )
    from_deps.add_argument(
        "--task-desc", type=str, default="",
        help="Longer description of the coding task.",
    )
    from_deps.add_argument(
        "--project-root", type=Path, default=Path("."),
        help="Root of the project being analysed (default: cwd).",
    )
    from_deps.add_argument("--verbose", "-v", action="store_true", default=False)

    # Legacy flat interface (no subcommand) — kept for backwards compat
    p.add_argument("--input", type=Path, default=None, help=argparse.SUPPRESS)
    p.add_argument("--output-dir", type=Path, default=None, help=argparse.SUPPRESS)
    p.add_argument("--verbose", "-v", action="store_true", default=False, help=argparse.SUPPRESS)

    return p


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _read_input(path: Path | None) -> str:
    """Read JSON string from file or stdin."""
    if path is not None:
        if not path.is_file():
            logger.error("Input file does not exist: %s", path)
            sys.exit(1)
        return path.read_text(encoding="utf-8")
    if sys.stdin.isatty():
        logger.error("No --input file specified and stdin is a terminal. Provide input JSON.")
        sys.exit(1)
    return sys.stdin.read()


def _make_provider(config: AppConfig, requested_provider: str) -> LLMProvider:
    """Instantiate the appropriate LLM provider.

    Priority:
    1. vercel  — uses VERCEL_AI_GATEWAY_KEY
    2. gemini  — uses GEMINI_API_KEY directly via google-genai SDK
    """
    from contextualize_docs.providers.vercel_gateway_provider import VercelGatewayProvider

    provider_name = requested_provider.lower().strip()

    if provider_name in ("vercel", "vercel_gateway", ""):
        if config.vercel_gateway_key:
            return VercelGatewayProvider(config)
        logger.warning("VERCEL_AI_GATEWAY_KEY not set; attempting direct Gemini SDK fallback.")
        provider_name = "gemini"

    if provider_name == "gemini":
        from contextualize_docs.providers.gemini_provider import GeminiProvider
        return GeminiProvider(config)

    raise ProviderError(
        f"Unknown provider '{requested_provider}'. Supported: 'vercel', 'gemini'."
    )


def _run_pipeline_and_emit(
    output_dir: Path,
    config: AppConfig,
    payload: ContextualizeInput,
) -> None:
    """Instantiate provider, run pipeline, emit JSON summary on stdout."""
    try:
        provider = _make_provider(config, payload.generation_config.llm_provider)
    except ProviderError as exc:
        logger.error("Provider initialization failed: %s", exc)
        print(json.dumps({"success": False, "error": "provider_init_failed", "details": str(exc)}, indent=2))
        sys.exit(1)

    # Allow input JSON to override model
    if payload.generation_config.llm_model:
        if hasattr(provider, "set_model"):
            provider.set_model(payload.generation_config.llm_model)  # type: ignore[attr-defined]
        elif hasattr(provider, "_model"):
            provider._model = payload.generation_config.llm_model  # noqa: SLF001

    try:
        summary = asyncio.run(
            run_pipeline(
                payload=payload,
                provider=provider,
                output_dir=output_dir,
                config=config,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed with an unexpected error.")
        print(json.dumps({"success": False, "error": "pipeline_failed", "details": str(exc)}, indent=2))
        sys.exit(1)

    print(json.dumps(summary.model_dump(), indent=2, default=str))
    if not summary.success:
        sys.exit(1)


# ------------------------------------------------------------------ #
# Command handlers                                                     #
# ------------------------------------------------------------------ #

def _handle_compile(args: argparse.Namespace, config: AppConfig) -> None:
    """compile: run pipeline from a pre-built JSON payload."""
    raw = _read_input(getattr(args, "input", None))
    try:
        raw_json = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Input is not valid JSON: %s", exc)
        sys.exit(1)

    try:
        payload = ContextualizeInput.model_validate(raw_json)
    except ValidationError as exc:
        logger.error("Input validation failed:\n%s", exc)
        print(json.dumps({
            "success": False,
            "error": "input_validation_failed",
            "details": exc.errors(),
        }, indent=2, default=str))
        sys.exit(1)

    _run_pipeline_and_emit(args.output_dir, config, payload)


def _handle_compile_from_deps(args: argparse.Namespace, config: AppConfig) -> None:
    """compile-from-deps: read dependencies.txt, fetch real docs, run pipeline."""
    from contextualize_docs.fetcher.deps_reader import read_dependencies
    from contextualize_docs.fetcher.input_builder import build_input_from_deps

    try:
        names = read_dependencies(args.deps_file)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        print(json.dumps({"success": False, "error": "deps_file_not_found", "details": str(exc)}, indent=2))
        sys.exit(1)

    if not names:
        logger.error("dependencies.txt is empty — nothing to process.")
        sys.exit(1)

    logger.info("Processing %d libraries from %s", len(names), args.deps_file)

    try:
        payload = asyncio.run(
            build_input_from_deps(
                library_entries=names,
                task_title=args.task,
                task_description=args.task_desc or args.task,
                project_root=args.project_root,
                llm_provider=config.default_llm_provider,
                llm_model=config.default_llm_model,
                max_cards=min(len(names), 10),
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to build input payload from dependencies.")
        print(json.dumps({"success": False, "error": "input_build_failed", "details": str(exc)}, indent=2))
        sys.exit(1)

    _run_pipeline_and_emit(args.output_dir, config, payload)


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def main() -> None:
    """Parse args and dispatch to the appropriate handler."""
    args = _build_parser().parse_args()
    setup_logging(verbose=args.verbose)
    config = AppConfig.from_env()

    if args.command == "compile-from-deps":
        _handle_compile_from_deps(args, config)
    else:
        # "compile" subcommand OR legacy flat interface
        _handle_compile(args, config)


if __name__ == "__main__":
    main()
