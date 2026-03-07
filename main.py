from fastapi import FastAPI

app = FastAPI(title="Exam Analyzer")


@app.get("/health")
def health():
    return {"status": "ok"}
