# Pitwall API: FastAPI + the LangGraph agent. Telemetry and corner caches live in /data.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.18 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1
WORKDIR /app

# Dependencies first, so code changes do not reinstall them
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project
COPY src ./src
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH" PITWALL_DATA_DIR=/data PYTHONUNBUFFERED=1
RUN mkdir -p /data && useradd --create-home pitwall && chown pitwall /data
USER pitwall
EXPOSE 8000
CMD ["sh", "-c", "uvicorn pitwall.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
