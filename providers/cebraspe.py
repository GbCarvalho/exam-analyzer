from __future__ import annotations
import re
from models.schemas import Question

# CEBRASPE right-column header: "CEBRASPE – TCU/AUFC – Edital: 2025"
_EXAM_CODE_RE = re.compile(r"CEBRASPE\s*[–\-]\s*(.+)", re.IGNORECASE)


def extract_exam_code(text: str) -> str | None:
    match = _EXAM_CODE_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def is_cover_page(text: str) -> bool:
    # CEBRASPE never has a cover page
    return False


def parse_questions(text: str) -> list[Question]:
    """Parse numbered questions from OCR'd CEBRASPE text."""
    questions: list[Question] = []
    current_number: int | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^(\d+)\s+(.*)", line.strip())
        if m:
            if current_number is not None:
                questions.append(Question(
                    number=current_number,
                    statement=" ".join(current_lines).strip(),
                ))
            current_number = int(m.group(1))
            current_lines = [m.group(2)]
        elif current_number is not None and line.strip():
            current_lines.append(line.strip())

    if current_number is not None:
        questions.append(Question(
            number=current_number,
            statement=" ".join(current_lines).strip(),
        ))

    return questions


def parse_answer_key_text(text: str) -> dict[str, str]:
    """
    Parse CEBRASPE answer key grid (space/tab-separated numbers and C/E/* answers).
    Ignores rows with '0' (filler placeholders).
    """
    result: dict[str, str] = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    i = 0
    while i < len(lines):
        tokens = lines[i].split()
        if tokens and all(t.isdigit() for t in tokens):
            if i + 1 < len(lines):
                ans_tokens = lines[i + 1].split()
                if len(ans_tokens) == len(tokens) and all(
                    t in ("C", "E", "*", "0") for t in ans_tokens
                ):
                    for num, ans in zip(tokens, ans_tokens):
                        if ans != "0":
                            result[num] = ans
                    i += 2
                    continue
        i += 1

    return result
