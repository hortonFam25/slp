# SLP Pro Backend

Run local:

```
pip install poetry
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Migrations:

`app/alembic.ini` sets `script_location = alembic`, a **relative** path, which
alembic resolves against the current working directory. So alembic has to be
run from `backend/app` — from `backend/` it fails with
`Path doesn't exist: '.../backend/alembic'`. `env.py` takes the connection
string from `SQL_SERVER_CONNECTION_STRING`.

```
cd app
poetry run alembic -c alembic.ini revision --autogenerate -m "init"
poetry run alembic -c alembic.ini upgrade head
```

Everything else about the databases — the three environments, Entra token auth,
building and seeding a dev database, and how a migration actually reaches
production — is in [docs/DATABASE.md](../docs/DATABASE.md).

Dev tooling lives in `scripts/`:

| | |
|---|---|
| `scripts/provision_dev_db.py` | build `slpdb_dev`, inventory any database (catalog views only), diff two inventories, apply the missing DDL |
| `scripts/seed_dev.py` | deterministic fake caseload for `slpdb_dev` or a local sqlite file |
| `scripts/grant_migration_identity.sql` | the minimal permissions the CI migration identity gets |
