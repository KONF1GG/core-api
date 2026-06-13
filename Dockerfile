FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/env

RUN uv sync --no-cache

CMD ["uv", "run", "main.py"]
