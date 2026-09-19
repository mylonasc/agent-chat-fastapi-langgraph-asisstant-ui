FROM python:3.11-slim

WORKDIR /app

COPY dist/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels

EXPOSE 8011

CMD ["minimal-chat-serve", "--host", "0.0.0.0", "--port", "8011"]
