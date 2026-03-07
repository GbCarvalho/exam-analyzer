from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


Provider = Literal["cebraspe", "fgv"]
BookletType = Literal["basicos", "especificos"]


class ProviderMeta(BaseModel):
    id: Provider
    label: str
    description: str
    supports_dual_booklet: bool


class ExamCreate(BaseModel):
    expected_questions: int
    cargo: str | None = None
    exam_type: str | None = None
    booklet_type: BookletType | None = None


class Question(BaseModel):
    number: int
    statement: str
    manual: bool = False


class ExamResponse(BaseModel):
    exam_id: str
    exam_code: str | None
    provider: str
    cargo: str | None
    exam_type: str | None
    booklet_type: str | None
    expected_questions: int
    partial: bool
    questions: list[Question] = []


class AnswerKeyCreate(BaseModel):
    answers: dict[str, str]  # {"1": "C", "2": "E", ...}


class AnswerKeyResponse(BaseModel):
    answer_key_id: str
    answers: dict[str, str]


class AnalyzeRequest(BaseModel):
    answers: list[str | None]


class Score(BaseModel):
    correct: int
    wrong: int
    blank: int
    annulled: int
    pct: float


class AnalyzeResponse(BaseModel):
    result_id: str
    score: Score


class BreakdownItem(BaseModel):
    question: int
    candidate: str | None
    correct: str | None
    hit: bool
    annulled: bool


class ResultResponse(BaseModel):
    score: Score
    breakdown: list[BreakdownItem]


class QuestionPatch(BaseModel):
    statement: str


class BulkQuestionPatchItem(BaseModel):
    number: int
    statement: str


class BulkQuestionPatch(BaseModel):
    updates: list[BulkQuestionPatchItem]
