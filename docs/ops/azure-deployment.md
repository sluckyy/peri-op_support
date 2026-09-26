# Deploying the demo to Azure

This is a runbook for you to run, not something this Claude Code session
can execute itself — there's no Azure CLI or connected Azure credential in
this sandbox (checked: no `az` binary, no connected Azure connector). If
you'd rather I ran these myself in a future session, see "Letting Claude
run this directly" at the bottom.

Uses `az acr build` throughout, which builds the container image in Azure
— you don't need Docker installed locally either.

## Prerequisites

- The Azure Database for PostgreSQL Flexible Server from the earlier step
  (`periop-support-pg`, database `periop_core`), reachable via public
  access (the dev/test-only `0.0.0.0-255.255.255.255` firewall rule).
- `az login` done, subscription set.

## 1. Apply the database migrations

Do this once, before first use, and again whenever a new migration file
is added (they're numbered and safe to (re-)apply in order — each only
creates its own new tables/types). From your machine (needs `psql`, or
use [Azure Cloud Shell](https://shell.azure.com) which has it
preinstalled):

```bash
for f in db/migrations/*.sql; do
  psql "host=periop-support-pg.postgres.database.azure.com \
        port=5432 dbname=periop_core user=periopadmin sslmode=require" \
       -f "$f"
done
```

You'll be prompted for the admin password you set when creating the
server.

## 2. Container registry + build the image

```bash
az acr create \
  --resource-group periop-support-rg \
  --name periopsupportacr \
  --sku Basic

# Builds db/migrations/../Dockerfile in Azure -- run from the repo root.
az acr build \
  --registry periopsupportacr \
  --image periop-demo:latest \
  .
```

## 3. Container Apps environment + the app itself

```bash
az extension add --name containerapp --upgrade

az containerapp env create \
  --resource-group periop-support-rg \
  --name periop-support-env \
  --location australiaeast

# The connection string is a secret, never passed as a plain --env-vars
# value. Build it from the same admin credentials used in step 1.
az containerapp create \
  --resource-group periop-support-rg \
  --name periop-support-demo \
  --environment periop-support-env \
  --image periopsupportacr.azurecr.io/periop-demo:latest \
  --registry-server periopsupportacr.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --secrets db-url="postgresql://periopadmin:<password>@periop-support-pg.postgres.database.azure.com:5432/periop_core?sslmode=require" \
  --env-vars PERIOP_DATABASE_URL=secretref:db-url
```

`az containerapp create` prints the app's public FQDN when it finishes —
that's the demo URL.

## 4. Redeploying after a code change

```bash
az acr build --registry periopsupportacr --image periop-demo:latest .
az containerapp update \
  --resource-group periop-support-rg \
  --name periop-support-demo \
  --image periopsupportacr.azurecr.io/periop-demo:latest
```

## Notes / things worth knowing before you rely on this

- **The Dockerfile itself has not been run through an actual `docker
  build`** in the session that wrote it (no Docker daemon available
  there). Its *runtime* logic (editable install path resolution, static
  file serving) was validated by simulation — see the repo README. `az
  acr build` in step 2 is the first time the Dockerfile's actual syntax
  gets exercised for real. If it fails, that's new information, not a
  regression of something previously working.
- The `0.0.0.0-255.255.255.255` Postgres firewall rule from the earlier
  setup is fine for this demo (Container Apps reaches it over the public
  internet with SSL enforced) but is not a production posture — tighten it
  (VNet integration, private endpoint, or at minimum "Allow public access
  from Azure services only") before anything beyond throwaway testing.
- This deploys the demo API + UI only. It does **not** touch the pending
  Azure Postgres data-residency/jurisdiction questions from earlier, and
  it is still the same demo scope as the README describes — no LLM,
  orchestrator, or FHIR layer.

## Letting Claude run this directly instead

If you'd rather a future session ran these `az` commands itself rather
than you copy-pasting them: add an Azure service-principal credential (or
an `az login` token) as an environment secret in this Claude Code
environment's settings (cloud environment menu → Edit → environment
variables/API credentials), then ask in a new session. That session would
install the Azure CLI, authenticate with the stored credential, and run
the deployment end-to-end rather than handing you a runbook. Never paste
the credential itself into chat.
