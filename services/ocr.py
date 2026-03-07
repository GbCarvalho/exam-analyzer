from __future__ import annotations
import base64
import io
import pytesseract
from PIL import Image
from models.schemas import Question

# Portuguese language, single block page segmentation
_TSS_CONFIG = "--psm 6 -l por"


def image_to_text(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, config=_TSS_CONFIG)


def validate_question_count(questions: list[Question], expected: int) -> bool:
    return len(questions) == expected


def needs_fallback(questions: list[Question], expected: int) -> bool:
    return not validate_question_count(questions, expected)


def image_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def ocr_with_claude_fallback(
    images: list[Image.Image],
    client,  # anthropic.Anthropic
) -> str:
    """Send page images to Claude vision and return extracted text."""
    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_to_base64(img),
            },
        })
    content.append({
        "type": "text",
        "text": (
            "Extract all exam questions from these images. "
            "For each question, output its number followed by its full text. "
            "Preserve the original Portuguese text exactly."
        ),
    })
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text
