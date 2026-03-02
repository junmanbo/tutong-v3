FROM python:3.12

ENV PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /workspace/

# Copy backend source (path dependency for bot_engine)
COPY ./backend/pyproject.toml /workspace/backend/
COPY ./backend/app /workspace/backend/app/

# Copy bot_engine pyproject first for dependency layer caching
COPY ./bot_engine/pyproject.toml /workspace/bot_engine/

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    cd /workspace/bot_engine && uv sync --no-dev

# Copy bot_engine source
COPY ./bot_engine /workspace/bot_engine/

# Re-sync to install the editable package itself
RUN --mount=type=cache,target=/root/.cache/uv \
    cd /workspace/bot_engine && uv sync --no-dev

ENV PATH="/workspace/bot_engine/.venv/bin:$PATH"

WORKDIR /workspace/bot_engine/

CMD ["celery", "-A", "bot_engine.celery_app", "worker", "--loglevel=info"]
