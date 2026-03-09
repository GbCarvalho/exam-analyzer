import pytest
import storage.memory as mem


@pytest.fixture(autouse=True)
def clear():
    mem.clear_all()
    yield
    mem.clear_all()


def test_store_and_get_exam():
    mem.store_exam(
        "id1",
        {"exam_code": "TCU", "cargo": "Auditor", "exam_type": None, "booklet_type": "basicos"},
    )
    assert mem.get_exam("id1")["exam_code"] == "TCU"


def test_get_exam_returns_none_if_missing():
    assert mem.get_exam("nonexistent") is None


def test_find_exam_by_identity_match():
    mem.store_exam(
        "id1",
        {"exam_code": "TCU", "cargo": "Auditor", "exam_type": None, "booklet_type": "basicos"},
    )
    result = mem.find_exam_by_identity("TCU", "Auditor", None, "basicos")
    assert result is not None
    assert result["exam_code"] == "TCU"


def test_find_exam_by_identity_no_match():
    mem.store_exam(
        "id1",
        {"exam_code": "TCU", "cargo": "Auditor", "exam_type": None, "booklet_type": "basicos"},
    )
    assert mem.find_exam_by_identity("TCU", "Other", None, "basicos") is None


def test_clear_all_removes_everything():
    mem.store_exam(
        "id1", {"exam_code": "TCU", "cargo": None, "exam_type": None, "booklet_type": None}
    )
    mem.store_answer_key("id1", {"answer_key_id": "ak1", "answers": {"1": "C"}})
    mem.store_result("r1", {"score": {}, "breakdown": []})
    mem.clear_all()
    assert mem.get_exam("id1") is None
    assert mem.get_answer_key("id1") is None
    assert mem.get_result("r1") is None


def test_store_and_get_answer_key():
    mem.store_answer_key("exam1", {"answer_key_id": "ak1", "answers": {"1": "C", "2": "E"}})
    ak = mem.get_answer_key("exam1")
    assert ak["answers"]["1"] == "C"


def test_store_and_get_result():
    mem.store_result("r1", {"score": {"correct": 5}, "breakdown": []})
    assert mem.get_result("r1")["score"]["correct"] == 5


def test_update_question_sets_statement_and_manual():
    mem.store_exam(
        "e1",
        {
            "exam_id": "e1",
            "questions": [{"number": 1, "statement": "original", "manual": False}],
        },
    )
    result = mem.update_question("e1", 1, "updated")
    assert result["statement"] == "updated"
    assert result["manual"] is True
    exam = mem.get_exam("e1")
    assert exam["questions"][0]["statement"] == "updated"
    assert exam["questions"][0]["manual"] is True


def test_update_question_returns_none_for_missing_exam():
    assert mem.update_question("nope", 1, "x") is None


def test_update_question_returns_none_for_missing_number():
    mem.store_exam(
        "e2", {"exam_id": "e2", "questions": [{"number": 1, "statement": "q", "manual": False}]}
    )
    assert mem.update_question("e2", 99, "x") is None


def test_bulk_update_questions_sets_all():
    mem.store_exam(
        "e3",
        {
            "exam_id": "e3",
            "questions": [
                {"number": 1, "statement": "q1", "manual": False},
                {"number": 2, "statement": "q2", "manual": False},
            ],
        },
    )
    results = mem.bulk_update_questions(
        "e3",
        [
            {"number": 1, "statement": "q1 edited"},
            {"number": 2, "statement": "q2 edited"},
        ],
    )
    assert len(results) == 2
    assert all(r["manual"] is True for r in results)
    assert results[0]["statement"] == "q1 edited"


def test_bulk_update_questions_skips_missing_numbers():
    mem.store_exam(
        "e4",
        {
            "exam_id": "e4",
            "questions": [{"number": 1, "statement": "q1", "manual": False}],
        },
    )
    results = mem.bulk_update_questions(
        "e4",
        [
            {"number": 1, "statement": "ok"},
            {"number": 99, "statement": "missing"},
        ],
    )
    assert len(results) == 1
    assert results[0]["number"] == 1
