FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
ARG CONTEXTBRIDGE_WORKERS=false
RUN pip install --no-cache-dir uv==0.11.23 && \
    if [ "$CONTEXTBRIDGE_WORKERS" = "true" ]; then uv sync --frozen --no-dev --extra workers; \
    else uv sync --frozen --no-dev; fi
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH"
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "contextbridge.main:app", "--host", "0.0.0.0", "--port", "8000"]
