"""
config.py — Centralised configuration loader.
Reads environment variables (from a .env file or the shell environment)
and exposes a single `Config` dataclass used everywhere in the project.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional dotenv support — gracefully skipped if package not installed
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on shell environment


def _require(key: str) -> str:
    """Return the value of a required environment variable or raise."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Copy env.example to .env and fill in your credentials."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """All runtime configuration for the LaTeX Diagram Agent."""

    # IBM WatsonX credentials
    watsonx_api_key: str = field(default_factory=lambda: _require("WATSONX_API_KEY"))
    watsonx_project_id: str = field(default_factory=lambda: _require("WATSONX_PROJECT_ID"))
    watsonx_url: str = field(
        default_factory=lambda: _optional("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    )

    # IBM Granite model
    granite_model_id: str = field(
        default_factory=lambda: _optional("GRANITE_MODEL_ID", "meta-llama/llama-3-3-70b-instruct")
    )

    # Inference hyper-parameters
    max_new_tokens: int = field(
        default_factory=lambda: int(_optional("GRANITE_MAX_NEW_TOKENS", "2048"))
    )
    min_new_tokens: int = field(
        default_factory=lambda: int(_optional("GRANITE_MIN_NEW_TOKENS", "50"))
    )
    temperature: float = field(
        default_factory=lambda: float(_optional("GRANITE_TEMPERATURE", "0.2"))
    )
    top_p: float = field(default_factory=lambda: float(_optional("GRANITE_TOP_P", "0.9")))
    top_k: int = field(default_factory=lambda: int(_optional("GRANITE_TOP_K", "50")))
    repetition_penalty: float = field(
        default_factory=lambda: float(_optional("GRANITE_REPETITION_PENALTY", "1.1"))
    )

    # Application settings
    app_env: str = field(default_factory=lambda: _optional("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: _optional("APP_LOG_LEVEL", "INFO"))
    output_dir: Path = field(
        default_factory=lambda: Path(_optional("OUTPUT_DIR", "outputs"))
    )
    max_refinement_iterations: int = field(
        default_factory=lambda: int(_optional("MAX_REFINEMENT_ITERATIONS", "10"))
    )
    enable_latex_validation: bool = field(
        default_factory=lambda: _optional("ENABLE_LATEX_VALIDATION", "true").lower() == "true"
    )

    # Local LaTeX compilation (optional)
    enable_local_compilation: bool = field(
        default_factory=lambda: _optional("ENABLE_LOCAL_COMPILATION", "false").lower() == "true"
    )
    latex_compiler: str = field(
        default_factory=lambda: _optional("LATEX_COMPILER", "pdflatex")
    )
    latex_temp_dir: Path = field(
        default_factory=lambda: Path(_optional("LATEX_TEMP_DIR", "outputs/temp"))
    )

    def __post_init__(self) -> None:
        # Ensure output directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.latex_temp_dir.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


# ---------------------------------------------------------------------------
# Module-level singleton — import this in other modules
# ---------------------------------------------------------------------------

def get_config() -> Config:
    """Return a Config instance. Raises EnvironmentError if credentials missing."""
    return Config()
