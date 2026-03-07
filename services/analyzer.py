from __future__ import annotations
from models.schemas import Score, BreakdownItem

ANNULLED = "*"


def score_answers(
    candidates: list[str | None],
    answer_key: dict[str, str],
    expected_questions: int,
) -> Score:
    correct = wrong = blank = annulled = 0

    for i in range(1, expected_questions + 1):
        key = answer_key.get(str(i))
        candidate = candidates[i - 1] if i - 1 < len(candidates) else None

        if key == ANNULLED:
            annulled += 1
        elif candidate is None:
            blank += 1
        elif candidate == key:
            correct += 1
        else:
            wrong += 1

    scorable = expected_questions - annulled
    pct = (correct / scorable * 100) if scorable > 0 else 0.0

    return Score(correct=correct, wrong=wrong, blank=blank, annulled=annulled, pct=round(pct, 2))


def build_breakdown(
    candidates: list[str | None],
    answer_key: dict[str, str],
    expected_questions: int,
) -> list[BreakdownItem]:
    items: list[BreakdownItem] = []

    for i in range(1, expected_questions + 1):
        key = answer_key.get(str(i))
        candidate = candidates[i - 1] if i - 1 < len(candidates) else None
        is_annulled = key == ANNULLED
        hit = (not is_annulled) and (candidate is not None) and (candidate == key)

        items.append(BreakdownItem(
            question=i,
            candidate=candidate,
            correct=None if is_annulled else key,
            hit=hit,
            annulled=is_annulled,
        ))

    return items
