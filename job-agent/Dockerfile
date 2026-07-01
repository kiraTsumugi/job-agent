FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ ./app/
COPY data/ ./data/
COPY scripts/ ./scripts/

EXPOSE 8000
CMD ["sh", "-c", "python scripts/ingest.py --vectors && python scripts/ingest_eval_jds.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
