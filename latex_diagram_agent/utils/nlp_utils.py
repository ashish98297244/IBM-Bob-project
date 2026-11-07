"""
nlp_utils.py — Natural-language processing helpers.

Handles intent classification, sketch-to-description conversion,
and command parsing for the refinement loop.
"""

from __future__ import annotations

import re
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

class RefinementIntent(Enum):
    """High-level category of a user refinement command."""
    STYLE       = auto()   # colour, font, thickness
    LAYOUT      = auto()   # move, resize, align, space
    ADD         = auto()   # add a node / edge / label / legend
    REMOVE      = auto()   # remove / delete something
    LABEL       = auto()   # change text on a node or edge
    SCALE       = auto()   # make bigger / smaller / zoom
    COLOUR      = auto()   # specific colour changes
    ANNOTATE    = auto()   # add annotations, captions, titles
    REDRAW      = auto()   # start over / completely redo
    UNKNOWN     = auto()


_INTENT_PATTERNS: list[tuple[RefinementIntent, list[str]]] = [
    (RefinementIntent.STYLE,    ["style", "bold", "dashed", "dotted", "thick", "thin", "font"]),
    (RefinementIntent.LAYOUT,   ["move", "shift", "align", "spacing", "position", "layout",
                                  "arrange", "centre", "center", "above", "below", "left", "right"]),
    (RefinementIntent.ADD,      ["add", "insert", "include", "put", "place", "append", "draw"]),
    (RefinementIntent.REMOVE,   ["remove", "delete", "erase", "hide", "eliminate", "take out"]),
    (RefinementIntent.LABEL,    ["label", "rename", "text", "caption", "title", "call it",
                                  "change the name"]),
    (RefinementIntent.SCALE,    ["bigger", "smaller", "scale", "zoom", "enlarge", "shrink",
                                  "resize", "larger"]),
    (RefinementIntent.COLOUR,   ["colour", "color", "red", "blue", "green", "yellow", "black",
                                  "white", "grey", "gray", "fill"]),
    (RefinementIntent.ANNOTATE, ["annotate", "note", "comment", "explain", "description",
                                  "legend", "key"]),
    (RefinementIntent.REDRAW,   ["redo", "start over", "rebuild", "regenerate", "completely",
                                  "from scratch"]),
]


def classify_intent(instruction: str) -> RefinementIntent:
    """
    Classify the user's refinement instruction into an intent category.

    Parameters
    ----------
    instruction : str
        Plain-English refinement command.

    Returns
    -------
    RefinementIntent
        The most likely intent (UNKNOWN if no match).
    """
    text = instruction.lower()
    scores: dict[RefinementIntent, int] = {}

    for intent, keywords in _INTENT_PATTERNS:
        score = sum(1 for kw in keywords if kw in text)
        if score:
            scores[intent] = score

    if not scores:
        return RefinementIntent.UNKNOWN

    return max(scores, key=lambda i: scores[i])


# ---------------------------------------------------------------------------
# Sketch / ASCII → description converter
# ---------------------------------------------------------------------------

def ascii_sketch_to_description(sketch: str) -> str:
    """
    Convert a simple ASCII sketch into a plain-English description
    that can be fed to the diagram agent.

    This does basic pattern recognition — boxes, arrows, labels.

    Parameters
    ----------
    sketch : str
        Multi-line ASCII art / rough sketch.

    Returns
    -------
    str
        A prose description of the detected elements.
    """
    lines = sketch.strip().splitlines()
    nodes: list[str] = []
    edges: list[tuple[str, str]] = []

    # Detect box labels:  [Label] or (Label)
    box_re = re.compile(r"[\[\(]([^\]\)]+)[\]\)]")
    # Detect arrow patterns: A -> B  or  A --> B  or  A => B
    arrow_re = re.compile(
        r"[\[\(]?([A-Za-z0-9 _]+)[\]\)]?\s*(?:-->?|==>?|→)\s*[\[\(]?([A-Za-z0-9 _]+)[\]\)]?"
    )

    for line in lines:
        for m in box_re.finditer(line):
            label = m.group(1).strip()
            if label and label not in nodes:
                nodes.append(label)
        for m in arrow_re.finditer(line):
            src, dst = m.group(1).strip(), m.group(2).strip()
            edges.append((src, dst))

    parts: list[str] = []
    if nodes:
        parts.append(f"Nodes: {', '.join(nodes)}.")
    if edges:
        edge_strs = [f"'{s}' points to '{d}'" for s, d in edges]
        parts.append(f"Connections: {'; '.join(edge_strs)}.")
    if not parts:
        parts.append("Custom diagram based on the provided sketch.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Command parsing for the CLI / REPL
# ---------------------------------------------------------------------------

class ParsedCommand:
    """Represents a parsed user command in the interactive loop."""

    __slots__ = ("action", "text", "raw")

    # Recognised actions
    GENERATE  = "generate"
    REFINE    = "refine"
    SAVE      = "save"
    SHOW      = "show"
    HISTORY   = "history"
    TEMPLATE  = "template"
    QUIT      = "quit"
    HELP      = "help"

    def __init__(self, action: str, text: str = "", raw: str = "") -> None:
        self.action = action
        self.text   = text
        self.raw    = raw

    def __repr__(self) -> str:
        return f"ParsedCommand(action={self.action!r}, text={self.text[:60]!r})"


_COMMAND_ALIASES: dict[str, str] = {
    "/generate": ParsedCommand.GENERATE,
    "/gen":      ParsedCommand.GENERATE,
    "/refine":   ParsedCommand.REFINE,
    "/r":        ParsedCommand.REFINE,
    "/save":     ParsedCommand.SAVE,
    "/show":     ParsedCommand.SHOW,
    "/s":        ParsedCommand.SHOW,
    "/history":  ParsedCommand.HISTORY,
    "/h":        ParsedCommand.HISTORY,
    "/template": ParsedCommand.TEMPLATE,
    "/t":        ParsedCommand.TEMPLATE,
    "/quit":     ParsedCommand.QUIT,
    "/exit":     ParsedCommand.QUIT,
    "/q":        ParsedCommand.QUIT,
    "/help":     ParsedCommand.HELP,
    "/?":        ParsedCommand.HELP,
}


def parse_command(raw: str) -> ParsedCommand:
    """
    Parse a raw line of user input into a `ParsedCommand`.

    Lines that start with '/' are treated as explicit commands.
    All other lines are treated as refinement instructions if a
    session is active, or generation requests otherwise.

    Parameters
    ----------
    raw : str
        Raw user input line.

    Returns
    -------
    ParsedCommand
    """
    stripped = raw.strip()

    if not stripped:
        return ParsedCommand(action=ParsedCommand.HELP, raw=raw)

    # Slash-command detection
    parts = stripped.split(maxsplit=1)
    cmd_token = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if cmd_token in _COMMAND_ALIASES:
        return ParsedCommand(
            action=_COMMAND_ALIASES[cmd_token],
            text=rest,
            raw=raw,
        )

    # No slash-command — treat as plain text (generate or refine)
    return ParsedCommand(action=ParsedCommand.REFINE, text=stripped, raw=raw)
