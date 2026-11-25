FROM python:3.15.1-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never

ADD pyproject.toml uv.lock /src/
ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src && uv sync --frozen --no-dev --no-editable --package code-coverage-bot
ENV PATH="/src/.venv/bin:$PATH"

CMD ["code-coverage-bot"]
