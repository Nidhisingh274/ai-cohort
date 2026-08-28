# syntax=docker/dockerfile:1

# =====================
# Stage 1: builder - installs dependencies into a virtualenv
# =====================
FROM python:3.13-slim AS builder

# Build tools are only needed here, not in the final image
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Use the CPU-only PyTorch build - this machine has no GPU, and the CUDA
# packages would add roughly 8GB to the image for no benefit
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
       --extra-index-url https://pypi.org/simple \
       -r requirements-docker.txt

# =====================
# Stage 2: final - slim runtime, no build tools
# =====================
FROM python:3.13-slim

# curl is needed for the HEALTHCHECK probe
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only the finished virtualenv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Application code and data the backend needs at runtime
COPY coverage-chatbot-api/ ./coverage-chatbot-api/
COPY retrieval_engine.py rag_chatbot.py redact_pii.py token_utils.py ./
COPY coverage.db ./
COPY data/ ./data/

# Keep Python from writing .pyc files and buffering logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# STEP 6: container health probe - hits the /health endpoint from Day 3
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

WORKDIR /app/coverage-chatbot-api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]