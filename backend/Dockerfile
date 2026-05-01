FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Render / Railway honour the PORT env var; fall back to 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
