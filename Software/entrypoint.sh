#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py initialize_platform
python manage.py collectstatic --noinput

if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo
fi

exec "$@"
