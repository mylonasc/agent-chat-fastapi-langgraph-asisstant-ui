FROM python:3.11-slim

WORKDIR /app

COPY packages/agent-chat-minimal /app/packages/agent-chat-minimal
RUN pip install "/app/packages/agent-chat-minimal[persistence]"

COPY application/backend/langgraph-server-minimal /app/dev-server
WORKDIR /app/dev-server

EXPOSE 8011

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8011"]
