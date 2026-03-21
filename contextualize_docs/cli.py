"""CLI entrypoint for the docs compiler.

Can be invoked as::

    python -m contextualize_docs --input payload.json --output-dir .contextualize

Or via stdin::

    cat payload.json | python -m contextualize_docs --output-dir .contextualize
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


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="contextualize-docs",
        description="Compile agent-native context cards from task + docs + repo evidence.",
    )
    p.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to input JSON file. Reads stdin if omitted.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Root output directory (typically .contextualize).",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable debug logging.",
    )
    return p


def _read_input(path: Path | None) -> str:
    """Read JSON string from file or stdin."""
    if path is not None:
        if not path.is_file():
            logger.error("Input file does not exist: %s", path)
            sys.exit(1)
        return path.read_text(encoding="utf-8")
    # stdin
    if sys.stdin.isatty():
        logger.error("No --input file specified and stdin is a terminal. Provide input JSON.")
        sys.exit(1)
    return sys.stdin.read()


def _make_provider(config: AppConfig, requested_provider: str) -> LLMProvider:
    """Instantiate the appropriate LLM provider.

    Priority:
    1. ``vercel`` (default) — uses VERCEL_AI_GATEWAY_KEY
    2. ``gemini`` — uses GEMINI_API_KEY directly via google-genai SDK
    """
    from contextualize_docs.providers.vercel_gateway_provider import VercelGatewayProvider

    # Normalise requested_provider
    provider_name = requested_provider.lower().strip()

    if provider_name in ("vercel", "vercel_gateway", ""):
        if config.vercel_gateway_key:
            return VercelGatewayProvider(config)
        # Fall through to Gemini SDK if Vercel key not set
        logger.warning(
            "VERCEL_AI_GATEWAY_KEY not set; attempting direct Gemini SDK fallback."
        )
        provider_name = "gemini"

    if provider_name == "gemini":
        from contextualize_docs.providers.gemini_provider import GeminiProvider
        return GeminiProvider(config)

    raise ProviderError(f"Unknown provider '{requested_provider}'. Supported: 'vercel', 'gemini'.")


def main() -> None:
    """Main entry point — parse args, validate input, run pipeline, emit result."""
    args = _build_parser().parse_args()
    setup_logging(verbose=args.verbose)

    # --- Load config ---
    config = AppConfig.from_env()

    # --- Read & validate input ---
    raw = _read_input(args.input)
    try:
        raw_json = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Input is not valid JSON: %s", exc)
        sys.exit(1)

    try:
        payload = ContextualizeInput.model_validate(raw_json)
    except ValidationError as exc:
        logger.error("Input validation failed:\n%s", exc)
        # Emit structured error on stdout for Node CLI
        error_out = {
            "success": False,
            "error": "input_validation_failed",
            "details": exc.errors(),
        }
        print(json.dumps(error_out, indent=2, default=str))
        sys.exit(1)

    # --- Instantiate provider ---
    try:
        provider = _make_provider(config, payload.generation_config.llm_provider)
    except ProviderError as exc:
        logger.error("Provider initialization failed: %s", exc)
        error_out = {"success": False, "error": "provider_init_failed", "details": str(exc)}
        print(json.dumps(error_out, indent=2))
        sys.exit(1)

    # Override model if input specifies one (supported by both providers)
    if payload.generation_config.llm_model:
        cast_provider = provider  # type: ignore[assignment]
        if hasattr(cast_provider, "_model"):
            cast_provider._model = payload.generation_config.llm_model  # noqa: SLF001

    # --- Run pipeline ---
    try:
        summary = asyncio.run(
            run_pipeline(
                payload=payload,
                provider=provider,
                output_dir=args.output_dir,
                config=config,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed with an unexpected error.")
        error_out = {"success": False, "error": "pipeline_failed", "details": str(exc)}
        print(json.dumps(error_out, indent=2))
        sys.exit(1)

    # --- Emit summary on stdout ---
    print(json.dumps(summary.model_dump(), indent=2, default=str))

    if not summary.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
