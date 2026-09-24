#!/bin/sh
set -eu

echo "Waiting for MySQL at ${MYSQL_HOST:-db}:${MYSQL_PORT:-3306}..."
until nc -z "${MYSQL_HOST:-db}" "${MYSQL_PORT:-3306}"; do
  sleep 1
done

python manage.py migrate --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
