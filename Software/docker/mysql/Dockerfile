FROM mysql:8.4

COPY docker/mysql/init-test-database.sh /docker-entrypoint-initdb.d/10-test-database.sh
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/10-test-database.sh \
    && chmod +x /docker-entrypoint-initdb.d/10-test-database.sh
