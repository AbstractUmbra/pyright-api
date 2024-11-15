FROM python:3.12-slim

LABEL org.opencontainers.image.source=https://github.com/abstractumbra/pyright-api
LABEL org.opencontainers.image.description="An API for running Pyright output"
LABEL org.opencontainers.image.licenses=MIT

ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

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
    git \
    # deps for building python deps
    build-essential \
    libcurl4-gnutls-dev \
    gnutls-dev \
    libmagic-dev \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g pyright@latest

RUN curl -sSL https://install.python-poetry.org | python -
# copy project requirement files here to ensure they will be cached.
WORKDIR /app
COPY poetry.lock pyproject.toml ./

ENV API_TOKEN=${API_TOKEN}

# install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
RUN poetry install --only main

COPY . /app/

EXPOSE 8130

ENTRYPOINT ["poetry", "run", "python", "-O", "run.py"]
