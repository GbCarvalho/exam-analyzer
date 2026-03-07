from __future__ import annotations
import fitz
import uuid6
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

import storage.memory as mem
import providers.cebraspe as cebraspe
import providers.fgv as fgv
from services.pdf import extract_column_images
from services.ocr import image_to_text, needs_fallback, ocr_with_claude_fallback
from services.analyzer import score_answers, build_breakdown
from models.schemas import (
    AnswerKeyCreate,
    AnalyzeRequest,
    ExamResponse,
    AnswerKeyResponse,
    AnalyzeResponse,
    ResultResponse,
)

app = FastAPI(title="Exam Analyzer")

import os
try:
    import anthropic
    _claude = anthropic.Anthropic() if os.environ.get("ANTHROPIC_API_KEY") else None
except Exception:
    _claude = None


def _new_id() -> str:
    return str(uuid6.uuid7())


def _detect_provider(column_texts: list[str]) -> str:
    combined = " ".join(column_texts[:4])
    if "CEBRASPE" in combined:
        return "cebraspe"
    if "FGV" in combined:
        return "fgv"
    return "unknown"


def _open_pdf(pdf_bytes: bytes) -> fitz.Document:
    return fitz.open(stream=pdf_bytes, filetype="pdf")


def _extract_text_from_columns(doc: fitz.Document, skip_first: bool) -> list[str]:
    """Primary extraction: use PyMuPDF embedded text (fast, accurate for digital PDFs)."""
    columns: list[str] = []
    start = 1 if skip_first else 0
    for i in range(start, doc.page_count):
        page = doc[i]
        w = page.rect.width
        # Skip blank pages (e.g. FGV has an empty page after the cover)
        if len(page.get_text().strip()) < 20:
            continue
        left = page.get_text(clip=fitz.Rect(0, 0, w / 2, page.rect.height))
        right = page.get_text(clip=fitz.Rect(w / 2, 0, w, page.rect.height))
        columns.append(left)
        columns.append(right)
    return columns


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/exams")
async def upload_exam(
    file: UploadFile = File(...),
    expected_questions: int = Form(...),
    cargo: str | None = Form(None),
    exam_type: str | None = Form(None),
    booklet_type: str | None = Form(None),
):
    pdf_bytes = await file.read()
    doc = _open_pdf(pdf_bytes)

    # Detect FGV cover page from right column of page 0
    first_page = doc[0]
    w = first_page.rect.width
    first_right = first_page.get_text(clip=fitz.Rect(w / 2, 0, w, first_page.rect.height))
    is_fgv_cover = fgv.is_cover_page(first_right)

    column_texts = _extract_text_from_columns(doc, skip_first=is_fgv_cover)
    provider = _detect_provider(column_texts)

    exam_code: str | None = None
    inferred_cargo: str | None = cargo
    inferred_exam_type: str | None = exam_type

    if provider == "fgv":
        exam_code = fgv.extract_exam_code(column_texts[0]) if column_texts else None
        if not inferred_cargo:
            inferred_cargo = fgv.extract_cargo(column_texts[0])
        if not inferred_exam_type:
            inferred_exam_type = fgv.extract_exam_type(column_texts[1]) if len(column_texts) > 1 else None
        questions = fgv.parse_questions(column_texts)

    elif provider == "cebraspe":
        exam_code = cebraspe.extract_exam_code(column_texts[1]) if len(column_texts) > 1 else None
        if not inferred_cargo:
            raise HTTPException(
                status_code=422,
                detail={"error": "could_not_infer_cargo", "hint": "Provide 'cargo' in the request"},
            )
        questions = cebraspe.parse_questions(" ".join(column_texts))

    else:
        raise HTTPException(status_code=422, detail="Could not detect exam provider")

    # Check for duplicate
    existing = mem.find_exam_by_identity(exam_code, inferred_cargo, inferred_exam_type, booklet_type)
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"error": "exam_already_exists", "exam_id": existing["exam_id"]},
        )

    # Fallback to OCR + Claude vision if question count doesn't match
    partial = False
    if needs_fallback(questions, expected_questions):
        # Try OCR on rendered images
        column_images = extract_column_images(doc, skip_first=is_fgv_cover)
        ocr_texts = [image_to_text(img) for img in column_images]
        if provider == "fgv":
            questions = fgv.parse_questions(ocr_texts)
        else:
            questions = cebraspe.parse_questions(" ".join(ocr_texts))

        # Final fallback: Claude vision
        if needs_fallback(questions, expected_questions) and _claude:
            fallback_text = ocr_with_claude_fallback(column_images, _claude)
            if provider == "fgv":
                questions = fgv.parse_questions([fallback_text])
            else:
                questions = cebraspe.parse_questions(fallback_text)

        if needs_fallback(questions, expected_questions):
            partial = True

    exam_id = _new_id()
    data = {
        "exam_id": exam_id,
        "exam_code": exam_code,
        "provider": provider,
        "cargo": inferred_cargo,
        "exam_type": inferred_exam_type,
        "booklet_type": booklet_type,
        "expected_questions": expected_questions,
        "partial": partial,
        "questions": [q.model_dump() for q in questions],
    }
    mem.store_exam(exam_id, data)

    return JSONResponse(content=data, status_code=206 if partial else 200)


@app.get("/exams/{exam_id}", response_model=ExamResponse)
def get_exam(exam_id: str):
    exam = mem.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@app.post("/exams/{exam_id}/answer-key", response_model=AnswerKeyResponse)
def upload_answer_key_json(exam_id: str, body: AnswerKeyCreate):
    """Store answer key from structured JSON."""
    exam = mem.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    answer_key_id = _new_id()
    data = {"answer_key_id": answer_key_id, "answers": body.answers}
    mem.store_answer_key(exam_id, data)
    return data


@app.post("/exams/{exam_id}/answer-key/upload", response_model=AnswerKeyResponse)
async def upload_answer_key_pdf(exam_id: str, file: UploadFile = File(...)):
    """Store answer key parsed from a PDF gabarito."""
    exam = mem.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    pdf_bytes = await file.read()
    doc = _open_pdf(pdf_bytes)
    full_text = "\n".join(doc[i].get_text() for i in range(doc.page_count))

    provider = exam["provider"]
    if provider == "fgv":
        exam_type_num = (exam["exam_type"] or "").replace("TIPO ", "").strip()
        answers = fgv.parse_answer_key_text(
            full_text,
            cargo=exam["cargo"] or "",
            exam_type=exam_type_num,
        )
    else:
        answers = cebraspe.parse_answer_key_text(full_text)

    if not answers:
        raise HTTPException(status_code=422, detail="Could not parse any answers from the PDF")

    answer_key_id = _new_id()
    data = {"answer_key_id": answer_key_id, "answers": answers}
    mem.store_answer_key(exam_id, data)
    return data


@app.get("/exams/{exam_id}/answer-key", response_model=AnswerKeyResponse)
def get_answer_key(exam_id: str):
    ak = mem.get_answer_key(exam_id)
    if not ak:
        raise HTTPException(status_code=404, detail="Answer key not found")
    return ak


@app.post("/exams/{exam_id}/analyze", response_model=AnalyzeResponse)
def analyze(exam_id: str, body: AnalyzeRequest):
    exam = mem.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    ak = mem.get_answer_key(exam_id)
    if not ak:
        raise HTTPException(status_code=404, detail="Answer key not found")

    score = score_answers(body.answers, ak["answers"], exam["expected_questions"])
    result_id = _new_id()
    breakdown = build_breakdown(body.answers, ak["answers"], exam["expected_questions"])
    mem.store_result(result_id, {
        "score": score.model_dump(),
        "breakdown": [b.model_dump() for b in breakdown],
    })
    return {"result_id": result_id, "score": score}


@app.get("/exams/{exam_id}/results/{result_id}", response_model=ResultResponse)
def get_result(exam_id: str, result_id: str):
    result = mem.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
