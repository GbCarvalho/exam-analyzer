from PIL import Image
from models.schemas import Question


def _blank_image():
    return Image.new("RGB", (100, 100), color="white")


def _questions(n: int) -> list[Question]:
    return [Question(number=i, statement=f"Q{i}") for i in range(1, n + 1)]


def test_image_to_text_returns_string():
    from services.ocr import image_to_text
    result = image_to_text(_blank_image())
    assert isinstance(result, str)


def test_validate_question_count_passes():
    from services.ocr import validate_question_count
    assert validate_question_count(_questions(5), expected=5) is True


def test_validate_question_count_fails():
    from services.ocr import validate_question_count
    assert validate_question_count(_questions(3), expected=5) is False


def test_needs_fallback_true_when_count_mismatch():
    from services.ocr import needs_fallback
    assert needs_fallback(_questions(2), expected=5) is True


def test_needs_fallback_false_when_count_matches():
    from services.ocr import needs_fallback
    assert needs_fallback(_questions(5), expected=5) is False


def test_image_to_base64_returns_string():
    from services.ocr import image_to_base64
    result = image_to_base64(_blank_image())
    assert isinstance(result, str)
    assert len(result) > 0
