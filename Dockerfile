FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# run the venv binaries directly: `uv run` would re-sync (and pull dev deps) on every start
ENV PATH="/app/.venv/bin:$PATH"

# ponytail: --forwarded-allow-ips=* безпечне лише поки api не публікує порт назовні
# (єдиний шлях — Caddy). Публікуватимеш 8000 — заміни * на підмережу docker.
CMD ["uvicorn", "app.main:sio_asgi_app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
