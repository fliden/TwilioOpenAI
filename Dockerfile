# 1. Base image
FROM python:3.13-slim

# 2. Workdir
WORKDIR /app

# 3. Install system deps (only if you need C extensions)
#RUN apt-get update && apt-get install -y --no-install-recommends \
#    build-essential curl \
# && rm -rf /var/lib/apt/lists/*

# 4. Install uv
RUN pip install --no-cache-dir uv

# 5. Copy pyproject + lock file first (better Docker caching)
COPY pyproject.toml uv.lock* ./

# 6. Install project dependencies (production only)
RUN uv sync --frozen --no-dev

# 7. Copy the rest of the code
COPY . .

# 8. Railway sets $PORT dynamically (default 8000 locally)
ENV PORT=8000

# 9. Start FastAPI with Uvicorn
CMD ["sh", "-c", "uv run uvicorn app:app --host 0.0.0.0 --port  ${PORT:-8000}"]
