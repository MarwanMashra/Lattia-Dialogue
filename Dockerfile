FROM        python:3.13-slim-bookworm AS base
COPY        --from=ghcr.io/astral-sh/uv:0.8.12 /uv /uvx /bin/

ENV         PYTHONUNBUFFERED=1 \
            PYTHONDONTWRITEBYTECODE=1 \
            PATH="/usr/app/.venv/bin:$PATH" \
            UV_PROJECT_ENVIRONMENT=/usr/app/.venv \
            UV_COMPILE_BYTECODE=1 \
            UV_LINK_MODE=copy \
            PYTHONWARNINGS="ignore::SyntaxWarning"


RUN         apt-get update && \
            apt-get install -y \
            build-essential libpq-dev \
            --no-install-recommends && \
            rm -rf /var/lib/apt/lists/*


RUN         --mount=type=cache,target=/root/.cache/uv \
            --mount=type=bind,source=uv.lock,target=uv.lock \
            --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
            uv sync --locked --no-install-project --group dev --group test

WORKDIR     /usr/app/src

COPY         ./src ./

EXPOSE      8000

CMD         ["uvicorn", "lattia.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
