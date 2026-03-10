FROM edoburu/pgbouncer:latest

USER root
RUN apk add --no-cache curl jq bash
COPY scripts/bootstrap-secrets.sh /app/bootstrap-secrets.sh
COPY services/pgbouncer/entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh /app/bootstrap-secrets.sh
USER postgres

ENTRYPOINT ["/custom-entrypoint.sh"]
CMD ["/usr/bin/pgbouncer", "/etc/pgbouncer/pgbouncer.ini"]
