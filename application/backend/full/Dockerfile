FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8010

CMD [".venv/bin/uvicorn", "fastlang.server.server:app", "--host", "0.0.0.0", "--port", "8010"]
