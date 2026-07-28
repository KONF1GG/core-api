FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

ENV UV_PROJECT_ENVIRONMENT=/env

RUN uv sync --frozen --no-dev

COPY . /app

ENV PATH="/env/bin:$PATH"

CMD ["uvicorn", "agent_service.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
