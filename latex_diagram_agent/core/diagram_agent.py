"""
diagram_agent.py — The central orchestrator for the LaTeX Diagram Generator.

Coordinates user input → prompt building → Granite inference →
TikZ extraction → validation → refinement loop → file output.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from latex_diagram_agent.config import Config
from latex_diagram_agent.core.granite_client import GraniteClient
from latex_diagram_agent.core.prompt_builder import (
    build_generation_prompt,
    build_refinement_prompt,
    build_validation_prompt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DiagramResult:
    """Holds the output of one generation / refinement cycle."""

    tikz_code: str                      # Extracted TikZ / LaTeX code
    raw_response: str                   # Full model response (for debugging)
    iteration: int = 0                  # Which refinement iteration produced this
    is_valid: bool = True               # Did it pass validation?
    validation_notes: str = ""          # Any validation feedback
    output_file: Optional[Path] = None  # Path to saved .tex file


@dataclass
class DiagramSession:
    """Tracks the full conversation history for a diagram."""

    original_description: str
    diagram_type: Optional[str] = None
    history: List[DiagramResult] = field(default_factory=list)

    @property
    def current_code(self) -> str:
        """Return the most recently generated TikZ code."""
        return self.history[-1].tikz_code if self.history else ""

    @property
    def iteration_count(self) -> int:
        return len(self.history)


# ---------------------------------------------------------------------------
# TikZ extraction helper
# ---------------------------------------------------------------------------

_LATEX_FENCE_RE = re.compile(
    r"```(?:latex|tex)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_tikz(response: str) -> str:
    """
    Pull the LaTeX code block out of Granite's response.
    Falls back to returning the raw response if no fenced block is found.
    """
    match = _LATEX_FENCE_RE.search(response)
    if match:
        return match.group(1).strip()
    # Heuristic: if response contains \documentclass, treat whole thing as code
    if r"\documentclass" in response:
        return response.strip()
    logger.warning("No fenced LaTeX block found in response; using raw output.")
    return response.strip()


# ---------------------------------------------------------------------------
# DiagramAgent
# ---------------------------------------------------------------------------

class DiagramAgent:
    """
    AI-Powered LaTeX Diagram Generator Agent.

    Workflow
    --------
    1. User provides a natural-language description.
    2. Agent builds a structured prompt and sends it to IBM Granite.
    3. TikZ code is extracted and optionally validated.
    4. User can issue plain-English refinement commands; agent loops.
    5. Final code is saved to an output .tex file.

    Parameters
    ----------
    config : Config
        Application configuration (credentials, paths, model settings).
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = GraniteClient(config)
        self._session: Optional[DiagramSession] = None
        logger.info("DiagramAgent initialised.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(
        self,
        description: str,
        diagram_type: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> DiagramResult:
        """
        Generate a TikZ diagram from a plain-English description.

        Parameters
        ----------
        description : str
            What the diagram should show.
        diagram_type : str, optional
            Category hint: 'flowchart', 'neural_network', 'graph', etc.
        extra_context : str, optional
            Extra styling / size / colour constraints.

        Returns
        -------
        DiagramResult
        """
        logger.info("Generating diagram: '%s'", description[:80])

        self._session = DiagramSession(
            original_description=description,
            diagram_type=diagram_type,
        )

        prompt = build_generation_prompt(description, diagram_type, extra_context)
        raw = self._client.generate(prompt)
        tikz = _extract_tikz(raw)

        result = DiagramResult(tikz_code=tikz, raw_response=raw, iteration=0)

        if self._config.enable_latex_validation:
            result = self._validate(result)

        self._session.history.append(result)
        result.output_file = self._save(result, label="v0")
        logger.info("Initial diagram saved to %s", result.output_file)
        return result

    def refine(self, instruction: str) -> DiagramResult:
        """
        Refine the current diagram with a plain-English instruction.

        Must be called after `generate()`.

        Parameters
        ----------
        instruction : str
            E.g. "Make the arrows blue and add a legend at the bottom."

        Returns
        -------
        DiagramResult
        """
        if self._session is None or not self._session.history:
            raise RuntimeError("Call generate() before refine().")

        n = self._session.iteration_count
        if n >= self._config.max_refinement_iterations:
            raise RuntimeError(
                f"Maximum refinement iterations ({self._config.max_refinement_iterations}) reached."
            )

        logger.info("Refinement #%d: '%s'", n, instruction[:80])

        prompt = build_refinement_prompt(
            original_description=self._session.original_description,
            current_tikz_code=self._session.current_code,
            refinement_instruction=instruction,
        )
        raw = self._client.generate(prompt)
        tikz = _extract_tikz(raw)

        result = DiagramResult(tikz_code=tikz, raw_response=raw, iteration=n)

        if self._config.enable_latex_validation:
            result = self._validate(result)

        self._session.history.append(result)
        result.output_file = self._save(result, label=f"v{n}")
        logger.info("Refined diagram (v%d) saved to %s", n, result.output_file)
        return result

    def get_session(self) -> Optional[DiagramSession]:
        """Return the current session (history of all iterations)."""
        return self._session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate(self, result: DiagramResult) -> DiagramResult:
        """
        Send the generated TikZ to Granite for syntax validation.
        Updates `result` in-place and returns it.
        """
        logger.info("Validating TikZ code with Granite …")
        prompt = build_validation_prompt(result.tikz_code)
        response = self._client.generate(prompt)

        if response.strip().upper() == "VALID":
            result.is_valid = True
            result.validation_notes = "Granite validation passed."
            logger.info("Validation: PASSED")
        elif r"\documentclass" in response or "```" in response:
            # Model returned corrected code
            corrected = _extract_tikz(response)
            logger.info("Validation: corrections applied by Granite.")
            result.tikz_code = corrected
            result.is_valid = True
            result.validation_notes = "Granite auto-corrected the code."
        else:
            result.is_valid = False
            result.validation_notes = response[:500]
            logger.warning("Validation: potential issues found — %s", response[:200])

        return result

    def _save(self, result: DiagramResult, label: str = "diagram") -> Path:
        """
        Save `result.tikz_code` to a .tex file in the output directory.

        Returns
        -------
        Path
            Absolute path to the saved file.
        """
        safe_desc = re.sub(r"[^a-zA-Z0-9_\-]", "_", self._session.original_description[:40])
        filename = f"{safe_desc}_{label}.tex"
        out_path = self._config.output_dir / filename

        out_path.write_text(result.tikz_code, encoding="utf-8")
        return out_path
