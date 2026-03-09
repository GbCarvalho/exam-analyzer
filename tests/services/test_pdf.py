import pytest
import fitz
from PIL import Image
from pathlib import Path

ASSETS = Path(__file__).parents[3] / "assets"
FGV_PDF = ASSETS / "fgv-auditor-fiscal-frb100-tipo-1.pdf"
CEBRASPE_PDF = ASSETS / "cebraspe-basicos-tcu_25_aufc.pdf"

pytestmark = pytest.mark.skipif(
    not FGV_PDF.exists() or not CEBRASPE_PDF.exists(),
    reason="PDF assets not available",
)


def test_split_page_returns_two_images():
    from services.pdf import split_page_vertically

    doc = fitz.open(str(FGV_PDF))
    page = doc[1]  # page 2, has two columns
    left, right = split_page_vertically(page)
    assert isinstance(left, Image.Image)
    assert isinstance(right, Image.Image)


def test_split_page_left_is_left_half():
    from services.pdf import split_page_vertically

    doc = fitz.open(str(FGV_PDF))
    page = doc[1]
    left, right = split_page_vertically(page)
    # left image width should be approximately half the full page width at SCALE
    page_width_px = int(page.rect.width * 2)  # at 2x scale
    assert abs(left.width - page_width_px // 2) <= 2


def test_extract_column_images_ordering():
    from services.pdf import extract_column_images

    doc = fitz.open(str(FGV_PDF))
    # FGV: skip page 0 (cover), pages 1+ have two columns
    columns = extract_column_images(doc, skip_first=True)
    # Should be (n_pages - 1) * 2 images
    assert len(columns) == (doc.page_count - 1) * 2
    assert all(isinstance(img, Image.Image) for img in columns)


def test_extract_column_images_no_skip():
    from services.pdf import extract_column_images

    doc = fitz.open(str(CEBRASPE_PDF))
    columns = extract_column_images(doc, skip_first=False)
    assert len(columns) == doc.page_count * 2
