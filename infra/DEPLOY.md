# Deploy runbook (one-time Azure setup)

Everything here needs **your** Azure account and **spends money** (Postgres B1ms ≈ the main cost;
Container Apps scale to zero; ACR Basic + Log Analytics are cheap). Claude wrote all the code
(`infra/main.bicep`, the CD workflow); these are the human-only steps. Run top to bottom once.

Prereqs: `az` CLI, `gh` CLI (logged in to the repo), Docker running locally (for the one-time
ingest you can skip Docker — ingest runs from your host against Azure Postgres), the corpus present
(`uv run python scripts/fetch_corpus.py`), and `.env` with a working `ANTHROPIC_API_KEY`.

Commands are single-line so they paste into PowerShell or bash. Where a value is captured into a
shell variable, PowerShell uses `$RG="..."` and bash uses `RG="..."`; substitute your own style.

---

## 0. Pick your names

- `RG` = resource group, e.g. `ruleslawyer-rg`
- `LOCATION` = region, e.g. `eastus`
- `PREFIX` = `ruleslawyer` (the Bicep derives every resource name from this)
- Derived: ACR = `ruleslawyeracr`, api app = `ruleslawyer-api`, ui app = `ruleslawyer-ui`

## 1. Log in and create the resource group

```
az login
az account set --subscription "<your-subscription-id>"
az group create --name ruleslawyer-rg --location eastus
```

## 2. Deploy the infrastructure

Dry-run first (`what-if` creates nothing — it validates the Bicep and shows the plan):

```
az deployment group what-if -g ruleslawyer-rg -f infra/main.bicep -p postgresAdminPassword="<STRONG-PW>" anthropicApiKey="<ANTHROPIC-KEY>"
```

Then create for real:

```
az deployment group create -g ruleslawyer-rg -f infra/main.bicep -p postgresAdminPassword="<STRONG-PW>" anthropicApiKey="<ANTHROPIC-KEY>"
```

Grab the outputs (ACR name, app FQDNs, Postgres FQDN):

```
az deployment group show -g ruleslawyer-rg -n main --query properties.outputs
```

## 3. One-time corpus load into Azure Postgres

Open the firewall to your current IP, apply the schema, then ingest ~5.5k chunks:

```
az postgres flexible-server firewall-rule create -g ruleslawyer-rg -n ruleslawyer-pg --rule-name myip --start-ip-address <YOUR-IP> --end-ip-address <YOUR-IP>
```

Point `DATABASE_URL` at Azure (note `sslmode=require`) — PowerShell:

```
$env:DATABASE_URL="postgresql://ruleslawyer:<STRONG-PW>@ruleslawyer-pg.postgres.database.azure.com:5432/ruleslawyer?sslmode=require"
```

bash:

```
export DATABASE_URL="postgresql://ruleslawyer:<STRONG-PW>@ruleslawyer-pg.postgres.database.azure.com:5432/ruleslawyer?sslmode=require"
```

Then:

```
uv run python scripts/apply_schema.py
uv run python scripts/ingest.py
```

(Optionally delete the firewall rule afterwards; the container apps reach Postgres via the
`AllowAzureServices` rule the Bicep created, not your IP.)

## 4. GitHub OIDC → Azure (no stored cloud keys)

Create an app registration + service principal, add a federated credential for pushes to `main`:

```
az ad app create --display-name ruleslawyer-github-oidc
```

Capture the app id (bash shown; in PowerShell assign to `$APP_ID`):

```
APP_ID=$(az ad app list --display-name ruleslawyer-github-oidc --query "[0].appId" -o tsv)
az ad sp create --id $APP_ID
```

Add the federated credential (bash — for PowerShell put the JSON in a file and pass `@file`):

```
az ad app federated-credential create --id $APP_ID --parameters '{"name":"gh-main","issuer":"https://token.actions.githubusercontent.com","subject":"repo:nwisken/rag-dnd-rules-lawyer:ref:refs/heads/main","audiences":["api://AzureADTokenExchange"]}'
```

Grant it deploy rights (Contributor on the RG) and image-push rights (AcrPush on the ACR):

```
SUB=$(az account show --query id -o tsv)
az role assignment create --assignee $APP_ID --role Contributor --scope /subscriptions/$SUB/resourceGroups/ruleslawyer-rg
az role assignment create --assignee $APP_ID --role AcrPush --scope /subscriptions/$SUB/resourceGroups/ruleslawyer-rg/providers/Microsoft.ContainerRegistry/registries/ruleslawyeracr
```

## 5. Repo secrets and variables

Secrets (sensitive) and variables (names) the workflows read:

```
gh secret set AZURE_CLIENT_ID -b "$APP_ID"
gh secret set AZURE_TENANT_ID -b "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID -b "$SUB"
gh secret set ANTHROPIC_API_KEY -b "<ANTHROPIC-KEY>"
gh variable set AZURE_RESOURCE_GROUP -b "ruleslawyer-rg"
gh variable set ACR_NAME -b "ruleslawyeracr"
gh variable set API_APP_NAME -b "ruleslawyer-api"
gh variable set UI_APP_NAME -b "ruleslawyer-ui"
```

## 6. First deploy

Push to `main` (or re-run the **Deploy** workflow). It builds both images in ACR and rolls the
apps onto the new tag. Watch it in the Actions tab.

## 7. Verify

```
az containerapp show -g ruleslawyer-rg -n ruleslawyer-ui --query properties.configuration.ingress.fqdn -o tsv
```

Open `https://<that-fqdn>` — the Streamlit UI. First hit after idle pays a scale-from-zero cold
start (~15–30 s: container start + model load); subsequent requests are fast. Telemetry lands in
Application Insights (`ruleslawyer-insights`); per-query rows land in the `query_log` table.

## Teardown (stop all spend)

```
az group delete --name ruleslawyer-rg --yes --no-wait
```
