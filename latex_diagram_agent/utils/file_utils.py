"""
file_utils.py — File I/O utilities for saving, loading, and exporting diagrams.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Save / load helpers
# ---------------------------------------------------------------------------

def save_tex(code: str, output_dir: Path, stem: str) -> Path:
    """
    Write a .tex file.

    Parameters
    ----------
    code : str
        LaTeX / TikZ source code.
    output_dir : Path
        Target directory (must exist or will be created).
    stem : str
        Base filename without extension.

    Returns
    -------
    Path
        Path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}.tex"
    path.write_text(code, encoding="utf-8")
    return path


def save_session(session_data: dict, output_dir: Path, stem: str) -> Path:
    """
    Persist a diagram session as JSON for later inspection or resuming.

    Parameters
    ----------
    session_data : dict
        Serialisable session dictionary.
    output_dir : Path
    stem : str

    Returns
    -------
    Path
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}_session.json"
    path.write_text(json.dumps(session_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_session(path: Path) -> dict:
    """Load a previously saved session JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def timestamped_stem(base: str) -> str:
    """Return base_YYYYMMDD_HHMMSS."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{ts}"


# ---------------------------------------------------------------------------
# Local PDF compilation (optional)
# ---------------------------------------------------------------------------

def compile_to_pdf(
    tex_path: Path,
    compiler: str = "pdflatex",
    temp_dir: Optional[Path] = None,
) -> Path:
    """
    Compile a .tex file to PDF using a local LaTeX installation.

    Parameters
    ----------
    tex_path : Path
        Path to the .tex file.
    compiler : str
        LaTeX compiler binary (pdflatex, xelatex, lualatex).
    temp_dir : Path, optional
        Directory for intermediate files. Defaults to tex_path.parent.

    Returns
    -------
    Path
        Path to the generated .pdf file.

    Raises
    ------
    FileNotFoundError
        If the compiler binary is not found on PATH.
    subprocess.CalledProcessError
        If compilation fails.
    """
    work_dir = temp_dir or tex_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)

    # Copy source to work dir if needed
    src = work_dir / tex_path.name
    if src != tex_path:
        shutil.copy2(tex_path, src)

    cmd = [
        compiler,
        "-interaction=nonstopmode",
        "-output-directory", str(work_dir),
        str(src),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    pdf_path = work_dir / src.with_suffix(".pdf").name

    if result.returncode != 0:
        log_snippet = result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=log_snippet
        )

    return pdf_path
