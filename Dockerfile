# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install into site-packages
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Final minimal run image
FROM python:3.12-slim AS runner

WORKDIR /app

# Copy python dependencies from builder
COPY --from=builder /install /usr/local
COPY . .

# Setup non-privileged system user for absolute security isolation
RUN groupadd -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Start server dynamically consuming PORT env var with production timeout configurations
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 5 --timeout-graceful-shutdown 30"]
