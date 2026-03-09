from __future__ import annotations
from typing import Any

_exams: dict[str, dict[str, Any]] = {}
_answer_keys: dict[str, dict[str, Any]] = {}  # keyed by exam_id
_results: dict[str, dict[str, Any]] = {}  # keyed by result_id


def store_exam(exam_id: str, data: dict[str, Any]) -> None:
    _exams[exam_id] = data


def get_exam(exam_id: str) -> dict[str, Any] | None:
    return _exams.get(exam_id)


def find_exam_by_identity(
    exam_code: str | None,
    cargo: str | None,
    exam_type: str | None,
    booklet_type: str | None,
) -> dict[str, Any] | None:
    for exam in _exams.values():
        if (
            exam["exam_code"] == exam_code
            and exam["cargo"] == cargo
            and exam["exam_type"] == exam_type
            and exam["booklet_type"] == booklet_type
        ):
            return exam
    return None


def store_answer_key(exam_id: str, data: dict[str, Any]) -> None:
    _answer_keys[exam_id] = data


def get_answer_key(exam_id: str) -> dict[str, Any] | None:
    return _answer_keys.get(exam_id)


def store_result(result_id: str, data: dict[str, Any]) -> None:
    _results[result_id] = data


def get_result(result_id: str) -> dict[str, Any] | None:
    return _results.get(result_id)


def update_question(exam_id: str, number: int, statement: str) -> dict[str, Any] | None:
    exam = _exams.get(exam_id)
    if not exam:
        return None
    for q in exam["questions"]:
        if q["number"] == number:
            q["statement"] = statement
            q["manual"] = True
            return dict(q)
    return None


def bulk_update_questions(exam_id: str, updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for u in updates:
        result = update_question(exam_id, u["number"], u["statement"])
        if result is not None:
            results.append(result)
    return results


def clear_all() -> None:
    """For test teardown only."""
    _exams.clear()
    _answer_keys.clear()
    _results.clear()
