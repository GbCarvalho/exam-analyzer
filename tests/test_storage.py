import pytest
import storage.memory as mem


@pytest.fixture(autouse=True)
def clear():
    mem.clear_all()
    yield
    mem.clear_all()


def test_store_and_get_exam():
    mem.store_exam("id1", {"exam_code": "TCU", "cargo": "Auditor", "exam_type": None, "booklet_type": "basicos"})
    assert mem.get_exam("id1")["exam_code"] == "TCU"


def test_get_exam_returns_none_if_missing():
    assert mem.get_exam("nonexistent") is None


def test_find_exam_by_identity_match():
    mem.store_exam("id1", {"exam_code": "TCU", "cargo": "Auditor", "exam_type": None, "booklet_type": "basicos"})
    result = mem.find_exam_by_identity("TCU", "Auditor", None, "basicos")
    assert result is not None
    assert result["exam_code"] == "TCU"


def test_find_exam_by_identity_no_match():
    mem.store_exam("id1", {"exam_code": "TCU", "cargo": "Auditor", "exam_type": None, "booklet_type": "basicos"})
    assert mem.find_exam_by_identity("TCU", "Other", None, "basicos") is None


def test_clear_all_removes_everything():
    mem.store_exam("id1", {"exam_code": "TCU", "cargo": None, "exam_type": None, "booklet_type": None})
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
