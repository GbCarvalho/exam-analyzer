import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
import storage.memory as mem
from models.schemas import Question

client = TestClient(app)

# --- Shared stubs ---

STUB_QUESTIONS = [Question(number=i, statement=f"Question {i}") for i in range(1, 6)]
STUB_COLUMN_TEXTS = ["left col text FGV CONHECIMENTO", "right col FGV TIPO BRANCA"]


@pytest.fixture(autouse=True)
def clear_storage():
    mem.clear_all()
    yield
    mem.clear_all()


def _fgv_pdf_mock():
    """Mock fitz.open for a FGV exam."""
    page = MagicMock()
    page.rect.width = 595
    page.rect.height = 842
    page.get_text.side_effect = lambda **kwargs: (
        "RECEITA FEDERAL DO BRASIL (CURSO DE FORMAÇÃO 2025/1)\n\nAUDITOR FISCAL\n\n1 Question one"
        if kwargs.get("clip") and kwargs["clip"].x0 == 0
        else "FGV CONHECIMENTO\n\nTIPO BRANCA – PÁGINA 2\n2 Question two"
    )
    doc = MagicMock()
    doc.page_count = 3
    doc.__getitem__ = lambda self, i: page
    return doc


def _post_fgv_exam(expected_questions: int = 5) -> dict:
    """Helper: upload a mocked FGV exam."""
    with patch("main._merge_pdfs", return_value=MagicMock()), \
         patch("main.fgv.is_cover_page", return_value=True), \
         patch("main._extract_text_from_columns", return_value=STUB_COLUMN_TEXTS), \
         patch("main._detect_provider", return_value="fgv"), \
         patch("main.fgv.extract_exam_code", return_value="CURSO DE FORMAÇÃO 2025/1"), \
         patch("main.fgv.extract_cargo", return_value="AUDITOR FISCAL"), \
         patch("main.fgv.extract_exam_type", return_value="TIPO BRANCA"), \
         patch("main.fgv.parse_questions", return_value=STUB_QUESTIONS), \
         patch("main.needs_fallback", return_value=False):
        resp = client.post(
            "/exams",
            data={"expected_questions": expected_questions},
            files=[("files", ("exam.pdf", b"%PDF stub", "application/pdf"))],
        )
    return resp


# --- POST /exams ---

def test_upload_fgv_exam_returns_200():
    resp = _post_fgv_exam()
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "fgv"
    assert body["cargo"] == "AUDITOR FISCAL"
    assert body["exam_type"] == "TIPO BRANCA"
    assert "exam_id" in body


def test_upload_cebraspe_requires_cargo():
    with patch("main._merge_pdfs", return_value=MagicMock()), \
         patch("main.fgv.is_cover_page", return_value=False), \
         patch("main._extract_text_from_columns", return_value=["CEBRASPE – TCU text", "more text"]), \
         patch("main._detect_provider", return_value="cebraspe"):
        resp = client.post(
            "/exams",
            data={"expected_questions": 100},
            files=[("files", ("exam.pdf", b"%PDF stub", "application/pdf"))],
        )
    assert resp.status_code == 422


def test_upload_cebraspe_with_cargo():
    with patch("main._merge_pdfs", return_value=MagicMock()), \
         patch("main.fgv.is_cover_page", return_value=False), \
         patch("main._extract_text_from_columns", return_value=["CEBRASPE text", "more"]), \
         patch("main._detect_provider", return_value="cebraspe"), \
         patch("main.cebraspe.extract_exam_code", return_value="TCU/AUFC – Edital: 2025"), \
         patch("main.cebraspe.parse_questions", return_value=STUB_QUESTIONS), \
         patch("main.needs_fallback", return_value=False):
        resp = client.post(
            "/exams",
            data={"expected_questions": 5, "cargo": "Auditor Federal", "booklet_type": "basicos"},
            files=[("files", ("exam.pdf", b"%PDF stub", "application/pdf"))],
        )
    assert resp.status_code == 200
    assert resp.json()["cargo"] == "Auditor Federal"


def test_upload_duplicate_returns_409():
    _post_fgv_exam()
    resp = _post_fgv_exam()
    assert resp.status_code == 409


def test_upload_returns_206_when_partial():
    with patch("main._merge_pdfs", return_value=MagicMock()), \
         patch("main.fgv.is_cover_page", return_value=True), \
         patch("main._extract_text_from_columns", return_value=STUB_COLUMN_TEXTS), \
         patch("main._detect_provider", return_value="fgv"), \
         patch("main.fgv.extract_exam_code", return_value="CURSO DE FORMAÇÃO 2025/1"), \
         patch("main.fgv.extract_cargo", return_value="AUDITOR FISCAL"), \
         patch("main.fgv.extract_exam_type", return_value="TIPO BRANCA"), \
         patch("main.fgv.parse_questions", return_value=STUB_QUESTIONS), \
         patch("main.needs_fallback", return_value=True), \
         patch("main.extract_column_images", return_value=[]), \
         patch("main.image_to_text", return_value=""), \
         patch("main._claude", None):
        resp = client.post(
            "/exams",
            data={"expected_questions": 60},
            files=[("files", ("exam.pdf", b"%PDF stub", "application/pdf"))],
        )
    assert resp.status_code == 206
    assert resp.json()["partial"] is True


# --- GET /exams/{exam_id} ---

def test_get_exam():
    exam_id = _post_fgv_exam().json()["exam_id"]
    resp = client.get(f"/exams/{exam_id}")
    assert resp.status_code == 200
    assert resp.json()["exam_id"] == exam_id
    assert isinstance(resp.json()["questions"], list)


def test_get_exam_not_found():
    assert client.get("/exams/nonexistent").status_code == 404


# --- POST /exams/{exam_id}/answer-key (JSON) ---

def test_upload_answer_key_json():
    exam_id = _post_fgv_exam().json()["exam_id"]
    resp = client.post(f"/exams/{exam_id}/answer-key", json={"answers": {"1": "C", "2": "E"}})
    assert resp.status_code == 200
    assert resp.json()["answers"]["1"] == "C"


def test_upload_answer_key_exam_not_found():
    resp = client.post("/exams/nonexistent/answer-key", json={"answers": {"1": "C"}})
    assert resp.status_code == 404


# --- POST /exams/{exam_id}/answer-key/upload (PDF) ---

def test_upload_answer_key_pdf():
    exam_id = _post_fgv_exam().json()["exam_id"]
    with patch("main._open_pdf") as mock_open, \
         patch("main.fgv.parse_answer_key_text", return_value={"1": "C", "2": "D", "3": "A"}):
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__getitem__ = lambda self, i: MagicMock(get_text=lambda: "gabarito text")
        mock_open.return_value = mock_doc
        resp = client.post(
            f"/exams/{exam_id}/answer-key/upload",
            files={"file": ("gabarito.pdf", b"%PDF stub", "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.json()["answers"]["1"] == "C"


# --- GET /exams/{exam_id}/answer-key ---

def test_get_answer_key():
    exam_id = _post_fgv_exam().json()["exam_id"]
    client.post(f"/exams/{exam_id}/answer-key", json={"answers": {"1": "C"}})
    resp = client.get(f"/exams/{exam_id}/answer-key")
    assert resp.status_code == 200
    assert resp.json()["answers"]["1"] == "C"


def test_get_answer_key_not_found():
    exam_id = _post_fgv_exam().json()["exam_id"]
    assert client.get(f"/exams/{exam_id}/answer-key").status_code == 404


# --- POST /exams/{exam_id}/analyze ---

def _exam_with_key() -> tuple[str, str]:
    exam_id = _post_fgv_exam().json()["exam_id"]
    client.post(f"/exams/{exam_id}/answer-key", json={"answers": {str(i): "C" for i in range(1, 6)}})
    return exam_id


def test_analyze_returns_score():
    exam_id = _exam_with_key()
    resp = client.post(f"/exams/{exam_id}/analyze", json={"answers": ["C", "C", "C", "C", "C"]})
    assert resp.status_code == 200
    assert resp.json()["score"]["correct"] == 5
    assert resp.json()["score"]["pct"] == 100.0


def test_analyze_partial_answers():
    exam_id = _exam_with_key()
    resp = client.post(f"/exams/{exam_id}/analyze", json={"answers": ["C"]})
    assert resp.status_code == 200
    assert resp.json()["score"]["blank"] == 4


def test_analyze_no_answer_key_returns_404():
    exam_id = _post_fgv_exam().json()["exam_id"]
    assert client.post(f"/exams/{exam_id}/analyze", json={"answers": ["C"]}).status_code == 404


# --- GET /exams/{exam_id}/results/{result_id} ---

def test_get_results_breakdown():
    exam_id = _exam_with_key()
    result_id = client.post(
        f"/exams/{exam_id}/analyze", json={"answers": ["C", "C", "C", "C", "C"]}
    ).json()["result_id"]
    resp = client.get(f"/exams/{exam_id}/results/{result_id}")
    assert resp.status_code == 200
    assert len(resp.json()["breakdown"]) == 5
    assert resp.json()["breakdown"][0]["hit"] is True


def test_get_result_not_found():
    exam_id = _post_fgv_exam().json()["exam_id"]
    assert client.get(f"/exams/{exam_id}/results/nonexistent").status_code == 404


def test_patch_question_updates_statement():
    exam_id = _post_fgv_exam().json()["exam_id"]
    r = client.patch(f"/exams/{exam_id}/questions/1", json={"statement": "Edited Q1"})
    assert r.status_code == 200
    data = r.json()
    assert data["statement"] == "Edited Q1"
    assert data["manual"] is True
    assert data["number"] == 1


def test_patch_question_returns_404_for_missing_exam():
    r = client.patch("/exams/nonexistent/questions/1", json={"statement": "x"})
    assert r.status_code == 404


def test_patch_question_returns_404_for_missing_number():
    exam_id = _post_fgv_exam().json()["exam_id"]
    r = client.patch(f"/exams/{exam_id}/questions/999", json={"statement": "x"})
    assert r.status_code == 404


def test_bulk_patch_questions():
    exam_id = _post_fgv_exam().json()["exam_id"]
    r = client.patch(f"/exams/{exam_id}/questions", json={
        "updates": [
            {"number": 1, "statement": "Bulk Q1"},
            {"number": 2, "statement": "Bulk Q2"},
        ]
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert all(q["manual"] is True for q in data)


def test_bulk_patch_questions_returns_404_for_missing_exam():
    r = client.patch("/exams/nonexistent/questions", json={"updates": [{"number": 1, "statement": "x"}]})
    assert r.status_code == 404
