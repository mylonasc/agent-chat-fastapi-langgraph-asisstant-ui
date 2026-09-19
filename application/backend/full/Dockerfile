FROM python:3.11-slim

ARG DOCLING_VARIANT=none

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN if [ "$DOCLING_VARIANT" = "cpu" ]; then uv sync --frozen --no-dev --extra docling-cpu; fi
RUN if [ "$DOCLING_VARIANT" = "gpu" ]; then uv sync --frozen --no-dev --extra docling-gpu; fi

COPY . .

EXPOSE 8010

CMD [".venv/bin/uvicorn", "fastlang.server.server:app", "--host", "0.0.0.0", "--port", "8010"]
