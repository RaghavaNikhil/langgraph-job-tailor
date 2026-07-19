"""Loads resume versions from the local `resumes/` directory.

Supports .docx (via python-docx), .md, and .txt files. The file whose
name contains "full" (case-insensitive) is treated as the master resume
— the detailed fact bank the writer may draw from.
"""

from pathlib import Path
from typing import Dict, Tuple

from docx import Document

RESUMES_DIR = Path(__file__).parent / "resumes"
MASTER_KEYWORD = "full"


def _read_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return _read_docx(path)
    return path.read_text(encoding="utf-8")


def load_resumes() -> Tuple[Dict[str, str], str]:
    """Load all resumes from RESUMES_DIR.

    Returns:
        (candidates, master_text) where candidates maps resume name (file
        stem) to its text for every non-master version, and master_text is
        the master resume's text ("" if no master file is found).
    """
    if not RESUMES_DIR.is_dir():
        raise FileNotFoundError(
            f"Resume directory not found: {RESUMES_DIR}. "
            "Create it and add your resume files (.docx, .md, or .txt)."
        )

    candidates: Dict[str, str] = {}
    master_text = ""

    for path in sorted(RESUMES_DIR.iterdir()):
        if path.suffix.lower() not in {".docx", ".md", ".txt"}:
            continue
        if path.name.startswith("~$"):  # Word lock files
            continue
        text = _read_file(path)
        if not text.strip():
            continue
        if MASTER_KEYWORD in path.stem.lower():
            master_text = text
        else:
            candidates[path.stem] = text

    if not candidates:
        raise FileNotFoundError(
            f"No readable resume files found in {RESUMES_DIR} "
            "(expected .docx, .md, or .txt)."
        )
    return candidates, master_text
