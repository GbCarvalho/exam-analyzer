import pytest
from providers.fgv import (
    extract_exam_code,
    extract_cargo,
    extract_exam_type,
    is_cover_page,
    parse_questions,
    parse_answer_key_text,
)


# --- is_cover_page ---

def test_fgv_cover_page_detected():
    right_text = "CEITA FEDERAL DO BRASIL\nCURSO DE FORMAÇÃO 2025/1"
    assert is_cover_page(right_text) is True


def test_fgv_cover_page_not_detected_on_content_page():
    right_text = "FGV CONHECIMENTO\n\nTIPO BRANCA – PÁGINA 2\n2 Com relação à estrutura..."
    assert is_cover_page(right_text) is False


# --- extract_exam_code ---

def test_extract_exam_code():
    left_text = "RECEITA FEDERAL DO BRASIL (CURSO DE FORMAÇÃO 2025/1)\n\nAUDITOR FISCAL"
    assert extract_exam_code(left_text) == "CURSO DE FORMAÇÃO 2025/1"


def test_extract_exam_code_returns_none_if_missing():
    assert extract_exam_code("some random text") is None


# --- extract_cargo ---

def test_extract_cargo():
    left_text = "RECEITA FEDERAL DO BRASIL (CURSO DE FORMAÇÃO 2025/1)\n\nAUDITOR FISCAL\n\nSeção X"
    assert extract_cargo(left_text) == "AUDITOR FISCAL"


def test_extract_cargo_analista():
    left_text = "RECEITA FEDERAL DO BRASIL (CURSO DE FORMAÇÃO 2025/1)\n\nANALISTA TRIBUTÁRIO\n\nSeção Y"
    assert extract_cargo(left_text) == "ANALISTA TRIBUTÁRIO"


def test_extract_cargo_returns_none_if_missing():
    assert extract_cargo("RECEITA FEDERAL DO BRASIL") is None


# --- extract_exam_type ---

def test_extract_exam_type():
    right_text = "FGV CONHECIMENTO\n\nTIPO BRANCA – PÁGINA 2"
    assert extract_exam_type(right_text) == "TIPO BRANCA"


def test_extract_exam_type_returns_none_if_missing():
    assert extract_exam_type("FGV CONHECIMENTO") is None


# --- parse_questions ---

def test_parse_questions_fgv():
    left = "RECEITA FEDERAL DO BRASIL (CURSO DE FORMAÇÃO 2025/1)\n\nAUDITOR FISCAL\n\nSeção MCA\n1 Tendo em vista o papel histórico..."
    right = "FGV CONHECIMENTO\n\nTIPO BRANCA – PÁGINA 2\n2 Com relação à estrutura..."
    questions = parse_questions([left, right])
    assert len(questions) == 2
    assert questions[0].number == 1
    assert questions[1].number == 2


def test_parse_questions_strips_headers():
    right = "FGV CONHECIMENTO\n\nTIPO BRANCA – PÁGINA 2\n5 Qual é a resposta?"
    questions = parse_questions([right])
    assert len(questions) == 1
    assert "FGV" not in questions[0].statement
    assert "TIPO" not in questions[0].statement


# --- parse_answer_key_text ---

def test_parse_answer_key_fgv_section():
    text = (
        "Auditor Fiscal - 1 - Turno Manhã\n"
        "1 C\n2 D\n3 A\n4 *\n"
    )
    result = parse_answer_key_text(text, cargo="Auditor Fiscal", exam_type="1")
    assert result == {"1": "C", "2": "D", "3": "A", "4": "*"}


def test_parse_answer_key_fgv_wrong_cargo_returns_empty():
    text = (
        "Auditor Fiscal - 1 - Turno Manhã\n"
        "1 C\n2 D\n"
    )
    result = parse_answer_key_text(text, cargo="Analista Tributário", exam_type="1")
    assert result == {}
