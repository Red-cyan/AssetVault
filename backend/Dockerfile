FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV ASSETVAULT_DATABASE_URL=postgresql+psycopg://assetvault:assetvault@postgres:5432/assetvault
ENV ASSETVAULT_THUMBNAIL_DIR=/app/cache/thumbnails
ENV ASSETVAULT_MODEL_CACHE_DIR=/app/models
ENV HF_HOME=/app/models

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend ./backend

RUN mkdir -p /app/cache/thumbnails /app/backups /app/models

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
