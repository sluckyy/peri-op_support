# Build from the repo root: az acr build --registry <acr> --image periop-migrator:latest -f docs/ops/migrator/Dockerfile .
FROM postgres:16-alpine
COPY db/migrations/*.sql /migrations/
COPY docs/ops/migrator/run.sh /run.sh
RUN chmod +x /run.sh
ENTRYPOINT ["/run.sh"]
