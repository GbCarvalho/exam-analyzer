from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.db import Result, ResultBreakdown
import uuid6


class ResultRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, result_id: str) -> Result | None:
        result = await self.session.execute(
            select(Result)
            .options(selectinload(Result.breakdown))
            .where(Result.result_id == result_id)
        )
        return result.scalar_one_or_none()

    async def create(self, exam_id: str, score: dict, breakdown: list[dict]) -> Result:
        res = Result(
            result_id=str(uuid6.uuid7()),
            exam_id=exam_id,
            **score,
        )
        self.session.add(res)
        await self.session.flush()

        for b in breakdown:
            item = ResultBreakdown(
                result_id=res.result_id,
                question_number=b["question"],
                candidate_answer=b["candidate"],
                correct_answer=b["correct"],
                hit=b["hit"],
                annulled=b["annulled"],
            )
            self.session.add(item)

        await self.session.commit()
        await self.session.refresh(res)
        return res
