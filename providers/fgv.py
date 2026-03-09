from __future__ import annotations
import re
from models.schemas import Question

_EXAM_CODE_RE = re.compile(r"CURSO DE FORMAÇÃO [\d/]+", re.IGNORECASE)
_EXAM_TYPE_RE = re.compile(r"TIPO\s+(\w+)", re.IGNORECASE)
# Section header in answer key: "Auditor Fiscal - 1 - Turno Manhã"
_SECTION_RE = re.compile(r"^(.+?)\s*-\s*(\w+)\s*-\s*Turno", re.MULTILINE)
_ANSWER_LINE_RE = re.compile(r"^(\d+)\s+([A-E*])\s*$", re.MULTILINE)

# Known FGV header fragments to skip during question parsing
_HEADER_FRAGMENTS = (
    "FGV CONHECIMENTO",
    "TIPO",
    "RECEITA FEDERAL",
    "AUDITOR FISCAL",
    "ANALISTA TRIBUTÁRIO",
    "ANALISTA TRIBUTARIO",
    "PÁGINA",
    "PAGINA",
)


def is_cover_page(right_column_text: str) -> bool:
    """FGV cover page: right column has no standalone question number on its own line."""
    return not bool(re.search(r"^\d+\s*$", right_column_text, re.MULTILINE))


def extract_exam_code(left_text: str) -> str | None:
    m = _EXAM_CODE_RE.search(left_text)
    return m.group(0).strip() if m else None


def extract_cargo(left_text: str) -> str | None:
    """Extract cargo from FGV left column header (all-caps line after institution name)."""
    lines = [ln.strip() for ln in left_text.splitlines() if ln.strip()]
    for line in lines:
        # All-caps line, at least 5 chars, not the institution name
        if (
            re.match(r"^[A-ZÁÉÍÓÚÃÕÇ ]{5,}$", line, re.UNICODE)
            and "RECEITA" not in line
            and "BRASIL" not in line
            and "FEDERAL" not in line
            and "CURSO" not in line
            and "FORMAÇÃO" not in line
        ):
            return line
    return None


def extract_exam_type(right_text: str) -> str | None:
    """Extract exam type from FGV right column header (e.g. 'TIPO BRANCA')."""
    m = _EXAM_TYPE_RE.search(right_text)
    if m:
        return f"TIPO {m.group(1).upper()}"
    return None


def parse_questions(column_texts: list[str]) -> list[Question]:
    """
    Parse questions from ordered column texts (left, right, left, right, ...).

    FGV format: question number appears alone on its own line, followed by
    question text on subsequent lines. E.g.:
        1
        Tendo em vista o papel histórico...
        (A) option A
        ...
    """
    questions: list[Question] = []
    current_number: int | None = None
    current_lines: list[str] = []

    for text in column_texts:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Standalone number = question start
            if re.match(r"^\d+$", stripped):
                if current_number is not None:
                    questions.append(
                        Question(
                            number=current_number,
                            statement=" ".join(current_lines).strip(),
                        )
                    )
                current_number = int(stripped)
                current_lines = []
            elif current_number is not None:
                if any(frag in stripped.upper() for frag in _HEADER_FRAGMENTS):
                    continue
                current_lines.append(stripped)

    if current_number is not None:
        questions.append(
            Question(
                number=current_number,
                statement=" ".join(current_lines).strip(),
            )
        )

    return questions


def parse_answer_key_text(text: str, cargo: str, exam_type: str) -> dict[str, str]:
    """
    Parse FGV answer key for a specific cargo and exam_type number (e.g. "Auditor Fiscal", "1").
    Returns empty dict if section is not found.
    """
    sections = list(_SECTION_RE.finditer(text))
    target_start = None
    target_end = None

    for i, sec in enumerate(sections):
        sec_cargo = sec.group(1).strip()
        sec_type = sec.group(2).strip()
        if cargo.lower() in sec_cargo.lower() and sec_type == exam_type:
            target_start = sec.end()
            target_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            break

    if target_start is None:
        # Fallback: match by cargo name only (ignore turno)
        for i, sec in enumerate(sections):
            if cargo.lower() in sec.group(1).strip().lower():
                target_start = sec.end()
                target_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
                break

    if target_start is None:
        return {}

    result: dict[str, str] = {}
    for m in _ANSWER_LINE_RE.finditer(text[target_start:target_end]):
        result[m.group(1)] = m.group(2)
    return result
