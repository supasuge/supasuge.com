FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    bash \
    openssh-client \
    libmagic1 \
  && rm -rf /var/lib/apt/lists/*
RUN chmod 1777 /tmp
WORKDIR /app
RUN groupadd -g 10001 appuser && useradd -u 10001 -g 10001 -m -s /usr/sbin/nologin appuser
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-editable
COPY --chown=10001:10001 . /app
RUN mkdir -p /app/instance && chown appuser:appuser /app/instance
RUN chmod -R 755 templates blueprints static && \
 chown -R appuser:appuser templates static && \
 find templates -type f -exec chmod 644 {} \; && \
 chmod +x /app/entrypoint.sh
USER 10001:10001
EXPOSE 8000
ENV PYTHONPATH=/app
HEALTHCHECK --interval=60s --timeout=5s --retries=3 --start-period=60s CMD \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/entrypoint.sh"]