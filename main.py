"""
main.py — Interactive CLI entry point for the AI-Powered LaTeX Diagram Generator.

Run with:
    python main.py

Commands available in the REPL:
    /generate <description>   Generate a new diagram from a description
    /refine   <instruction>   Refine the current diagram
    /show                     Print the current TikZ code
    /save     [filename]      Save to a custom filename
    /history                  Show all iterations in this session
    /template <type>          Insert a starter template
    /help                     Print this help
    /quit                     Exit
"""

from __future__ import annotations

import logging
import sys
import textwrap
from pathlib import Path
from typing import Optional

# Force UTF-8 output on Windows so Unicode symbols (✓ ✗ ► …) render correctly
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from latex_diagram_agent.config import get_config
from latex_diagram_agent.core.diagram_agent import DiagramAgent, DiagramResult
from latex_diagram_agent.generators.tikz_generator import detect_diagram_type, get_template, post_process
from latex_diagram_agent.utils.nlp_utils import ParsedCommand, classify_intent, parse_command
from latex_diagram_agent.utils.file_utils import save_tex, timestamped_stem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ANSI colour helpers (degrade gracefully on Windows without ANSI support)
# ---------------------------------------------------------------------------

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_CYAN   = "\033[36m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_BLUE   = "\033[34m"
_DIM    = "\033[2m"


def _c(text: str, colour: str) -> str:
    """Wrap text in an ANSI colour code."""
    try:
        import os
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass
    return f"{colour}{text}{_RESET}"


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

_HELP = f"""
{_c('AI-Powered LaTeX Diagram Generator', _BOLD + _CYAN)}
{_c('IBM Watson Studio  ·  IBM Granite Models', _DIM)}

{'─' * 62}
{_c('COMMANDS', _BOLD)}
  /generate <description>    Generate a diagram from scratch
  /refine   <instruction>    Refine the current diagram with plain English
  /show                      Print the current TikZ code to the terminal
  /save     [filename]       Save as <filename>.tex  (auto-named if omitted)
  /history                   List all generated versions in this session
  /template <type>           Load a starter template (flowchart, neural_network,
                              state_machine)
  /help  /?                  Show this help
  /quit  /exit               Exit

{_c('SHORTHAND', _BOLD)}
  Any input without a leading / is treated as a refinement command
  when a diagram session is active, or a generate command otherwise.

{_c('DIAGRAM TYPES', _BOLD)}
  flowchart · neural_network · graph · tree · state_machine ·
  sequence_diagram · plot · block_diagram · venn · timeline
{'─' * 62}
"""

# ---------------------------------------------------------------------------
# CLI loop
# ---------------------------------------------------------------------------

class DiagramCLI:
    """Interactive command-line interface for the diagram agent."""

    def __init__(self) -> None:
        print(_c("\n  Loading configuration …", _DIM))
        self._config = get_config()
        self._agent  = DiagramAgent(self._config)
        self._last_result: Optional[DiagramResult] = None
        print(_c("  ✓ Agent ready.\n", _GREEN))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        print(_HELP)
        while True:
            try:
                raw = input(_c("diagram> ", _BOLD + _BLUE)).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n" + _c("Goodbye.", _DIM))
                break

            if not raw:
                continue

            cmd = parse_command(raw)
            self._dispatch(cmd)

    # ------------------------------------------------------------------
    # Command dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, cmd: ParsedCommand) -> None:
        try:
            if cmd.action == ParsedCommand.HELP:
                print(_HELP)

            elif cmd.action == ParsedCommand.QUIT:
                print(_c("Goodbye.", _DIM))
                sys.exit(0)

            elif cmd.action == ParsedCommand.GENERATE:
                self._cmd_generate(cmd.text)

            elif cmd.action == ParsedCommand.REFINE:
                if self._last_result is None:
                    # No active session → treat as generate
                    self._cmd_generate(cmd.text)
                else:
                    self._cmd_refine(cmd.text)

            elif cmd.action == ParsedCommand.SHOW:
                self._cmd_show()

            elif cmd.action == ParsedCommand.SAVE:
                self._cmd_save(cmd.text)

            elif cmd.action == ParsedCommand.HISTORY:
                self._cmd_history()

            elif cmd.action == ParsedCommand.TEMPLATE:
                self._cmd_template(cmd.text)

            else:
                print(_c("Unknown command. Type /help for available commands.", _YELLOW))

        except EnvironmentError as exc:
            print(_c(f"\n[Config Error] {exc}\n", _RED))
        except RuntimeError as exc:
            print(_c(f"\n[Agent Error] {exc}\n", _RED))
        except KeyboardInterrupt:
            print(_c("\n[Cancelled]", _YELLOW))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error")
            print(_c(f"\n[Error] {exc}\n", _RED))

    # ------------------------------------------------------------------
    # Individual command handlers
    # ------------------------------------------------------------------

    def _cmd_generate(self, description: str) -> None:
        if not description:
            print(_c("Usage: /generate <plain-English description>", _YELLOW))
            return

        diagram_type = detect_diagram_type(description)
        if diagram_type:
            print(_c(f"  ► Detected diagram type: {diagram_type}", _DIM))

        print(_c("  ► Sending to IBM Granite …", _DIM))
        result = self._agent.generate(
            description=description,
            diagram_type=diagram_type,
        )
        # Post-process for clean output
        result.tikz_code = post_process(result.tikz_code, description)

        self._last_result = result
        self._print_result(result)

    def _cmd_refine(self, instruction: str) -> None:
        if not instruction:
            print(_c("Usage: /refine <plain-English instruction>", _YELLOW))
            return

        intent = classify_intent(instruction)
        print(_c(f"  ► Detected intent: {intent.name}", _DIM))
        print(_c("  ► Sending to IBM Granite …", _DIM))

        result = self._agent.refine(instruction)
        result.tikz_code = post_process(result.tikz_code)
        self._last_result = result
        self._print_result(result)

    def _cmd_show(self) -> None:
        if self._last_result is None:
            print(_c("No diagram generated yet. Use /generate first.", _YELLOW))
            return
        print("\n" + _c("── Current TikZ Code ──────────────────────────────", _DIM))
        print(self._last_result.tikz_code)
        print(_c("───────────────────────────────────────────────────\n", _DIM))

    def _cmd_save(self, filename: str) -> None:
        if self._last_result is None:
            print(_c("Nothing to save. Use /generate first.", _YELLOW))
            return

        session = self._agent.get_session()
        if filename:
            stem = Path(filename).stem
        else:
            base = session.original_description[:30].replace(" ", "_") if session else "diagram"
            stem = timestamped_stem(base)

        path = save_tex(self._last_result.tikz_code, self._config.output_dir, stem)
        print(_c(f"  ✓ Saved to: {path}", _GREEN))

        # Optional: compile to PDF
        if self._config.enable_local_compilation:
            self._try_compile(path)

    def _cmd_history(self) -> None:
        session = self._agent.get_session()
        if session is None or not session.history:
            print(_c("No session active. Use /generate first.", _YELLOW))
            return

        print(_c("\n── Session History ──────────────────────────────────", _DIM))
        print(f"  Description: {session.original_description[:80]}")
        print(f"  Iterations : {session.iteration_count}")
        for i, r in enumerate(session.history):
            valid_str = _c("✓ valid", _GREEN) if r.is_valid else _c("⚠ issues", _YELLOW)
            file_str  = str(r.output_file) if r.output_file else "—"
            print(f"  [{i}] {valid_str}  |  {file_str}")
        print(_c("─────────────────────────────────────────────────────\n", _DIM))

    def _cmd_template(self, diagram_type: str) -> None:
        if not diagram_type:
            print(_c("Usage: /template <type>  (flowchart | neural_network | state_machine)", _YELLOW))
            return

        tmpl = get_template(diagram_type)
        if tmpl is None:
            print(_c(f"No template for '{diagram_type}'. Try: flowchart, neural_network, state_machine", _YELLOW))
            return

        print(_c(f"\n── Template: {diagram_type} ──────────────────────────", _DIM))
        print(tmpl)
        print(_c("─────────────────────────────────────────────────────\n", _DIM))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _print_result(self, result: DiagramResult) -> None:
        status = _c("✓ Valid", _GREEN) if result.is_valid else _c("⚠ Review", _YELLOW)
        print(f"\n  {status}  |  Iteration v{result.iteration}")
        if result.output_file:
            print(_c(f"  ✓ Saved  → {result.output_file}", _GREEN))
        if result.validation_notes:
            print(_c(f"  ℹ  {result.validation_notes}", _DIM))

        # Print a preview (first 20 lines)
        preview_lines = result.tikz_code.splitlines()[:20]
        preview = "\n".join(preview_lines)
        if len(result.tikz_code.splitlines()) > 20:
            preview += f"\n{_c('  … (use /show to see full code)', _DIM)}"
        print("\n" + textwrap.indent(preview, "  ") + "\n")

    def _try_compile(self, tex_path: Path) -> None:
        from latex_diagram_agent.utils.file_utils import compile_to_pdf
        try:
            pdf = compile_to_pdf(tex_path, self._config.latex_compiler, self._config.latex_temp_dir)
            print(_c(f"  ✓ PDF compiled → {pdf}", _GREEN))
        except FileNotFoundError:
            print(_c(f"  ⚠  {self._config.latex_compiler} not found on PATH — skipping PDF.", _YELLOW))
        except Exception as exc:  # noqa: BLE001
            print(_c(f"  ⚠  PDF compilation failed: {exc}", _YELLOW))


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cli = DiagramCLI()
    cli.run()


if __name__ == "__main__":
    main()
