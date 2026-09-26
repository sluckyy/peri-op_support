# Multi-stage build: Vue frontend, then a Python runtime that serves both
# the built static assets and the FastAPI demo API from one container --
# minimising the number of Azure resources needed for the demo (one
# Container App / App Service instead of a separate static site + API).

FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY docs/exports/clinical_dataset_v1.0.csv docs/exports/clinical_dataset_v1.0.csv
COPY docs/exports/source_authority_matrix.csv docs/exports/source_authority_matrix.csv
# Editable install: periop_core.dataset/.source_authority resolve their
# CSV paths relative to the package source tree (REPO_ROOT = three parents
# up from src/periop_core/*.py) -- a non-editable install would copy the
# package into site-packages and break that path assumption. See those
# modules' REPO_ROOT computation before changing this to `pip install .`.
RUN pip install --no-cache-dir -e .

COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
ENV PERIOP_FRONTEND_DIST=/app/frontend/dist

# PERIOP_DATABASE_URL must be provided at runtime (e.g. an Azure Container
# Apps secret/env var pointing at Azure Database for PostgreSQL) -- there
# is deliberately no default pointing at a real database baked into the
# image.
EXPOSE 8000
CMD ["uvicorn", "periop_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
