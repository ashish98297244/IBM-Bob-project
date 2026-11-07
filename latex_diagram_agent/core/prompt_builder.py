"""
prompt_builder.py — Constructs structured prompts for IBM Granite.

All prompt engineering lives here so that the model-calling code stays
clean and prompts can be iterated without touching business logic.
"""

from __future__ import annotations

from typing import List, Optional


# ---------------------------------------------------------------------------
# System / persona instruction
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
You are an expert LaTeX and TikZ programmer specialising in academic diagrams \
for scientific publications. Your sole task is to generate complete, \
compilable TikZ code based on the user's description.

Rules you MUST follow:
1. Output ONLY valid TikZ/PGF code wrapped in a LaTeX document skeleton.
2. Always wrap the TikZ picture inside a minimal but compilable LaTeX document \
   that uses \\documentclass{{standalone}} so it compiles without extra packages.
3. Include every \\usepackage{{...}} the diagram needs.
4. Do NOT include any explanation outside the code block.
5. Respond in this exact format:

```latex
<full compilable LaTeX document here>
```

6. If the description is ambiguous, make the most reasonable assumption and note \
   it as a LaTeX comment inside the code.
7. Use clean, well-commented TikZ code. Add \\% comments that explain sections.
"""

# ---------------------------------------------------------------------------
# Diagram-type hints injected into the prompt
# ---------------------------------------------------------------------------

_DIAGRAM_HINTS: dict[str, str] = {
    "flowchart": (
        "Use TikZ nodes with rectangle/diamond shapes, arrows between them, "
        "and the 'shapes.geometric' library."
    ),
    "neural_network": (
        "Use TikZ circles for neurons, layered x-positions, and 'foreach' loops "
        "to draw connections efficiently."
    ),
    "graph": (
        "Use 'tikz-network' style or plain TikZ nodes/edges. "
        "Label nodes clearly."
    ),
    "tree": (
        "Use the TikZ 'trees' library with child nodes syntax."
    ),
    "state_machine": (
        "Use 'automata' and 'positioning' libraries; 'state' style for nodes "
        "and 'edge' with bend for transitions."
    ),
    "sequence_diagram": (
        "Use the 'pgf-umlsd' or plain TikZ approach with vertical lifelines "
        "and horizontal arrows."
    ),
    "plot": (
        "Use the 'pgfplots' package with \\begin{axis} environment."
    ),
    "block_diagram": (
        "Use rectangular blocks connected by arrows; 'positioning' library "
        "to align blocks relative to each other."
    ),
    "venn": (
        "Use filled circles with transparency (fill opacity=0.3) and "
        "set intersection labels."
    ),
    "timeline": (
        "Draw a horizontal line with tick marks and annotation nodes above/below."
    ),
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def build_generation_prompt(
    description: str,
    diagram_type: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> str:
    """
    Build the full prompt for an *initial* TikZ diagram generation request.

    Parameters
    ----------
    description : str
        Plain-English description of the desired diagram.
    diagram_type : str, optional
        High-level category (e.g. 'flowchart', 'neural_network').
        When provided, type-specific hints are appended.
    extra_context : str, optional
        Any additional constraints (colour scheme, size, style, etc.).

    Returns
    -------
    str
        Fully-formatted prompt ready to send to Granite.
    """
    parts: List[str] = [_SYSTEM_INSTRUCTION, "\n"]

    parts.append("### User Request\n")
    parts.append(f"Description: {description.strip()}\n")

    if diagram_type:
        hint = _DIAGRAM_HINTS.get(diagram_type.lower().replace(" ", "_"), "")
        parts.append(f"Diagram type: {diagram_type}\n")
        if hint:
            parts.append(f"TikZ hint: {hint}\n")

    if extra_context:
        parts.append(f"Additional constraints: {extra_context.strip()}\n")

    parts.append("\n### TikZ Code\n")

    return "".join(parts)


def build_refinement_prompt(
    original_description: str,
    current_tikz_code: str,
    refinement_instruction: str,
) -> str:
    """
    Build the prompt for a *refinement* turn — the user wants to modify
    an existing diagram with a plain-English command.

    Parameters
    ----------
    original_description : str
        The description that produced `current_tikz_code`.
    current_tikz_code : str
        The TikZ code generated so far.
    refinement_instruction : str
        The user's plain-English modification request.

    Returns
    -------
    str
        Fully-formatted refinement prompt.
    """
    return (
        f"{_SYSTEM_INSTRUCTION}\n"
        "### Current Diagram Description\n"
        f"{original_description.strip()}\n\n"
        "### Current TikZ Code\n"
        f"```latex\n{current_tikz_code.strip()}\n```\n\n"
        "### Refinement Instruction\n"
        f"{refinement_instruction.strip()}\n\n"
        "Apply ONLY the requested change. Keep everything else identical.\n\n"
        "### Updated TikZ Code\n"
    )


def build_validation_prompt(tikz_code: str) -> str:
    """
    Ask Granite to review TikZ code for compilation errors.

    Returns
    -------
    str
        Prompt that asks the model to return corrected code or 'VALID'.
    """
    return (
        f"{_SYSTEM_INSTRUCTION}\n"
        "### Task: Validate & Auto-correct TikZ Code\n"
        "Review the following LaTeX/TikZ code for syntax errors, missing packages, "
        "or undefined commands. If there are errors, return the corrected compilable "
        "code. If the code is already valid, return exactly the word: VALID\n\n"
        f"```latex\n{tikz_code.strip()}\n```\n\n"
        "### Response\n"
    )
