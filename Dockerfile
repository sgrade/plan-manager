FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app

# Dependencies layer (cached separately from app code)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --locked --no-install-project

# App + docs (docs are force-included in the wheel by hatchling)
COPY src/ src/
COPY docs/ docs/
RUN uv sync --no-dev --locked --no-editable

# --- Runtime ---
FROM python:3.13-slim-bookworm

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 3000
CMD ["pm"]
