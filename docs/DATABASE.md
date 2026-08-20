# Databases

Where SLP Pro's data lives, how to connect to it, how to build a development
copy, and how a schema change gets from a migration file to production.

---

## Environments

| | **production** | **development** | **local** |
|---|---|---|---|
| Database | `slpdb_2` | `slpdb_dev` | a sqlite file |
| Server | `hortonfam.database.windows.net` | `hortonfam.database.windows.net` | your disk |
| Contains | **real student PII** — names, dates of birth, UICs, IEP goals, therapy notes | fake data from `backend/scripts/seed_dev.py` | fake data, or nothing |
| Created | — | 2026-08-19 | `sqlite:///./local.db` on first run |
| Auth | Entra ID token (no passwords) | Entra ID token (no passwords) | none |
| Who writes to it | the app, and `alembic upgrade` from CI | you, freely | you, freely |
| Safe to seed? | **never** | yes | yes |
| Safe to `SELECT *`? | **no — see the PII rules below** | yes | yes |

There is no `slpdb` any more. The original database was **deleted on
2026-08-20**; anything that still names it is stale and should be corrected to
`slpdb_2`.

Alembic head is **`c5a91b3e77d4`**. `slpdb_2`'s schema predates alembic
entirely: it corresponds to revision **`f2d4b8c9a1e0`** and (before the first
run of the migration workflow) carries no `alembic_version` table at all. The
two revisions between those points — `a7f31c9e5d02` (api_tokens) and
`c5a91b3e77d4` (the OAuth facade tables) — are what a first production
migration actually applies. Both are pure DDL.

---

## Production access rules (read this before connecting to `slpdb_2`)

`slpdb_2` is a special-education caseload. The rules are not about being
careful; they are about not looking.

1. **Catalog views only.** Against production you may read `sys.*` and
   `INFORMATION_SCHEMA.*` — table names, column types, index definitions,
   trigger bodies. You may not `SELECT` from a user table. Not to "check a
   count", not to "see one row", not to sanity-check a migration.
2. **The tooling enforces it.** `provision_dev_db.py --compare` validates every
   statement before it sends it (`_assert_catalog_only`) and refuses anything
   that is not a `SELECT` against a system catalog. A test
   (`backend/tests/test_seed_dev.py`) sweeps the module's source and fails if a
   SQL literal anywhere in it names a user table.
3. **Nothing writes to production except alembic.** `--provision`, `--apply`
   and `seed_dev.py` all ask the server `SELECT DB_NAME()` and refuse anything
   that is not literally `slpdb_dev`. There is no flag that turns that off.
4. **The CI identity cannot read data.** `slp-deploy-github` is a member of
   `db_ddladmin` and has DML on exactly one table — `dbo.alembic_version`,
   which holds revision hashes. `SELECT * FROM dbo.students` fails for it. See
   `backend/scripts/grant_migration_identity.sql` for the reasoning.
5. **Never copy production data down.** A development database is seeded with
   Faker output, never with a restore or an export of `slpdb_2`.
6. **Schema inventories are not committed.** `db-artifacts/` and `schema-*.json`
   are gitignored. They contain no rows, but a prod inventory is still a map of
   production and does not belong in the repository.

---

## Connecting

### Entra token auth, locally

There are no SQL logins on these databases. Everything authenticates with an
Entra ID access token, and the token comes from whoever `az` is logged in as.

```powershell
az login
az account set --subscription <AZURE_SUBSCRIPTION_ID>

# Prove you can mint a token for Azure SQL (prints an expiry, never the token):
az account get-access-token --resource https://database.windows.net/ --query expiresOn -o tsv
```

You also need **ODBC Driver 18 for SQL Server** installed locally, and the
backend dependencies:

```powershell
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

The scripts in `backend/scripts/` support two ways of handing that token to the
driver, selected with `SLP_DB_AUTH`:

| `SLP_DB_AUTH` | How | When |
|---|---|---|
| `token` (default) | `az account get-access-token` → `attrs_before={1256: <token struct>}` (`SQL_COPT_SS_ACCESS_TOKEN`) | anything the scripts do themselves |
| `azcli` | `Authentication=ActiveDirectoryAzCli` in the ODBC string | when the connection has to travel as a URL — alembic's `env.py` builds its engine with `engine_from_config()` and cannot take `connect_args` |

Environment variables the scripts read:

```
SLP_DB_SERVER    default hortonfam.database.windows.net
SLP_DB_NAME      required — no default, so nothing is ever guessed
SLP_ODBC_DRIVER  default "ODBC Driver 18 for SQL Server"
SLP_DB_AUTH      token | azcli
```

### Alembic, by hand

`backend/app/alembic.ini` sets `script_location = alembic`, a **relative** path.
Alembic resolves it against the current working directory, so it has to be run
from `backend/app` — from anywhere else it cannot find `versions/` and says so.
`env.py` reads the connection string from `SQL_SERVER_CONNECTION_STRING`.

```powershell
$env:SQL_SERVER_CONNECTION_STRING = "sqlite:///./local.db"
$env:PYTHONPATH = "$PWD/backend"
cd backend/app
alembic -c alembic.ini current
alembic -c alembic.ini upgrade head
```

### Local sqlite

The fastest loop. Nothing Azure is involved:

```powershell
python backend/scripts/seed_dev.py --sqlite ./dev-seed.db --reset
$env:SQL_SERVER_CONNECTION_STRING = "sqlite:///./dev-seed.db"
$env:ENVIRONMENT = "development"
$env:AUTH_REQUIRE_BEARER = "false"
python backend/start_server.py
```

The models carry `server_default=GETDATE()` on ~60 columns, which sqlite does
not have. `seed_dev.py` (and `backend/tests/conftest.py`) install a
sqlite-only statement shim that rewrites it to `CURRENT_TIMESTAMP`. It is
scoped to the sqlite dialect; nothing else in the app's SQL is touched.

---

## Runbook: provisioning and seeding `slpdb_dev`

Run from the repository root, in order. Every step is idempotent except the
seed, which needs `--reset` to repeat.

```powershell
# ---- 0. prerequisites -------------------------------------------------
az login
az account set --subscription <AZURE_SUBSCRIPTION_ID>
mkdir -Force db-artifacts       # gitignored

# ---- 1. inventory PRODUCTION (read-only, catalog views only) ----------
# This is the baseline everything else is compared against, and the check
# that prod really is at f2d4b8c9a1e0. It reads no user table.
$env:SLP_DB_NAME = "slpdb_2"
python backend/scripts/provision_dev_db.py --compare --out db-artifacts/schema-prod.json

# ---- 2. build the dev schema -----------------------------------------
# create_all from app/models + `alembic stamp head`.
# Refuses unless the server answers DB_NAME() = 'slpdb_dev'.
$env:SLP_DB_NAME = "slpdb_dev"
python backend/scripts/provision_dev_db.py --provision

# ---- 3. inventory DEV -------------------------------------------------
python backend/scripts/provision_dev_db.py --compare --out db-artifacts/schema-dev.json

# ---- 4. diff, review, apply ------------------------------------------
# Baseline = prod, target = dev. Emits DDL for the triggers, views,
# functions, procedures and secondary indexes dev is missing. Schema drift
# (missing tables/columns) is REPORTED as a comment, never generated —
# that belongs in a migration.
python backend/scripts/provision_dev_db.py --diff `
    db-artifacts/schema-prod.json db-artifacts/schema-dev.json `
    --out db-artifacts/dev-missing.sql

#   READ db-artifacts/dev-missing.sql NOW.
#
#   Expected shape of a healthy diff:
#     * "tables present in the target only" lists api_tokens, oauth_clients,
#       oauth_codes, oauth_refresh_tokens, alembic_version — the objects the
#       two unapplied revisions add. That is the confirmation that prod
#       really is at f2d4b8c9a1e0.
#     * "tables MISSING from the target" should be empty. Anything there is
#       a table prod has that the models do not, and wants a decision, not
#       a script.
#     * the executable part should be triggers (SLP Pro's schema uses them,
#       which is why the app runs with implicit_returning=False) and any
#       views.

python backend/scripts/provision_dev_db.py --apply db-artifacts/dev-missing.sql --dry-run
python backend/scripts/provision_dev_db.py --apply db-artifacts/dev-missing.sql

# ---- 5. re-inventory dev and confirm the gap closed -------------------
python backend/scripts/provision_dev_db.py --compare --out db-artifacts/schema-dev.json
python backend/scripts/provision_dev_db.py --diff `
    db-artifacts/schema-prod.json db-artifacts/schema-dev.json `
    --out db-artifacts/dev-missing-2.sql
#   Expect "Nothing to apply" in the executable section.

# ---- 6. grant the CI identity, dev FIRST ------------------------------
sqlcmd -S hortonfam.database.windows.net -d slpdb_dev -G -i backend/scripts/grant_migration_identity.sql
sqlcmd -S hortonfam.database.windows.net -d slpdb_2   -G -i backend/scripts/grant_migration_identity.sql

# ---- 7. seed dev with fake data --------------------------------------
$env:SLP_DB_NAME = "slpdb_dev"
python backend/scripts/seed_dev.py --reset
```

### What the seed produces

Deterministic (fixed Faker seed), so two runs give the same caseload:

3 schools · 10 teachers · 3 roles · 25 students · 6 eligibility categories ·
35 student eligibilities · 6 goal categories · 50 IEP goals · 150 objectives ·
6 time blocks · 24 block assignments · 100 appointments · 50 therapy sessions ·
100 session goals · 100 session objectives · 100 progress entries · 1 dev user
(`external_auth_id = 'local-user'`, matching the backend's development
anonymous-fallback identity) with access grants to all 25 students.

The exact numbers live in `seed_dev.PLAN` and are asserted by
`backend/tests/test_seed_dev.py`, so a change to the generator that quietly
changes the shape of the dataset fails the build.

Progress notes name the student they belong to, in sentences, because that is
what the AI progress-note features read.

Re-run with `--reset` to get a clean caseload. `--reset` deletes only the
tables the seeder writes, in foreign-key order; if some other tool has put rows
in a table that references `students`, it will fail on the foreign key rather
than widen its blast radius.

---

## Runbook: migrations

Schema changes ship by hand, through
[`.github/workflows/migrate.yml`](../.github/workflows/migrate.yml). It is
`workflow_dispatch` only.

### 1. Write the migration

```powershell
$env:SQL_SERVER_CONNECTION_STRING = "sqlite:///./local.db"
$env:PYTHONPATH = "$PWD/backend"
cd backend/app
alembic -c alembic.ini revision --autogenerate -m "what it does"
```

Read the generated script. Autogenerate against sqlite will not get SQL Server
right on its own — check types, server defaults (`GETDATE()`), and that
constraint changes are wrapped in `batch_alter_table` the way
`c5a91b3e77d4_add_oauth_facade_tables.py` does.

### 2. Rehearse on dev

```powershell
gh workflow run migrate.yml -f target=dev
gh run watch
```

`target=dev` needs no confirmation string. The dev database has the same schema,
the same triggers, and — deliberately — **the same grants** as production, so a
green run here is real evidence that production has enough permission. That is
the main reason `slpdb_dev` exists.

Then re-seed and exercise the app against it:

```powershell
$env:SLP_DB_NAME = "slpdb_dev"
python backend/scripts/seed_dev.py --reset
```

### 3. Ship to production

```powershell
gh workflow run migrate.yml -f target=prod -f confirm=migrate-prod
gh run watch
```

`confirm` must be exactly `migrate-prod`. Anything else fails the first step,
before the runner has installed a driver or logged in to Azure. (The
GitHub UI works too: **Actions → migrate → Run workflow**, pick `prod`, type
the confirmation.)

### What the workflow does

1. checks the confirmation string, and stops there if it is wrong;
2. maps `dev` → `slpdb_dev`, `prod` → `slpdb_2`;
3. installs `msodbcsql18` + `unixodbc-dev` from Microsoft's apt repository,
   keyed to the runner's Ubuntu release;
4. `azure/login@v2` with the repo variables `AZURE_CLIENT_ID`,
   `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` — OIDC, no secrets. GitHub-hosted
   runners reach the server through the `AllowAllWindowsAzureIps` firewall rule;
5. verifies the service principal can mint an Azure SQL token (prints the
   expiry, never the token);
6. asks `sys.tables` whether `alembic_version` exists;
7. **if it does not** — a database whose schema predates alembic —
   `alembic stamp f2d4b8c9a1e0`. One-time bootstrap; writes a version row and
   nothing else. In practice
   `grant_migration_identity.sql` has already created and stamped the table, so
   this branch is a fallback;
8. `alembic upgrade head`;
9. echoes `alembic current` before and after.

`concurrency: migrate-slppro` means one migration at a time across both
targets. Two alembic runs racing for the same `alembic_version` row is how a
schema ends up half-applied.

The workflow issues no query against a user table, prints no row of data, and
puts no token in an environment variable, a file, or the log.

### After a production migration

```powershell
$env:SLP_DB_NAME = "slpdb_2"
python backend/scripts/provision_dev_db.py --compare --out db-artifacts/schema-prod-after.json
python backend/scripts/provision_dev_db.py --diff `
    db-artifacts/schema-prod-after.json db-artifacts/schema-dev.json `
    --out db-artifacts/prod-vs-dev.sql
```

Both directions should be empty apart from seeded-data artefacts. Catalog views
only, as always.

---

## The tools

| File | What it is |
|---|---|
| [`backend/scripts/provision_dev_db.py`](../backend/scripts/provision_dev_db.py) | `--provision` / `--compare` / `--diff` / `--apply`. Only `--provision` and `--apply` can write, and only to `slpdb_dev`. |
| [`backend/scripts/seed_dev.py`](../backend/scripts/seed_dev.py) | Deterministic fake caseload. Refuses anything but `slpdb_dev` or sqlite. |
| [`backend/scripts/grant_migration_identity.sql`](../backend/scripts/grant_migration_identity.sql) | The exact, minimal permissions the CI identity gets, with the reasoning for each. |
| [`.github/workflows/migrate.yml`](../.github/workflows/migrate.yml) | The dispatch-only migration workflow. |
| [`backend/tests/test_seed_dev.py`](../backend/tests/test_seed_dev.py) | The gate: the guards refuse production, the catalog-only rule holds across the whole module, and the seeder runs end to end on sqlite. |

---

## Troubleshooting

**`Principal 'slp-deploy-github' could not be resolved`** — `CREATE USER ...
FROM EXTERNAL PROVIDER` for a service principal needs the logical server's
managed identity to have the **Directory Readers** Entra role. One-time change,
made by someone with Privileged Role Administrator. It is not a typo in the
name.

**`Login failed for user '<token-identified principal>'`** — the token is valid
but there is no database user for it. Run
`backend/scripts/grant_migration_identity.sql` against that database.

**`The SELECT permission was denied`** during a migration — a revision is doing
DML on a user table. That is the grant set working as designed. Do not add
`db_datareader`; add a grant scoped to the one table, next to a comment naming
the revision, and revoke it once the revision is everywhere. See the reasoning
block in `grant_migration_identity.sql`.

**`Path doesn't exist: '.../backend/alembic'`** — alembic was run from the wrong
directory. `script_location` is relative; run it from `backend/app`.

**`near "(": syntax error`** on sqlite — something ran `create_all` without the
`GETDATE()` shim. Use `seed_dev.build_sqlite_engine()` or the test harness.

**`Database is paused` / error 40613** — Azure SQL serverless resuming. Retry;
the app's engine already has retry logic for it.
