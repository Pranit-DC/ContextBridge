FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN pip install --no-cache-dir uv==0.11.23 && uv sync --frozen --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH"
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "contextbridge.main:app", "--host", "0.0.0.0", "--port", "8000"]
