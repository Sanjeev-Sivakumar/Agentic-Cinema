# ==============================================================================
# Chain of Title — Production Dockerfile for Google Cloud Run
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered log streaming
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    APP_ENV=production \
    DEBIAN_FRONTEND=noninteractive

# Install essential runtime packages for OpenCV, FFmpeg, and EasyOCR/Torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source code and models
COPY backend /app/backend
COPY yolov8n.pt /app/yolov8n.pt
COPY yolov8n.pt /app/backend/yolov8n.pt

# Ensure local fallback directories exist
RUN mkdir -p /app/data/storage /app/reports

# Set Python path
ENV PYTHONPATH=/app/backend

# Cloud Run exposes port 8080 by default
EXPOSE 8080

WORKDIR /app/backend

# Healthcheck for container runtimes
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Start Uvicorn bound to 0.0.0.0:$PORT
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --log-level info
