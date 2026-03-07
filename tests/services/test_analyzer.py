import pytest
from services.analyzer import score_answers, build_breakdown

ANSWER_KEY = {"1": "C", "2": "E", "3": "A", "4": "*", "5": "B"}
EXPECTED = 5


# --- score_answers ---

def test_all_correct():
    candidates = ["C", "E", "A", None, "B"]  # Q4 annulled
    score = score_answers(candidates, ANSWER_KEY, EXPECTED)
    assert score.correct == 4
    assert score.wrong == 0
    assert score.blank == 0
    assert score.annulled == 1
    assert score.pct == 100.0


def test_some_wrong():
    candidates = ["C", "C", "A", None, "B"]
    score = score_answers(candidates, ANSWER_KEY, EXPECTED)
    assert score.correct == 3
    assert score.wrong == 1
    assert score.blank == 0
    assert score.annulled == 1


def test_blank_answers_with_null():
    candidates = ["C", None, "A", None, None]
    score = score_answers(candidates, ANSWER_KEY, EXPECTED)
    assert score.blank == 2  # Q2 and Q5 (Q4 is annulled)
    assert score.annulled == 1


def test_partial_array_trailing_blanks():
    candidates = ["C", "E"]  # only 2 answers for 5 questions
    score = score_answers(candidates, ANSWER_KEY, EXPECTED)
    assert score.correct == 2
    assert score.blank == 2  # Q3 and Q5 (Q4 annulled)
    assert score.annulled == 1


def test_pct_all_correct():
    candidates = ["C", "E", "A", None, "B"]
    score = score_answers(candidates, ANSWER_KEY, EXPECTED)
    # 4 correct out of (5 - 1 annulled) = 4
    assert score.pct == 100.0


def test_pct_partial():
    candidates = ["C", "C", "A", None, "B"]
    score = score_answers(candidates, ANSWER_KEY, EXPECTED)
    # 3 correct out of 4 scorable = 75%
    assert score.pct == pytest.approx(75.0)


def test_all_blank():
    candidates = []
    score = score_answers(candidates, ANSWER_KEY, EXPECTED)
    assert score.correct == 0
    assert score.blank == 4  # Q4 annulled
    assert score.annulled == 1
    assert score.pct == 0.0


# --- build_breakdown ---

def test_build_breakdown_length():
    candidates = ["C", "E", "A", None, "B"]
    breakdown = build_breakdown(candidates, ANSWER_KEY, EXPECTED)
    assert len(breakdown) == EXPECTED


def test_build_breakdown_correct_hit():
    candidates = ["C", "E", "A", None, "B"]
    breakdown = build_breakdown(candidates, ANSWER_KEY, EXPECTED)
    assert breakdown[0].question == 1
    assert breakdown[0].candidate == "C"
    assert breakdown[0].correct == "C"
    assert breakdown[0].hit is True
    assert breakdown[0].annulled is False


def test_build_breakdown_wrong_hit():
    candidates = ["E", "E", "A", None, "B"]
    breakdown = build_breakdown(candidates, ANSWER_KEY, EXPECTED)
    assert breakdown[0].hit is False
    assert breakdown[0].candidate == "E"
    assert breakdown[0].correct == "C"


def test_build_breakdown_annulled():
    candidates = ["C", "E", "A", "B", "B"]
    breakdown = build_breakdown(candidates, ANSWER_KEY, EXPECTED)
    assert breakdown[3].annulled is True
    assert breakdown[3].hit is False
    assert breakdown[3].correct is None


def test_build_breakdown_blank_at_null():
    candidates = ["C", None, "A", None, "B"]
    breakdown = build_breakdown(candidates, ANSWER_KEY, EXPECTED)
    assert breakdown[1].candidate is None
    assert breakdown[1].hit is False


def test_build_breakdown_trailing_blank():
    candidates = ["C"]  # Q2–Q5 missing
    breakdown = build_breakdown(candidates, ANSWER_KEY, EXPECTED)
    assert breakdown[1].candidate is None  # Q2 trailing blank
    assert breakdown[1].hit is False
