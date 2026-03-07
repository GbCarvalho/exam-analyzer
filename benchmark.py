"""
Real-world benchmark: runs full pipeline on actual exam PDFs and reports timing.
Usage: python benchmark.py
"""
import time
import json
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
import storage.memory as mem

client = TestClient(app)
ASSETS = Path(__file__).parent.parent / "assets"


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def step(label: str, resp, t: float):
    status = resp.status_code
    mark = "✓" if status in (200, 206) else "✗"
    partial = " [PARTIAL]" if status == 206 else ""
    print(f"  {mark} [{t*1000:.0f}ms] {label} → {status}{partial}")
    if status not in (200, 206):
        print(f"      ERROR: {resp.text[:200]}")
    return resp.json() if status in (200, 206) else None


def run_fgv():
    section("FGV — Auditor Fiscal (frb100-tipo-1)")

    # 1. Upload exam
    t0 = time.perf_counter()
    with open(ASSETS / "fgv-auditor-fiscal-frb100-tipo-1.pdf", "rb") as f:
        resp = client.post(
            "/exams",
            data={"expected_questions": 60},
            files={"file": ("exam.pdf", f, "application/pdf")},
        )
    body = step("POST /exams", resp, time.perf_counter() - t0)
    if not body:
        return

    exam_id = body["exam_id"]
    print(f"      exam_id    : {exam_id}")
    print(f"      exam_code  : {body['exam_code']}")
    print(f"      cargo      : {body['cargo']}")
    print(f"      exam_type  : {body['exam_type']}")
    print(f"      questions  : {len(body['questions'])} extracted")
    print(f"      partial    : {body['partial']}")

    # 2. Upload gabarito PDF
    t0 = time.perf_counter()
    with open(ASSETS / "fgv-gabarito-analista-tributario-e-auditor-fiscal.pdf", "rb") as f:
        resp = client.post(
            f"/exams/{exam_id}/answer-key/upload",
            files={"file": ("gabarito.pdf", f, "application/pdf")},
        )
    ak_body = step("POST /answer-key/upload (PDF)", resp, time.perf_counter() - t0)
    if ak_body:
        print(f"      answers parsed: {len(ak_body['answers'])}")

    # 3. Analyze with candidate answers (first 10 correct, rest blank)
    correct_answers = ak_body["answers"] if ak_body else {}
    candidate = [correct_answers.get(str(i)) for i in range(1, 61)]
    # Blank out questions 11-60
    candidate = candidate[:10] + [None] * 50

    t0 = time.perf_counter()
    resp = client.post(f"/exams/{exam_id}/analyze", json={"answers": candidate})
    score_body = step("POST /analyze", resp, time.perf_counter() - t0)
    if score_body:
        s = score_body["score"]
        print(f"      correct={s['correct']} wrong={s['wrong']} blank={s['blank']} annulled={s['annulled']} pct={s['pct']}%")

    # 4. Fetch breakdown
    if score_body:
        result_id = score_body["result_id"]
        t0 = time.perf_counter()
        resp = client.get(f"/exams/{exam_id}/results/{result_id}")
        step("GET /results/{result_id}", resp, time.perf_counter() - t0)


def run_cebraspe():
    section("CEBRASPE — TCU/AUFC Básicos")

    # 1. Upload exam (cargo required for CEBRASPE)
    t0 = time.perf_counter()
    with open(ASSETS / "cebraspe-basicos-tcu_25_aufc.pdf", "rb") as f:
        resp = client.post(
            "/exams",
            data={
                "expected_questions": 100,
                "cargo": "Auditor Federal de Controle Externo",
                "booklet_type": "basicos",
            },
            files={"file": ("exam.pdf", f, "application/pdf")},
        )
    body = step("POST /exams", resp, time.perf_counter() - t0)
    if not body:
        return

    exam_id = body["exam_id"]
    print(f"      exam_id    : {exam_id}")
    print(f"      exam_code  : {body['exam_code']}")
    print(f"      cargo      : {body['cargo']}")
    print(f"      questions  : {len(body['questions'])} extracted")
    print(f"      partial    : {body['partial']}")

    # 2. Upload gabarito PDF
    t0 = time.perf_counter()
    with open(ASSETS / "cebraspe-gabarito-basicos-tcu_25_aufc.pdf", "rb") as f:
        resp = client.post(
            f"/exams/{exam_id}/answer-key/upload",
            files={"file": ("gabarito.pdf", f, "application/pdf")},
        )
    ak_body = step("POST /answer-key/upload (PDF)", resp, time.perf_counter() - t0)
    if ak_body:
        print(f"      answers parsed: {len(ak_body['answers'])}")

    # 3. Analyze — simulate candidate getting 60% right
    correct_answers = ak_body["answers"] if ak_body else {}
    candidate = []
    for i in range(1, 101):
        correct = correct_answers.get(str(i))
        if correct == "*":
            candidate.append(None)
        elif i % 3 == 0:
            candidate.append(None)  # blank every 3rd
        else:
            candidate.append(correct)

    t0 = time.perf_counter()
    resp = client.post(f"/exams/{exam_id}/analyze", json={"answers": candidate})
    score_body = step("POST /analyze", resp, time.perf_counter() - t0)
    if score_body:
        s = score_body["score"]
        print(f"      correct={s['correct']} wrong={s['wrong']} blank={s['blank']} annulled={s['annulled']} pct={s['pct']}%")

    # 4. Fetch breakdown
    if score_body:
        result_id = score_body["result_id"]
        t0 = time.perf_counter()
        resp = client.get(f"/exams/{exam_id}/results/{result_id}")
        step("GET /results/{result_id}", resp, time.perf_counter() - t0)


def run_fgv_analista():
    section("FGV — Analista Tributário (rfb200-tipo-1)")

    t0 = time.perf_counter()
    with open(ASSETS / "fgv-analista-tributario-rfb200-tipo-1.pdf", "rb") as f:
        resp = client.post(
            "/exams",
            data={"expected_questions": 60},
            files={"file": ("exam.pdf", f, "application/pdf")},
        )
    body = step("POST /exams", resp, time.perf_counter() - t0)
    if not body:
        return

    exam_id = body["exam_id"]
    print(f"      exam_id    : {exam_id}")
    print(f"      exam_code  : {body['exam_code']}")
    print(f"      cargo      : {body['cargo']}")
    print(f"      exam_type  : {body['exam_type']}")
    print(f"      questions  : {len(body['questions'])} extracted")
    print(f"      partial    : {body['partial']}")

    # Upload answer key as JSON (using known gabarito data)
    t0 = time.perf_counter()
    with open(ASSETS / "fgv-gabarito-analista-tributario-e-auditor-fiscal.pdf", "rb") as f:
        resp = client.post(
            f"/exams/{exam_id}/answer-key/upload",
            files={"file": ("gabarito.pdf", f, "application/pdf")},
        )
    ak_body = step("POST /answer-key/upload (PDF)", resp, time.perf_counter() - t0)
    if ak_body:
        print(f"      answers parsed: {len(ak_body['answers'])}")


if __name__ == "__main__":
    mem.clear_all()
    total_start = time.perf_counter()

    run_fgv()
    run_cebraspe()
    run_fgv_analista()

    total = time.perf_counter() - total_start
    section(f"TOTAL: {total*1000:.0f}ms")
