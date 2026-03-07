from __future__ import annotations
import fitz
from PIL import Image

SCALE = 2.0  # render at 2x for better OCR quality
MATRIX = fitz.Matrix(SCALE, SCALE)


def split_page_vertically(page: fitz.Page) -> tuple[Image.Image, Image.Image]:
    """Render a PDF page and split it into left and right column images."""
    pix = page.get_pixmap(matrix=MATRIX)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    mid = img.width // 2
    return img.crop((0, 0, mid, img.height)), img.crop((mid, 0, img.width, img.height))


def extract_column_images(doc: fitz.Document, skip_first: bool = False) -> list[Image.Image]:
    """
    Extract all column images from a PDF in reading order:
    page N left -> page N right -> page N+1 left -> ...

    Args:
        doc: Opened PyMuPDF document.
        skip_first: If True, skip page 0 (FGV cover page).
    """
    columns: list[Image.Image] = []
    start = 1 if skip_first else 0
    for i in range(start, doc.page_count):
        left, right = split_page_vertically(doc[i])
        columns.append(left)
        columns.append(right)
    return columns
