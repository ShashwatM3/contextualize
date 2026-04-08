"""Configuration management for the docs compiler."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _find_env_file() -> Path | None:
    """Walk upward from CWD looking for ``.env.local``."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".env.local"
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True)
class AppConfig:
    """Immutable runtime configuration loaded from env + defaults."""

    # LLM — OpenAI
    openai_api_key: str = ""
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = 0.2
    llm_max_retries: int = 3
    llm_timeout_seconds: float = 120.0

    # Output
    output_subdir: str = "docs"  # nested under .contextualize/

    # Quality thresholds
    min_confidence_threshold: float = 0.3
    max_relevant_apis: int = 5
    max_rules_for_agent: int = 6

    @classmethod
    def from_env(cls) -> AppConfig:
        """Build config by loading ``.env.local`` then reading env vars."""
        env_file = _find_env_file()
        if env_file is not None:
            load_dotenv(env_file, override=False)

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            default_llm_model=os.getenv("CONTEXTUALIZE_LLM_MODEL", cls.default_llm_model),
            llm_temperature=float(os.getenv("CONTEXTUALIZE_LLM_TEMP", str(cls.llm_temperature))),
            llm_max_retries=int(os.getenv("CONTEXTUALIZE_LLM_RETRIES", str(cls.llm_max_retries))),
            llm_timeout_seconds=float(os.getenv("CONTEXTUALIZE_LLM_TIMEOUT", str(cls.llm_timeout_seconds))),
            min_confidence_threshold=float(
                os.getenv("CONTEXTUALIZE_MIN_CONFIDENCE", str(cls.min_confidence_threshold))
            ),
        )
