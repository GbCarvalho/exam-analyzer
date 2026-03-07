import pytest
from providers.cebraspe import (
    extract_exam_code,
    parse_questions,
    parse_answer_key_text,
    is_cover_page,
)


# --- extract_exam_code ---

def test_extract_exam_code_standard():
    header = "CEBRASPE – TCU/AUFC – Edital: 2025"
    assert extract_exam_code(header) == "TCU/AUFC – Edital: 2025"


def test_extract_exam_code_returns_none_if_not_found():
    assert extract_exam_code("some random text") is None


# --- is_cover_page ---

def test_cebraspe_has_no_cover_page():
    assert is_cover_page("CEBRASPE – TCU/AUFC – Edital: 2025\n\n1 Some question text") is False


# --- parse_questions ---

def test_parse_questions_basic():
    text = """
CEBRASPE – TCU/AUFC – Edital: 2025

1 O Brasil é a maior economia da América Latina.

2 O TCU é um órgão do Poder Executivo.
"""
    questions = parse_questions(text)
    assert len(questions) == 2
    assert questions[0].number == 1
    assert "maior economia" in questions[0].statement
    assert questions[1].number == 2


def test_parse_questions_skips_header():
    text = "CEBRASPE – TCU/AUFC – Edital: 2025\n\n1 Questão um."
    questions = parse_questions(text)
    assert len(questions) == 1
    assert questions[0].number == 1


# --- parse_answer_key_text ---

def test_parse_answer_key_ce_format():
    text = """
1  2  3  4  5
C  E  C  C  E
"""
    result = parse_answer_key_text(text)
    assert result == {"1": "C", "2": "E", "3": "C", "4": "C", "5": "E"}


def test_parse_answer_key_annulled():
    text = """
1  2  3
C  *  E
"""
    result = parse_answer_key_text(text)
    assert result == {"1": "C", "2": "*", "3": "E"}


def test_parse_answer_key_ignores_zeros():
    text = """
1  2  3
C  E  0
"""
    result = parse_answer_key_text(text)
    assert "3" not in result
