FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
# ocrmac 依赖 macOS Vision，在 Linux 上跳过；OCR 会回退 tesseract。
RUN uv sync --frozen --no-dev --no-install-package ocrmac

COPY app ./app
COPY samples ./samples

EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
