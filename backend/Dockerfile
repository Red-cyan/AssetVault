FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV ASSETVAULT_DATABASE_URL=sqlite:////app/data/assetvault.db
ENV ASSETVAULT_THUMBNAIL_DIR=/app/cache/thumbnails

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend ./backend

RUN mkdir -p /app/data /app/cache/thumbnails /app/backups

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
