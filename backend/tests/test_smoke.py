"""Smoke suite — the backend half of the PR gate.

Deliberately shallow. These tests answer one question: *does this revision of
the backend still boot and serve?* They assert status codes and coarse shape,
never a router's internals, so ordinary feature work does not have to come with
a test edit. If you want depth, add a focused module next to this one rather
than tightening these.

What is actually covered:

1. the app imports and every router in ``main.py`` mounts (an ImportError or a
   duplicate/ malformed route makes this file fail at collection time);
2. ``GET /`` — the liveness probe an operator hits first;
3. ``GET /api/health/live`` — the App Service / deploy-gate probe;
4. ``GET /openapi.json`` — proves every response_model in the app can be
   resolved, which is where broken Pydantic schemas surface;
5. one write round-trip through the ORM against sqlite, using the anonymous
   fallback user that ``ENVIRONMENT=development`` +
   ``AUTH_REQUIRE_BEARER=false`` provides.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI


def test_app_object_is_a_fastapi_app(app):
    assert isinstance(app, FastAPI)
    # A handful of routes always exist; an app that mounted nothing is a bug
    # even if it imported cleanly.
    assert len(app.routes) > 10


def test_health_router_is_mounted(app):
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/" in paths
    assert any(p.startswith("/api/health") for p in paths), sorted(paths)[:20]


def test_root_returns_ok(client):
    response = client.get("/")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    assert body.get("status") == "ok"


def test_health_liveness(client):
    """The exact endpoint deploy.yml polls after a zip deploy."""
    response = client.get("/api/health/live")
    assert response.status_code == 200, response.text
    assert response.json() == {"live": True}


def test_openapi_schema_builds(client):
    """Every response_model in the app has to be resolvable to serve this."""
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    schema = response.json()
    assert schema.get("openapi", "").startswith("3.")
    assert schema["info"]["title"]
    assert len(schema.get("paths", {})) > 5


def test_students_list_is_reachable(client):
    """Anonymous fallback user must get a list, not a 401."""
    response = client.get("/api/students")
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_student_create_then_read_back(client):
    """One real write round-trip: FastAPI -> repository -> SQLAlchemy -> sqlite.

    Kept intentionally minimal — only the fields StudentBase actually requires —
    so that adding optional columns never breaks the smoke gate.
    """
    unique = uuid.uuid4().hex[:8]
    payload = {"first": f"Smoke{unique}", "last": "Test"}

    created = client.post("/api/students", json=payload)
    if created.status_code in (401, 403):
        pytest.skip(
            "student creation is auth-gated in this configuration "
            f"(HTTP {created.status_code}) — nothing to round-trip"
        )
    assert created.status_code in (200, 201), created.text

    body = created.json()
    student_id = body.get("id")
    assert isinstance(student_id, int), body

    fetched = client.get(f"/api/students/{student_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json().get("id") == student_id


def test_unknown_route_is_a_404(client):
    assert client.get("/api/definitely-not-a-route").status_code == 404
