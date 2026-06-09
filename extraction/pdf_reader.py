"""Thin PyMuPDF wrapper: page text, positional words, and page renders.

Text-layer first (this filing has a clean one). Renders are available for vision
cross-checks on tricky pages (the 4-column income statement, the segment table).
"""
from __future__ import annotations

from pathlib import Path

import fitz


class PdfDoc:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.doc = fitz.open(self.path)

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def text(self, pages: list[int]) -> str:
        """Concatenated text for the given 0-based pages, with page markers."""
        out = []
        for i in pages:
            out.append(f"\n===== PAGE {i} =====\n{self.doc[i].get_text()}")
        return "\n".join(out)

    def render_png(self, page: int, dpi: int = 140) -> bytes:
        return self.doc[page].get_pixmap(dpi=dpi).tobytes("png")

    def is_text_layer_ok(self, page: int, min_chars: int = 60) -> bool:
        return len(self.doc[page].get_text().strip()) >= min_chars

    def close(self) -> None:
        self.doc.close()
