FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

# The container runs with a read-only filesystem, so bytecode is compiled at build time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# Dependencies first, so a code change does not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# README.md is package metadata (pyproject `readme`), needed only to build the project itself.
COPY README.md ./
COPY deel_advisor ./deel_advisor
RUN uv sync --frozen --no-dev --no-editable --no-cache \
    && rm -rf deel_advisor

ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

RUN useradd --system --uid 10001 --no-create-home advisor \
    && mkdir -p /app/data \
    && chown advisor /app/data
USER advisor

ENV DATA_DIR=/app/data \
    MPLCONFIGDIR=/tmp/matplotlib
# Healthy while the heartbeat task keeps reaching Telegram (it writes every 60 s).
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import os,sys,time; sys.exit(time.time() - os.path.getmtime('/tmp/deel-advisor.heartbeat') > 180)"]

CMD ["python", "-m", "deel_advisor"]
