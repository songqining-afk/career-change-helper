"""
Text extraction and chunking for uploaded documents.
Supports: PDF, TXT, MD.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: str | Path) -> str:
    """Extract plain text from a file. Supports .pdf, .txt, .md."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix in (".txt", ".md", ".markdown"):
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .pdf, .txt, or .md")


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise ImportError("PyPDF2 is required for PDF support: pip install pypdf2")

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split text into overlapping chunks by character count.

    Uses paragraph boundaries when possible, falls back to sentence/word splits.
    """
    if not text.strip():
        return []

    # Split into paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            # If single paragraph exceeds chunk_size, split it
            if len(para) > chunk_size:
                words = para.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= chunk_size:
                        current = f"{current} {word}" if current else word
                    else:
                        if current:
                            chunks.append(current)
                        current = word
            else:
                current = para

    if current:
        chunks.append(current)

    # Add overlap: prepend tail of previous chunk to each chunk
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(f"{prev_tail}...{chunks[i]}")
        chunks = overlapped

    return chunks
