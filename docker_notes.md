# Docker Notes — Day 28

Containerizing the coverage chatbot (FastAPI backend + Streamlit frontend) with Docker and docker-compose.

## Architecture

Two services, defined in docker-compose.yml:

- backend - built from Dockerfile, runs coverage-chatbot-api/main.py via uvicorn on port 8000
- frontend - built from Dockerfile.frontend, runs app.py via streamlit on port 8501, and reaches the backend over the compose network at http://backend:8000/chat (via the BACKEND_URL environment variable)

Both Dockerfiles use a two-stage build: a builder stage with build-essential installs all Python dependencies into a virtualenv, and a slim final stage copies only that virtualenv, keeping the runtime image free of compiler tooling.

## Secrets and Data

GROQ_API_KEY is never hardcoded. Both services load it via env_file: .env. .env is in .gitignore and .dockerignore, so it is never committed or baked into an image. .env.example documents the required variable with a placeholder value only.

Chroma's local vector store is mounted as a volume (./chroma_data:/app/chroma_data) rather than copied into the image, so the vector data persists independently of the container lifecycle and rebuilds don't require re-embedding.

## Health Checks

Both Dockerfiles define a HEALTHCHECK that curls the service's own health endpoint (/health for the backend, Streamlit's built-in /_stcore/health for the frontend) every 30 seconds, with a 90-second start period to allow the embedding model to load on first boot. docker-compose additionally uses depends_on: backend: condition: service_healthy, so the frontend container does not start until the backend reports healthy.

## Build and Run

Command: docker compose up --build

Confirmed both containers reach a healthy state. Backend log showed: INFO Application startup complete, followed by GET /health returning 200 OK, and Docker itself reported "Container coverage-backend Healthy". Frontend log showed: "You can now view your Streamlit app in your browser" with Local URL http://localhost:8501.

curl http://localhost:8000/health from the host also returns {"status": "ok"}.

## End-to-End Test

With both containers running, http://localhost:8501 was opened in a browser and asked: "What is my deductible on the Gold PPO plan?"

Response: "Your annual deductible on the Gold PPO plan is $2,000." plus the Day 19 rich Coverage Summary card (Deductible $2,000.00, Copay 10.0%, Covered: Yes) rendered correctly - confirming the frontend container successfully reached the backend container over the compose network, and the full retrieval -> LLM -> UI pipeline works identically inside Docker.

## Issues Encountered and Fixed

Several real problems came up getting this running, documented here rather than glossed over.

numpy build failure. The base images were pinned to python:3.11-slim, but requirements.txt (frozen from this machine's Python 3.13 environment) pinned numpy==2.5.1, which requires Python >=3.12. Fix: both Dockerfiles were changed to python:3.13-slim to match the host environment that generated requirements.txt.

pywin32 install failure. requirements.txt included pywin32, a Windows-only package that cannot install on the Linux base image. Fix: created requirements-docker.txt, a copy of requirements.txt with pywin32 (and other Windows-only packages) filtered out, and pointed both Dockerfiles at it instead.

GPU-flavoured PyTorch bloating the image and exhausting disk space. By default, pip install pulls the CUDA/GPU build of torch, which pulled in roughly 8GB of nvidia-* packages this machine has no use for (there is no GPU here; the embedding model already runs on CPU, as confirmed in earlier days' logs). Combined with limited free disk space, this caused a "no space left on device" failure mid-build. Fix: both Dockerfiles now install with --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple, which pulls the CPU-only torch build (about 200MB instead of about 8GB) with no change in behaviour, since this machine was always running on CPU anyway.

Docker's own WSL2 virtual disk was full of reclaimed-but-unreturned space. Even after docker system prune, Windows disk space did not increase, because Docker's WSL2 disk file (docker_data.vhdx) had grown to about 14GB of allocated space that wasn't given back to the OS. Fix: shut down WSL with wsl --shutdown, then compacted the virtual disk with diskpart (select vdisk file, attach vdisk readonly, compact vdisk, detach vdisk), which reclaimed roughly 7.5GB back to the host filesystem.

Docker Desktop's build engine crashed mid-build twice ("frontend grpc server closed unexpectedly" / "file has already been closed"). This appears to be an intermittent Docker Desktop engine issue on this machine, unrelated to the Dockerfiles or compose config - restarting Docker Desktop (fully quitting via the tray icon, not just the Restart button) resolved it both times.

Blank white page on first load of the frontend. The Streamlit UI loaded as an empty white page with only the browser tab title showing "Streamlit" - the WebSocket connection Streamlit needs for rendering was not completing inside the container. Fix: added --server.enableCORS=false --server.enableXsrfProtection=false to the Streamlit CMD in Dockerfile.frontend. After rebuilding, the app rendered correctly.

## Summary

Both services build, start, pass their health checks, and correctly serve a real end-to-end request through the browser. The main lessons from this exercise: Docker base image versions must match the Python version requirements.txt was frozen on; OS-specific packages need a separate requirements file for Linux containers; GPU-flavoured ML dependencies are worth pinning to CPU-only builds when there is no GPU, both for image size and to avoid exhausting disk space during heavy local development; and Streamlit's CORS/XSRF defaults can silently break rendering behind a container/proxy boundary.