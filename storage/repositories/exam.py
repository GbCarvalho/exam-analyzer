from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from models.db import Exam, Question


class ExamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, exam_id: str) -> Exam | None:
        result = await self.session.execute(
            select(Exam).where(Exam.exam_id == exam_id)
        )
        return result.scalar_one_or_none()

    async def get_with_questions(self, exam_id: str) -> Exam | None:
        from sqlalchemy.orm import selectinload
        result = await self.session.execute(
            select(Exam)
            .options(selectinload(Exam.questions))
            .where(Exam.exam_id == exam_id)
        )
        return result.scalar_one_or_none()

    async def find_by_identity(
        self,
        exam_code: str | None,
        cargo: str | None,
        exam_type: str | None,
        booklet_type: str | None,
    ) -> Exam | None:
        result = await self.session.execute(
            select(Exam).where(
                and_(
                    Exam.exam_code == exam_code,
                    Exam.cargo == cargo,
                    Exam.exam_type == exam_type,
                    Exam.booklet_type == booklet_type,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Exam:
        questions_data = data.pop("questions", [])
        exam = Exam(**data)
        self.session.add(exam)
        await self.session.flush()

        for q in questions_data:
            question = Question(
                exam_id=exam.exam_id,
                number=q["number"],
                statement=q["statement"],
                manual=q.get("manual", False),
            )
            self.session.add(question)

        await self.session.commit()
        await self.session.refresh(exam)
        return exam

    async def list(self) -> list[Exam]:
        result = await self.session.execute(select(Exam))
        return list(result.scalars().all())

    async def update_question(
        self, exam_id: str, number: int, statement: str
    ) -> Question | None:
        result = await self.session.execute(
            select(Question).where(
                and_(Question.exam_id == exam_id, Question.number == number)
            )
        )
        question = result.scalar_one_or_none()
        if not question:
            return None
        question.statement = statement
        question.manual = True
        await self.session.commit()
        await self.session.refresh(question)
        return question

    async def bulk_update_questions(
        self, exam_id: str, updates: list[dict]
    ) -> list[Question]:
        updated = []
        for u in updates:
            q = await self.update_question(exam_id, u["number"], u["statement"])
            if q:
                updated.append(q)
        return updated
