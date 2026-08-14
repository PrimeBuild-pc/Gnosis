FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('intfloat/multilingual-e5-small')"

COPY migrations ./migrations
COPY config ./config

RUN useradd --create-home --uid 10001 gnosis && mkdir -p /data/telegram && \
    chown -R gnosis:gnosis /app /data /tmp/fastembed_cache
USER gnosis

CMD ["gnosis", "web"]
