# Digests, not tags: a tag can be repointed under us, and the two python stages must be
# the same image -- the venv bakes absolute /app/.venv paths and one interpreter ABI.
ARG PYTHON_IMAGE=python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285

FROM ${PYTHON_IMAGE} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 /uv /bin/uv

WORKDIR /app

# Dependencies before the source, so editing app/ doesn't re-resolve the world.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev


FROM ${PYTHON_IMAGE}

WORKDIR /app

RUN useradd --system --uid 1000 app \
 && mkdir -p /app/logs \
 && chown -R app:app /app

# Only the venv and what runs crosses over; uv and the build cache stay behind.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app app
# Read at runtime by setup_logging, so it has to be copied explicitly now that the
# final stage no longer does COPY . .
COPY --chown=app:app logging_config.yaml ./

ENV PATH="/app/.venv/bin:$PATH"

USER app

CMD ["uvicorn", "app.main:sio_asgi_app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
