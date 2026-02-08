FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY alembic.ini .

# Set Python path
ENV PYTHONPATH=/app

# Default to worker, can override with beat
CMD ["celery", "-A", "src.workers.celery_app", "worker", "--loglevel=info"]
