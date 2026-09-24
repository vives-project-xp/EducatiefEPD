#!/bin/sh
set -eu

python - <<'PY'
import os
import time

import MySQLdb

for attempt in range(1, 31):
    try:
        connection = MySQLdb.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"],
            connect_timeout=3,
            charset="utf8mb4",
        )
        connection.close()
        break
    except MySQLdb.Error:
        if attempt == 30:
            raise
        time.sleep(2)
PY

python manage.py migrate --noinput
python manage.py initialize_platform
python manage.py collectstatic --noinput

if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo
fi

exec "$@"
