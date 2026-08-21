# CI/CD — how a change gets from a branch to Azure

```
branch ──PR──▶  CI (backend + frontend)  ──green──▶  automerge (label-gated)
                                                          │ squash merge
                                                          ▼
                                                    main ──▶ deploy ──▶ Azure App Service (x2)
                                                                          │
                                                              health check + Kudu VFS content check
```

Three workflows in `.github/workflows/`: `ci.yml`, `automerge.yml`,
`deploy.yml`. No marketplace actions beyond first-party `actions/*` and
`azure/login` — everything else is plain shell/Python.

---

## 1. `ci.yml` — the pull-request gate

`on: pull_request`, every branch. Two independent jobs:

- **backend** — ubuntu-latest, Python 3.11 (matches the App Service's
  `PYTHON|3.11` runtime). Installs `unixodbc-dev` first (pyodbc has no
  manylinux wheel and builds from source on Linux), then
  `pip install -r backend/requirements.txt -r backend/requirements-dev.txt`,
  then `ruff check backend`, `python -m compileall backend/app backend/main.py`,
  then `pytest backend/tests -q`.
- **frontend** — ubuntu-latest, Node 20. `npm ci`, `npm run build` (`vite
  build`), then a **stub gate**: `dist/index.html` must exist, be >500 bytes,
  and reference an `assets/index-*.js` bundle that's actually there and
  >100 KB. This exists because a 55-byte placeholder `index.html` once
  shipped as a real build in a sibling project.

**`tsc --noEmit` is deliberately not run.** As of this workflow being
written there are 76 pre-existing TypeScript errors across 23 files (mostly
TanStack Query v4→v5 fallout). The re-enable snippet is commented directly
in `ci.yml`:

```yaml
#   - name: tsc --noEmit
#     run: npx tsc --noEmit
```

Uncomment it (and ideally flip the `build` script to `tsc && vite build`)
once those errors are cleaned up.

The workflow's **name** — `CI` — is load-bearing: `automerge.yml` triggers on
a `workflow_run` of a workflow named exactly that. Renaming it silently
disables auto-merge.

## 2. `automerge.yml` — the label contract

`on: workflow_run` for `CI`, `types: [completed]`. When CI concluded
`success`, it finds every open PR at that commit and squash-merges each one
that is **all** of:

- open (not draft, not closed),
- labelled **`automerge`**,
- from a branch in this repo, not a fork,
- still at the SHA CI ran on (no new commits since),
- not reporting a merge conflict.

Every skip is logged with its reason in the workflow run. Merging uses the
built-in `GITHUB_TOKEN` — no PAT.

Because a push made with `GITHUB_TOKEN` does **not** trigger another
workflow's `on: push` (GitHub suppresses that to stop recursion), the squash
merge here would never fire `deploy.yml` on its own. `automerge.yml`
therefore explicitly dispatches it afterward:
`actions.createWorkflowDispatch({ workflow_id: 'deploy.yml', ref: 'main' })`
— `workflow_dispatch` is the one trigger `GITHUB_TOKEN` is allowed to start.
A merge done by hand in the GitHub UI is an ordinary push and fires
`deploy.yml`'s `on: push` on its own; the two paths never double-deploy
because only one of them happens for a given merge.

**One-time setup:** create the label once —
Settings → Issues → Labels → New label → name it exactly `automerge`.

## 3. `deploy.yml` — main to Azure

`on: push` to `main`, plus `workflow_dispatch` for manual runs. Concurrency
group `deploy-slppro` so two deploys never overlap.

SLP Pro is **two Azure App Services** in resource group `hortonfam`,
deployed independently and in parallel — a frontend-only change still
redeploys the backend and vice versa, because shipping `main` means shipping
all of `main`:

| service | app name | runtime | host |
| --- | --- | --- | --- |
| backend | `slppro-api` | `PYTHON\|3.11`, gunicorn + uvicorn workers | `slppro-api-a7caazgxa2gcaaaz.eastus2-01.azurewebsites.net` |
| frontend | `slppro` | `NODE\|20-lts`, `pm2 serve --spa` | `slppro-dbgmguexhmd5h3fh.eastus2-01.azurewebsites.net` |

**Backend job:** zip `backend/` with `main.py` at the zip root (excludes
`venv/`, `__pycache__/`, `*.db`, `.env*`, `tests/`), a gate that asserts no
backslash path entries and that `main.py` / `requirements.txt` / `app/` are
present, `azure/login` (OIDC), `az webapp deployment source config-zip`, then
poll `GET /api/health/live` until `200 {"live": true}` (up to ~5 min — this
never touches the database, so a paused Azure SQL serverless tier can't fail
it), then check `GET /` returns `{"status": "ok"}`. `GET /api/health/ready`
is reported but never gates the deploy — a cold serverless database is not a
bad deploy.

**Frontend job:** fresh `npm ci && npm run build`, the same stub gate as CI,
zip the **contents** of `dist/` (not the directory — `pm2 serve` treats
`wwwroot` as the document root), a gate against backslash entries and a
nested `dist/`, `azure/login`, `az webapp deployment source config-zip`. Then
a content check via **Kudu's VFS API** (`GET
https://<scm-host>/api/vfs/site/wwwroot/...`, authenticated with the same ARM
token `azure/login` already obtained) confirming the deployed
`index.html`'s referenced bundle actually exists on disk and is >100 KB.

**Kudu VFS as the content check, `GET /` as the liveness check.** History:
`slppro` originally had App Service Authentication (Easy Auth) enabled, which
answered anonymous requests with a bare `401` — that's why the workflow
verifies build contents through Kudu VFS instead of scraping `/`. Easy Auth
was removed on 2026-08-20 (it was redundant — the SPA does its own MSAL
sign-in, and its client secret had silently expired, breaking logins), so an
anonymous `GET /` now returns `200` with the real shell, matching the
RamHuddle setup. `deploy.yml` still accepts `200`/`401`/`302` as liveness so
it works under either configuration; only a timeout, `502`/`503`, or a
connection failure fails the job.

### No secrets — OIDC federated identity

`azure/login@v2` uses **OIDC**: the workflow requests a short-lived GitHub
ID token (`permissions: id-token: write`) and exchanges it for an Azure
token. The three inputs are repository **variables**, not secrets — none of
them is one:

| variable | what it is |
| --- | --- |
| `AZURE_CLIENT_ID` | the Entra app registration (or managed identity) federated to this repo |
| `AZURE_TENANT_ID` | `6481be4b-701d-41fe-8371-91c69d38228c` |
| `AZURE_SUBSCRIPTION_ID` | `20f7f847-ae85-4cfa-820e-647ac5d998dd` |

There is no client secret anywhere in this repository, and nothing to
rotate. Deleting the federated credential on the Azure side is how you
revoke the pipeline's access entirely.

---

## One-time Azure OIDC setup

Do this once, before the first deploy run. Requires Owner or User Access
Administrator on the `hortonfam` resource group (or Contributor + a
separate role assignment step by someone who has it).

**1. Create the app registration:**

```bash
az ad app create --display-name "slp-deploy-github" \
  --query "{appId:appId, id:id}" -o json
# note appId (this is AZURE_CLIENT_ID) and id (the object id, needed below)
```

Create a service principal for it:

```bash
az ad sp create --id <appId>
```

**2. Add the federated credential**, scoped to `main` pushes on this exact
repo:

```bash
az ad app federated-credential create --id <appId> --parameters '{
  "name": "slp-main-branch",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:hortonFam25/slp:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

**3. Grant Contributor on both App Services** (covers zip deploy via `az
webapp deployment source config-zip` and the frontend job's Kudu VFS read):

```bash
SUB=20f7f847-ae85-4cfa-820e-647ac5d998dd
RG=hortonfam

az role assignment create --assignee <appId> --role Contributor \
  --scope "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Web/sites/slppro-api"

az role assignment create --assignee <appId> --role Contributor \
  --scope "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Web/sites/slppro"
```

**4. Set the three GitHub repo variables** (Settings → Secrets and
variables → Actions → **Variables** tab — not Secrets):

```bash
gh variable set AZURE_CLIENT_ID --body "<appId>"
gh variable set AZURE_TENANT_ID --body "6481be4b-701d-41fe-8371-91c69d38228c"
gh variable set AZURE_SUBSCRIPTION_ID --body "20f7f847-ae85-4cfa-820e-647ac5d998dd"
```

Or via the UI: **Settings → Secrets and variables → Actions → Variables →
New repository variable**, one for each of the three above.

**5. GitHub repo settings, both one-time:**

- **Settings → Actions → General → Workflow permissions** → set to
  **"Read and write permissions"**. `automerge.yml` needs `contents: write`
  and `pull-requests: write` to squash-merge, and `actions: write` to
  dispatch `deploy.yml`.
- **Settings → Issues → Labels → New label** → create a label named exactly
  `automerge` (used by `automerge.yml`; see above).

## The normal flow

1. Branch off `main`, commit, open a PR.
2. `ci.yml` runs automatically (`backend` + `frontend` jobs).
3. Once CI is green, add the `automerge` label to the PR (any time — before
   or after CI finishes; the label just has to be present when CI
   completes).
4. `automerge.yml` squash-merges it and dispatches `deploy.yml`.
5. `deploy.yml` builds and ships both App Services in parallel, then
   verifies each.

To skip auto-merge, just don't add the label — merge by hand from the GitHub
UI when ready. A manual merge fires `deploy.yml` on its own via `on: push`.

## Manual deploy

`deploy.yml` also runs on `workflow_dispatch`. From the GitHub UI: **Actions
→ deploy → Run workflow → main**. Or via `gh`:

```bash
gh workflow run deploy.yml --ref main
```

Useful for re-shipping `main` without a new commit — e.g. after fixing an
App Service setting rather than code.

## Troubleshooting

- **First CI run fails installing `pyodbc`.** `pyodbc` has no Linux wheel
  and compiles from source, which needs the unixODBC headers. `ci.yml`
  installs `unixodbc-dev` via `apt-get` before `pip install` specifically
  for this — if a fresh runner image is missing something else `pyodbc`
  needs, the error will be a compiler/linker failure during that `pip
  install` step, not an import error later.
- **`slppro` (frontend) returns 401 on `GET /`.** As of 2026-08-20 this is
  NOT expected anymore: Easy Auth was removed from that App Service (the SPA
  authenticates via MSAL; the API verifies tokens). Anonymous `GET /` should
  return `200` with the app shell. If you see `401` again, someone has
  re-enabled App Service Authentication — check the portal's Authentication
  blade. A genuine outage shows up as a timeout or `502`/`503`.
- **`tsc --noEmit` isn't part of CI.** This is intentional (see above), not
  a gap someone forgot — don't add it back without first working through
  the 76 existing errors, or every PR will go red on day one.
- **Deploy job fails at "Azure login".** Almost always the OIDC setup above
  wasn't completed, or the federated credential's `subject` doesn't match
  `repo:hortonFam25/slp:ref:refs/heads/main` exactly (wrong repo name,
  wrong branch, or `pull_request` instead of `ref:refs/heads/main`). Re-check
  step 2 above.
- **Deploy job fails at the Kudu VFS check specifically.** The identity has
  Contributor on the App Service but the SCM/Kudu endpoint hasn't warmed up
  yet, or the deploy genuinely didn't write the expected bundle. The step
  retries for several minutes before failing — a persistent failure past
  that means the zip's contents (check the "Gate — the zip is laid out the
  way pm2 serve expects" step's log) don't match what's expected.

## Suggested cleanup (not yet done)

`deploy_temp/` and `deploy_frontend_temp/` are committed to this repo and
appear to be stale local artifacts from an earlier deploy method — they're
unrelated to the zip-deploy pipeline `deploy.yml` uses today, which builds
fresh from `backend/` and `frontend/` on every run. Recommended, but not
performed as part of this documentation change:

```bash
git rm -r --cached deploy_temp deploy_frontend_temp
```

...then add `deploy_temp/`, `deploy_frontend_temp/`, and `backend/local.db`
to `.gitignore`.

## Related documentation

- [`docs/MCP_SERVER.md`](MCP_SERVER.md) — the MCP server this pipeline
  deploys.
- [`docs/CONNECT_CLAUDE.md`](CONNECT_CLAUDE.md) — user-facing connection
  guide.

## Required App Settings (the `.env` trap)

The manual deploy scripts used to copy `backend/.env` into the zip, so
production quietly inherited whatever that file contained. `deploy.yml`
excludes `.env*` on purpose — secrets do not belong in deploy artefacts — which
means **every setting the API needs must exist as an App Service App Setting**.
On 2026-08-21 four keys that had only ever lived in `.env` turned out to be
missing from `slppro-api` (`ACCESS_ADMIN_EMAILS`, `ACCESS_CONTROL_MODE`,
`ACCESS_FULL_STUDENT_ACCESS_EMAILS`, `OPENAI_API_KEY`): nobody was admin and
the in-app AI chat had no key. The backend deploy job now has a gate that
fails BEFORE deploying if any of these names is absent on the target (names
only — values are never read or logged):

| Setting | Purpose |
|---|---|
| `ENVIRONMENT` | `production` — turns on JWT signature verification, turns off dev `create_all` |
| `AUTH_REQUIRE_BEARER` | `true` — no anonymous fallback user |
| `AAD_TENANT_ID`, `AAD_CLIENT_ID` | Entra validation (issuer / JWKS) |
| `SQL_SERVER_CONNECTION_STRING` | Azure SQL (slpdb_2) |
| `SLP_PUBLIC_ORIGIN`, `SLP_FRONTEND_ORIGIN` | OAuth issuer/resource URI and consent-page redirect |
| `ACCESS_CONTROL_MODE` | `off` / `monitor` / `enforce` |
| `ACCESS_ADMIN_EMAILS` | JSON list of admin sign-in emails (admins see aliases in the UI) |
| `ACCESS_FULL_STUDENT_ACCESS_EMAILS` | JSON list of accounts auto-granted every student |
| `OPENAI_API_KEY` | In-app AI chat |

Add a row here AND to `REQUIRED_APP_SETTINGS` in `deploy.yml` whenever the
API grows a new required setting.
