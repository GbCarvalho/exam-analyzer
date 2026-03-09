from __future__ import annotations
import os
import fitz
import subprocess
import uuid6
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
    Question,
    QuestionPatch,
    BulkQuestionPatch,
    ProviderMeta,
)
from storage.database import get_session
from storage.repositories.exam import ExamRepository
from storage.repositories.answer_key import AnswerKeyRepository
from storage.repositories.result import ResultRepository


@asynccontextmanager
async def lifespan(app):
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    yield


app = FastAPI(title="Exam Analyzer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def _merge_pdfs(parts_bytes: list[bytes]) -> fitz.Document:
    """Merge one or more PDF byte strings into a single fitz.Document."""
    merged = fitz.open()
    for pdf_bytes in parts_bytes:
        merged.insert_pdf(_open_pdf(pdf_bytes))
    return merged


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


def _exam_to_dict(exam) -> dict:
    return {
        "exam_id": exam.exam_id,
        "exam_code": exam.exam_code,
        "provider": exam.provider,
        "cargo": exam.cargo,
        "exam_type": exam.exam_type,
        "booklet_type": exam.booklet_type,
        "expected_questions": exam.expected_questions,
        "partial": exam.partial,
        "questions": [
            {"number": q.number, "statement": q.statement, "manual": q.manual}
            for q in (exam.questions or [])
        ],
    }


def _result_to_dict(result) -> dict:
    return {
        "score": {
            "correct": result.correct,
            "wrong": result.wrong,
            "blank": result.blank,
            "annulled": result.annulled,
            "pct": result.pct,
        },
        "breakdown": [
            {
                "question": b.question_number,
                "candidate": b.candidate_answer,
                "correct": b.correct_answer,
                "hit": b.hit,
                "annulled": b.annulled,
            }
            for b in result.breakdown
        ],
    }


_PROVIDERS: list[ProviderMeta] = [
    ProviderMeta(
        id="cebraspe",
        label="CEBRASPE",
        description="Questões C/E — suporta dois cadernos (básicos + específicos)",
        supports_dual_booklet=True,
    ),
    ProviderMeta(
        id="fgv",
        label="FGV",
        description="Questões A–E — caderno único por cargo e tipo",
        supports_dual_booklet=False,
    ),
]


async def get_exam_repo(session: AsyncSession = Depends(get_session)) -> ExamRepository:
    return ExamRepository(session)


async def get_ak_repo(session: AsyncSession = Depends(get_session)) -> AnswerKeyRepository:
    return AnswerKeyRepository(session)


async def get_result_repo(session: AsyncSession = Depends(get_session)) -> ResultRepository:
    return ResultRepository(session)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/providers", response_model=list[ProviderMeta])
def list_providers():
    return _PROVIDERS


@app.post("/exams")
async def upload_exam(
    files: list[UploadFile] = File(...),
    expected_questions: int = Form(...),
    cargo: str | None = Form(None),
    exam_type: str | None = Form(None),
    booklet_type: str | None = Form(None),
    repo: ExamRepository = Depends(get_exam_repo),
):
    parts_bytes = [await f.read() for f in files]
    doc = _merge_pdfs(parts_bytes)

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
            inferred_exam_type = (
                fgv.extract_exam_type(column_texts[1]) if len(column_texts) > 1 else None
            )
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
    existing = await repo.find_by_identity(
        exam_code, inferred_cargo, inferred_exam_type, booklet_type
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"error": "exam_already_exists", "exam_id": existing.exam_id},
        )

    # Fallback to OCR + Claude vision if question count doesn't match
    partial = False
    if needs_fallback(questions, expected_questions):
        column_images = extract_column_images(doc, skip_first=is_fgv_cover)
        ocr_texts = [image_to_text(img) for img in column_images]
        if provider == "fgv":
            questions = fgv.parse_questions(ocr_texts)
        else:
            questions = cebraspe.parse_questions(" ".join(ocr_texts))

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
    exam = await repo.create(data)
    exam = await repo.get_with_questions(exam.exam_id)

    return JSONResponse(content=_exam_to_dict(exam), status_code=206 if partial else 200)


@app.get("/exams/{exam_id}", response_model=ExamResponse)
async def get_exam(exam_id: str, repo: ExamRepository = Depends(get_exam_repo)):
    exam = await repo.get_with_questions(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return _exam_to_dict(exam)


@app.post("/exams/{exam_id}/answer-key", response_model=AnswerKeyResponse)
async def upload_answer_key_json(
    exam_id: str,
    body: AnswerKeyCreate,
    exam_repo: ExamRepository = Depends(get_exam_repo),
    ak_repo: AnswerKeyRepository = Depends(get_ak_repo),
):
    """Store answer key from structured JSON."""
    if not await exam_repo.get(exam_id):
        raise HTTPException(status_code=404, detail="Exam not found")
    ak = await ak_repo.create(exam_id, body.answers)
    return {"answer_key_id": ak.answer_key_id, "answers": ak_repo.to_dict(ak)}


@app.post("/exams/{exam_id}/answer-key/upload", response_model=AnswerKeyResponse)
async def upload_answer_key_pdf(
    exam_id: str,
    file: UploadFile = File(...),
    exam_repo: ExamRepository = Depends(get_exam_repo),
    ak_repo: AnswerKeyRepository = Depends(get_ak_repo),
):
    """Store answer key parsed from a PDF gabarito."""
    exam = await exam_repo.get(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    pdf_bytes = await file.read()
    doc = _open_pdf(pdf_bytes)
    full_text = "\n".join(doc[i].get_text() for i in range(doc.page_count))

    provider = exam.provider
    if provider == "fgv":
        exam_type_num = (exam.exam_type or "").replace("TIPO ", "").strip()
        answers = fgv.parse_answer_key_text(
            full_text,
            cargo=exam.cargo or "",
            exam_type=exam_type_num,
        )
    else:
        answers = cebraspe.parse_answer_key_text(full_text)

    if not answers:
        raise HTTPException(status_code=422, detail="Could not parse any answers from the PDF")

    ak = await ak_repo.create(exam_id, answers)
    return {"answer_key_id": ak.answer_key_id, "answers": ak_repo.to_dict(ak)}


@app.get("/exams/{exam_id}/answer-key", response_model=AnswerKeyResponse)
async def get_answer_key(exam_id: str, ak_repo: AnswerKeyRepository = Depends(get_ak_repo)):
    ak = await ak_repo.get(exam_id)
    if not ak:
        raise HTTPException(status_code=404, detail="Answer key not found")
    return {"answer_key_id": ak.answer_key_id, "answers": ak_repo.to_dict(ak)}


@app.post("/exams/{exam_id}/analyze", response_model=AnalyzeResponse)
async def analyze(
    exam_id: str,
    body: AnalyzeRequest,
    exam_repo: ExamRepository = Depends(get_exam_repo),
    ak_repo: AnswerKeyRepository = Depends(get_ak_repo),
    result_repo: ResultRepository = Depends(get_result_repo),
):
    exam = await exam_repo.get(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    ak = await ak_repo.get(exam_id)
    if not ak:
        raise HTTPException(status_code=404, detail="Answer key not found")

    answers_dict = ak_repo.to_dict(ak)
    score = score_answers(body.answers, answers_dict, exam.expected_questions)
    breakdown = build_breakdown(body.answers, answers_dict, exam.expected_questions)
    result = await result_repo.create(
        exam_id, score.model_dump(), [b.model_dump() for b in breakdown]
    )
    return {"result_id": result.result_id, "score": score}


@app.get("/exams/{exam_id}/results/{result_id}", response_model=ResultResponse)
async def get_result(
    exam_id: str,
    result_id: str,
    result_repo: ResultRepository = Depends(get_result_repo),
):
    result = await result_repo.get(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return _result_to_dict(result)


@app.patch("/exams/{exam_id}/questions/{number}", response_model=Question)
async def patch_question(
    exam_id: str,
    number: int,
    body: QuestionPatch,
    repo: ExamRepository = Depends(get_exam_repo),
):
    if not await repo.get(exam_id):
        raise HTTPException(status_code=404, detail="Exam not found")
    updated = await repo.update_question(exam_id, number, body.statement)
    if updated is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return updated


@app.patch("/exams/{exam_id}/questions", response_model=list[Question])
async def patch_questions_bulk(
    exam_id: str,
    body: BulkQuestionPatch,
    repo: ExamRepository = Depends(get_exam_repo),
):
    if not await repo.get(exam_id):
        raise HTTPException(status_code=404, detail="Exam not found")
    return await repo.bulk_update_questions(exam_id, [u.model_dump() for u in body.updates])
