FROM python:3.11-slim
RUN groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --create-home appuser
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
RUN mkdir -p /home/appuser/.local/state/mcp-web-engine && chown -R appuser:appgroup /home/appuser/.local
USER appuser
ENV HOST=0.0.0.0 PORT=5050 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 5050
CMD ["mcp-web-engine", "--serve"]
