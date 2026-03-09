FROM python:3.11-slim

ARG DOCLING_VARIANT=none

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN uv pip install --python .venv/bin/python pypdf docx2txt
RUN if [ "$DOCLING_VARIANT" = "cpu" ]; then uv pip install --python .venv/bin/python docling; fi
RUN if [ "$DOCLING_VARIANT" = "gpu" ]; then uv pip install --python .venv/bin/python docling onnxruntime-gpu; fi

COPY . .

EXPOSE 8010

CMD [".venv/bin/uvicorn", "fastlang.server.server:app", "--host", "0.0.0.0", "--port", "8010"]
