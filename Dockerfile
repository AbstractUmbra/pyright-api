ARG PYTHON_BASE=3.12-slim

FROM python:${PYTHON_BASE} AS builder

# disable update check since we're "static" in an image
ENV PDM_CHECK_UPDATE=false
# install PDM
RUN pip install -U pdm

WORKDIR /project
COPY . /project/
RUN apt-get update -y \
    && apt-get install --no-install-recommends --no-install-suggests -y git \
    && rm -rf /var/lib/apt/lists/*

RUN pdm install --check --prod --no-editable

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

WORKDIR /app
COPY --from=builder /project/.venv/ /app/.venv/
ENV PATH="/app/.venv/bin:$PATH"
COPY . /app/

CMD [ "python", "-O", "run.py" ]
