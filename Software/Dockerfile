FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system epd \
    && adduser --system --ingroup epd epd

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY --chown=epd:epd . .
RUN mkdir -p /app/staticfiles && chown -R epd:epd /app && chmod +x /app/entrypoint.sh

USER epd
EXPOSE 8001
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8001", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
