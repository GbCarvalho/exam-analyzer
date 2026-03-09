from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel


class Exam(SQLModel, table=True):
    __tablename__ = "exams"

    exam_id: str = Field(primary_key=True)
    exam_code: Optional[str] = None
    provider: str
    cargo: Optional[str] = None
    exam_type: Optional[str] = None
    booklet_type: Optional[str] = None
    expected_questions: int
    partial: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    questions: List["Question"] = Relationship(back_populates="exam")
    answer_key: Optional["AnswerKey"] = Relationship(back_populates="exam")
    results: List["Result"] = Relationship(back_populates="exam")


class Question(SQLModel, table=True):
    __tablename__ = "questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: str = Field(foreign_key="exams.exam_id")
    number: int
    statement: str
    manual: bool = False

    exam: Optional[Exam] = Relationship(back_populates="questions")


class AnswerKey(SQLModel, table=True):
    __tablename__ = "answer_keys"

    answer_key_id: str = Field(primary_key=True)
    exam_id: str = Field(foreign_key="exams.exam_id", unique=True)

    exam: Optional[Exam] = Relationship(back_populates="answer_key")
    items: List["AnswerKeyItem"] = Relationship(back_populates="answer_key")


class AnswerKeyItem(SQLModel, table=True):
    __tablename__ = "answer_key_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    answer_key_id: str = Field(foreign_key="answer_keys.answer_key_id")
    question_number: int
    answer: str

    answer_key: Optional[AnswerKey] = Relationship(back_populates="items")


class Result(SQLModel, table=True):
    __tablename__ = "results"

    result_id: str = Field(primary_key=True)
    exam_id: str = Field(foreign_key="exams.exam_id")
    correct: int
    wrong: int
    blank: int
    annulled: int
    pct: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    exam: Optional[Exam] = Relationship(back_populates="results")
    breakdown: List["ResultBreakdown"] = Relationship(back_populates="result")


class ResultBreakdown(SQLModel, table=True):
    __tablename__ = "result_breakdown"

    id: Optional[int] = Field(default=None, primary_key=True)
    result_id: str = Field(foreign_key="results.result_id")
    question_number: int
    candidate_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    hit: bool
    annulled: bool

    result: Optional[Result] = Relationship(back_populates="breakdown")
