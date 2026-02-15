# SLP Pro Backend

Run local:

```
pip install poetry
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Migrations:

```
poetry run alembic -c app/alembic.ini revision --autogenerate -m "init"
poetry run alembic -c app/alembic.ini upgrade head
```


