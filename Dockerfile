# =============================================================================
# Backend image — Django + DRF + Celery
# =============================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=Taghzieh.settings

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        util-linux && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r app && \
    useradd -r -g app -d /app -s /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --default-timeout=120 -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /app/data /app/staticfiles /app/media && \
    chown -R app:app /app

EXPOSE 8000

ENV RUN_ROLE=web

ENTRYPOINT ["/app/entrypoint.sh"]

# pid/control files go under /tmp so non-root runtime never writes into /app.
CMD ["gunicorn", "Taghzieh.asgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--pid", "/tmp/gunicorn.pid", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
