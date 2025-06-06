ARG PYTHON_BASE=3.13-slim-bookworm
ARG UV_BASE=python3.13-bookworm-slim

FROM ghcr.io/astral-sh/uv:${UV_BASE} AS builder

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /project

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=/project/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/project/uv.lock \
    uv sync --frozen --no-install-project --no-dev

ADD --chown=1000:1000 . /project

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

FROM python:${PYTHON_BASE}

LABEL org.opencontainers.image.source=https://github.com/abstractumbra/pyright-api
LABEL org.opencontainers.image.description="An API for running Pyright output"
LABEL org.opencontainers.image.licenses=MIT

RUN mkdir -p /etc/apt/keyrings \
    && apt update -y \
    && apt-get install --no-install-recommends -y \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_23.x -o nodesource_setup.sh \
    && bash nodesource_setup.sh \
    && apt update -y \
    && apt-get install --no-install-recommends -y \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g pyright@latest

USER 1000:1000

WORKDIR /app

COPY --from=builder --chown=1000:1000 /project /app
ENV PATH="/app/.venv/bin:$PATH"

CMD [ "python", "-O", "run.py" ]
