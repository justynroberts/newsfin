# NewsFin - API + prebuilt Flutter web PWA in one image.
#
# The Flutter web bundle is built on the developer machine and committed to
# server/static, rather than compiled here. Building Flutter in Docker means
# pulling a ~2.5GB SDK image on every deploy for a bundle that changes far less
# often than the server does; `make web` regenerates it.

FROM python:3.12-slim

# curl is not optional: Coolify's healthcheck shells out to curl or wget, and
# python:*-slim ships neither. Without it the healthcheck can only fail, and
# the deploy is rolled back while the app is serving perfectly.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so an application-only change reuses the layer.
COPY server/pyproject.toml /app/pyproject.toml
COPY server/newsfin /app/newsfin
RUN pip install --no-cache-dir .

COPY server/static /app/static

ENV NEWSFIN_DB=/data/newsfin.db \
    NEWSFIN_STATIC=/app/static \
    NEWSFIN_FAST_MINUTES=3 \
    NEWSFIN_FULL_MINUTES=12 \
    PYTHONUNBUFFERED=1

# SQLite lives on a persistent volume; losing it costs the corroboration
# history that the ranking is built on.
VOLUME ["/data"]

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8099/healthz || exit 1

# Single worker on purpose: one process owns the SQLite file and runs the
# APScheduler poll loop. Concurrency comes from asyncio, not from forking.
CMD ["uvicorn", "newsfin.api:app", "--host", "0.0.0.0", "--port", "8099", "--workers", "1"]
