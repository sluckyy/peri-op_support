# Deploying the demo to Azure

Deployed and running as of 2026-09-27. This session had an Azure
service-principal credential (`AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET`/
`AZURE_TENANT_ID`/`AZURE_SUBSCRIPTION_ID`) in its environment secrets and
ran the whole thing end-to-end with the Azure CLI. The sections below are
what actually happened plus what you need to redeploy or reproduce it.

**Live demo URL:**
`https://periop-support-demo.greenmushroom-6f4a2598.australiaeast.azurecontainerapps.io`

## What's provisioned (resource group `periop-support-rg`, `australiaeast`)

- `periop-support-pg` — Azure Database for PostgreSQL Flexible Server 16,
  Burstable `Standard_B1ms`, database `periop_core`.
- `periopsupportacr` — Azure Container Registry (Basic), images
  `periop-demo:latest` (the app) and `periop-migrator:latest` (one-shot
  migration runner, deleted after use — see below).
- `periop-support-env` — Container Apps environment (Consumption workload
  profile).
- `periop-support-demo` — the Container App itself, external ingress,
  target port 8000.

## Choices made differently from the original plan, and why

- **Postgres firewall: "allow Azure services only", not open to all
  IPs.** The original draft of this runbook used a
  `0.0.0.0-255.255.255.255` firewall rule for convenience. When this
  session tried to create the server that way, Claude Code's auto-mode
  security classifier blocked it as a security-weakening action. Asked
  directly, the user chose the Azure-services-only rule instead
  (`az postgres flexible-server firewall-rule create --name
  allowazureservices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0`
  — this specific IP pair is Azure's documented special case for "any
  Azure service," not a real IP). Practical effect: only Azure-hosted
  resources (Container Apps, Container Apps Jobs, etc.) can reach the
  server — nothing on the open internet, and not this Claude Code
  session's own sandbox either.
- **Migrations ran via a Container Apps Job, not Azure Container
  Instances (ACI) and not psql from an operator's machine.** Because of
  the firewall choice above, nothing outside Azure can open a direct
  psql connection to the server — including this sandbox itself. The
  original plan (`az container create`, i.e. ACI) failed because the
  `Microsoft.ContainerInstance` resource provider wasn't registered on
  the subscription, and the service principal doesn't hold subscription-
  level rights to register it (its role assignment is scoped to just
  this resource group). `Microsoft.App` (Container Apps) was already
  registered, so the fix was a disposable **Container Apps Job**
  instead: a `postgres:16-alpine` image with the two files under
  `db/migrations/` baked in and a `run.sh` that applies them in order
  with `psql -v ON_ERROR_STOP=1`, run once via `az containerapp job
  start`, then deleted. If you need to run migrations again (new
  migration file added), recreate that job the same way — see "Running a
  new migration" below.
- **`pgcrypto` had to be allow-listed before `0001_init.sql` would
  apply.** Azure Database for PostgreSQL requires extensions to be
  explicitly allow-listed via the `azure.extensions` server parameter
  before `CREATE EXTENSION` succeeds, even for extensions Azure itself
  supports. Fixed with:
  ```bash
  az postgres flexible-server parameter set \
    --resource-group periop-support-rg \
    --server-name periop-support-pg \
    --name azure.extensions \
    --value pgcrypto
  ```
  This takes effect immediately (no restart needed). If a future
  migration needs another extension, add it to the same
  comma-separated value rather than overwriting it.
- **Registry auth used a short-lived `az acr login --expose-token`
  token, not the ACR admin user.** The ACR admin user is a shared,
  long-lived credential Microsoft recommends leaving disabled (it stays
  disabled here: `adminUserEnabled: false`). Every `--registry-password`
  in the commands below is that token, valid for a few hours — regenerate
  it before reuse:
  ```bash
  az acr login --name periopsupportacr --expose-token --output tsv --query accessToken
  # username is always the literal string 00000000-0000-0000-0000-000000000000
  ```
- **The Dockerfile builds cleanly.** The version of this runbook written
  before Azure network access was available flagged the Dockerfile as
  never having been run through a real `docker build`. It has been now
  — both `az acr build` calls in this session (the app image and the
  migrator image) succeeded on the first pass with no changes needed.

## Redeploying after a code change

```bash
cd /path/to/repo
az acr build --registry periopsupportacr --image periop-demo:latest .
az containerapp update \
  --resource-group periop-support-rg \
  --name periop-support-demo \
  --image periopsupportacr.azurecr.io/periop-demo:latest
```

## Running a new migration

Whenever a new file lands under `db/migrations/`, rebuild and rerun the
migrator job (it isn't kept around between uses). The Dockerfile and
entrypoint script are checked in at `docs/ops/migrator/` — build from
the repo root:

```bash
ACR_TOKEN=$(az acr login --name periopsupportacr --expose-token --output tsv --query accessToken)

az acr build \
  --registry periopsupportacr \
  --image periop-migrator:latest \
  -f docs/ops/migrator/Dockerfile \
  .

az containerapp job create \
  --resource-group periop-support-rg \
  --name periop-migrator \
  --environment periop-support-env \
  --trigger-type Manual \
  --replica-timeout 300 --replica-retry-limit 0 \
  --replica-completion-count 1 --parallelism 1 \
  --image periopsupportacr.azurecr.io/periop-migrator:latest \
  --registry-server periopsupportacr.azurecr.io \
  --registry-username 00000000-0000-0000-0000-000000000000 \
  --registry-password "$ACR_TOKEN" \
  --secrets db-url="postgresql://periopadmin:<password>@periop-support-pg.postgres.database.azure.com:5432/periop_core?sslmode=require" \
  --env-vars PERIOP_DATABASE_URL=secretref:db-url \
  --cpu 0.5 --memory 1Gi
```

**Important:** there's no `schema_migrations` tracking table yet, so
`run.sh` doesn't know which files were already applied. Starting the job
with no arguments re-applies *every* file in `db/migrations/` in order —
correct the very first time (a fresh database), but it will fail on an
already-migrated database because `0001`/`0002` etc. try to
`CREATE TYPE`/`CREATE TABLE` things that already exist. For every
migration after the first, override the job's command to run only the
*new* file(s):

```bash
az containerapp job update \
  --resource-group periop-support-rg \
  --name periop-migrator \
  --command "/run.sh" \
  --args "000X_new_migration.sql"   # just the new filename(s), space-separated

az containerapp job start --resource-group periop-support-rg --name periop-migrator
# poll: az containerapp job execution list -g periop-support-rg -n periop-migrator -o table
# logs: az containerapp job logs show -g periop-support-rg -n periop-migrator --container periop-migrator --tail 200

az containerapp job delete --resource-group periop-support-rg --name periop-migrator --yes
```

(`--command ""` does *not* clear the override back to the image's own
entrypoint the way you'd expect — it sets the command to a literal empty
string, which just hangs. Always pass `--command "/run.sh"` explicitly.)

## Notes / things worth knowing before you rely on this

- The admin password for `periopadmin` is not recorded in this repo or
  in chat — it was generated and used only within the session that
  provisioned the server. If you don't have it, reset it with `az
  postgres flexible-server update --resource-group periop-support-rg
  --name periop-support-pg --admin-password <new password>`.
- The `az` CLI's own status-polling requests to `management.azure.com`
  occasionally hit a transient `Connection reset by peer` from this
  sandbox's egress proxy partway through a long-running create (Postgres
  server, Container Apps environment/job/app). In every case the
  operation had actually gone through server-side — checking the
  resource with a plain `show` command after the "failure" confirmed it
  existed. Don't take that error at face value; check before retrying,
  since retrying a `create` that already succeeded is usually harmless
  but wasteful, and retrying a `start` on a job can enqueue a duplicate
  execution.
- Azure Database for PostgreSQL Flexible Server extensions must be
  allow-listed via `azure.extensions` before `CREATE EXTENSION` works,
  even for extensions in Azure's own supported list (see above).
- This deploys the demo API + UI only. It does **not** touch the pending
  Azure Postgres data-residency/jurisdiction questions from earlier, and
  it is still the same demo scope as the README describes — an LLM-backed
  interviewer (see below), but no orchestrator or FHIR layer.

## Enabling the voice interviewer

The interviewer calls the Claude API. Without a key it fails closed: the
"Talk to the pre-op assistant" panel says it's unavailable and the
manual form opens instead. No database migration is needed — it uses the
`interview_action` and `turn` tables from `0001`.

1. Create a key at console.anthropic.com (Settings → API keys) and add
   billing credit.
2. Store it as a secret on the Container App and point an env var at it
   (single quotes, and `set +H` first if the key contains `!`):

   ```bash
   az containerapp secret set \
     --resource-group periop-support-rg --name periop-support-demo \
     --secrets anthropic-api-key='<your key>'

   az containerapp update \
     --resource-group periop-support-rg --name periop-support-demo \
     --set-env-vars ANTHROPIC_API_KEY=secretref:anthropic-api-key \
     --revision-suffix llm$(date +%s)
   ```

   A Container App doesn't pick up a changed secret until a new revision
   starts, which the `--revision-suffix` forces.
3. Optional: `PERIOP_LLM_MODEL` (default `claude-opus-5-5`) switches the
   model without a code change, e.g. `--set-env-vars
   PERIOP_LLM_MODEL=claude-sonnet-5-5`.

Voice input works in Chrome and Edge (the page is served over HTTPS, which
browsers require for the microphone). Browser speech recognition sends
audio to the browser vendor — demo data only.
- The Azure-services-only firewall rule means nobody can `psql` in
  directly, including from a laptop or Azure Cloud Shell. If you need
  ad-hoc query access, either add a firewall rule scoped to your own
  current IP (`az postgres flexible-server firewall-rule create
  --name my-ip --start-ip-address <ip> --end-ip-address <ip>`, and
  remove it again afterward) or spin up a throwaway psql-capable job the
  same way the migrator above does.
