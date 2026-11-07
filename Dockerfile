FROM ghcr.io/astral-sh/uv:0.11.15 AS uv
FROM python:3.11-slim
COPY --from=uv /uv /usr/local/bin/uv
RUN groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --create-home appuser
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
# Validate metadata against the lock; install only hashed runtime dependencies.
RUN uv export --locked --no-dev --no-emit-project --output-file /app/runtime-requirements.txt \
    && pip install --no-cache-dir --require-hashes -r /app/runtime-requirements.txt \
    && pip install --no-cache-dir . --no-deps
RUN mkdir -p /home/appuser/.local/state/mcp-web-engine && chown -R appuser:appgroup /home/appuser/.local
USER appuser
ENV HOST=0.0.0.0 PORT=5050 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 5050
CMD ["mcp-web-engine", "--serve"]
