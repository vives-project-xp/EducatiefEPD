FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN addgroup --system epd && adduser --system --ingroup epd epd

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=epd:epd . .
RUN mkdir -p /app/staticfiles && chown -R epd:epd /app && chmod +x /app/entrypoint.sh

USER epd
EXPOSE 8001
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8001", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
