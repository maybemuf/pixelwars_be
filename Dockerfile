FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --system --uid 1000 app \
 && mkdir -p /app/logs \
 && chown -R app:app /app
USER app

CMD ["uvicorn", "app.main:sio_asgi_app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
