FROM python:3.11-slim

RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock requirements.txt ./
RUN uv sync --group dev

COPY . .

CMD ["uv", "run", "pytest"]
