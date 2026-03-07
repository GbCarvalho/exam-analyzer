# exam-analyzer

FastAPI service for ingesting Brazilian exam PDFs, extracting questions via OCR, managing answer keys, and scoring candidate responses.

## Features

- Upload exam PDFs (FGV and CEBRASPE supported)
- Automatic question extraction via PyMuPDF + Tesseract OCR, with Claude Vision as fallback
- Upload answer key PDFs or provide answers as JSON
- Score candidate answers and get per-question breakdown
- Manual question editing with PATCH endpoints

## Requirements

- Python 3.11+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on `PATH`
- Optional: `ANTHROPIC_API_KEY` env var for Claude Vision fallback

## Setup

```bash
pip install -r requirements.txt
```

## Running

```bash
uvicorn main:app --reload
```

API available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/exams` | Upload exam PDF |
| `GET` | `/exams/{id}` | Get exam with questions |
| `POST` | `/exams/{id}/answer-key` | Save answer key as JSON |
| `POST` | `/exams/{id}/answer-key/upload` | Upload answer key PDF |
| `GET` | `/exams/{id}/answer-key` | Get stored answer key |
| `POST` | `/exams/{id}/analyze` | Score candidate answers |
| `GET` | `/exams/{id}/results/{result_id}` | Get scored result with breakdown |
| `PATCH` | `/exams/{id}/questions/{number}` | Edit a single question |
| `PATCH` | `/exams/{id}/questions` | Bulk edit questions |

### Upload exam

```bash
curl -X POST http://localhost:8000/exams \
  -F "file=@exam.pdf" \
  -F "expected_questions=60" \
  -F "cargo=Auditor Fiscal"
```

Returns `200` (complete) or `206` (partial extraction) with the parsed questions. Returns `409` if an identical exam already exists.

### Score answers

```bash
curl -X POST http://localhost:8000/exams/{id}/analyze \
  -H "Content-Type: application/json" \
  -d '{"answers": ["C", "E", null, "C", ...]}'
```

Use `null` for blank answers.

## Testing

```bash
pytest
```

Benchmark tests (require real PDFs in `../assets/`) are excluded by default:

```bash
pytest tests/benchmark/ -v -s
```

## Storage

Exams, answer keys, and results are stored in memory. Data is lost on restart. S3 persistence is planned.
