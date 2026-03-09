from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.db import AnswerKey, AnswerKeyItem
import uuid6


class AnswerKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, exam_id: str) -> AnswerKey | None:
        result = await self.session.execute(
            select(AnswerKey)
            .options(selectinload(AnswerKey.items))
            .where(AnswerKey.exam_id == exam_id)
        )
        return result.scalar_one_or_none()

    async def create(self, exam_id: str, answers: dict[str, str]) -> AnswerKey:
        existing = await self.get(exam_id)
        if existing:
            await self.session.delete(existing)
            await self.session.flush()

        ak = AnswerKey(answer_key_id=str(uuid6.uuid7()), exam_id=exam_id)
        self.session.add(ak)
        await self.session.flush()

        for q_num, answer in answers.items():
            item = AnswerKeyItem(
                answer_key_id=ak.answer_key_id,
                question_number=int(q_num),
                answer=answer,
            )
            self.session.add(item)

        await self.session.commit()
        # Re-fetch with items loaded to avoid lazy-load in async context
        return await self.get(exam_id)

    def to_dict(self, ak: AnswerKey) -> dict[str, str]:
        """Convert AnswerKey items to {question_number: answer} dict."""
        return {str(item.question_number): item.answer for item in ak.items}
