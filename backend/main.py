from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.settings import settings
from app.routers import health, students, csv_import, goals, objectives, progress_entries, schools, teachers, scheduling, therapy_sessions, eligibilities, goals_import, ai_chat, auth_access, api_tokens
from app.routers import oauth_public
from app.routers import import_upload
from app.db import database
from app.mcp import McpAuthMiddleware, mcp_asgi_app, mcp_server


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Startup/shutdown for the whole process.

    The first half is the old @on_event("startup") body, unchanged: keep local
    developer convenience, but avoid schema drift in non-development
    environments where Alembic is the source of truth.

    The second half is not optional. FastMCP's session manager runs inside an
    anyio task group that something has to enter, and the ASGI app we hand to
    the middleware is a Starlette sub-application whose OWN lifespan is never
    run by the app it is attached to. Without this the first POST to /mcp fails
    with "task group is not initialized".
    """
    if settings.environment.lower() == "development":
        from app.db.base import Base
        from app import models  # noqa: F401
        Base.metadata.create_all(bind=database.engine)

    async with mcp_server.session_manager.run():
        yield


app = FastAPI(title="SLP Pro API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The OAuth 2.1 connector facade, FIRST and deliberately so.
#
# Its paths are fixed by RFC and live outside /api: /.well-known/... and
# /oauth/... . Nothing else in this app claims them today, but registering them
# ahead of everything means a future catch-all (an SPA fallback, a proxy route)
# cannot swallow them — a discovery document that answers with HTML is worse
# than one that 404s, because the client reports "malformed metadata" and
# nobody can tell why. include_in_schema=False is set on the router itself.
app.include_router(oauth_public.router)
# The human half of the same flow: /api/oauth/consent, behind the session gate.
app.include_router(oauth_public.consent_router)

# The blind import's upload door, registered early for the same reason as the
# OAuth facade: it lives outside /api (the URL is handed to a human, who has to
# be able to read it back off a screen) and it is unauthenticated by design,
# because the URL itself is the one-shot credential. Registering it ahead of the
# /api routers means no later catch-all can claim /import/*.
# include_in_schema=False is set on the router itself.
app.include_router(import_upload.router)

app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(auth_access.router)
app.include_router(students.router)
app.include_router(csv_import.router)
app.include_router(goals_import.router)
app.include_router(goals.router)
app.include_router(objectives.router)
app.include_router(progress_entries.router)
app.include_router(schools.router)
app.include_router(teachers.router)
app.include_router(scheduling.router)
app.include_router(therapy_sessions.router)
app.include_router(eligibilities.router)
app.include_router(ai_chat.router)
app.include_router(api_tokens.router)

# /mcp is an ASGI application, not a route. It is intercepted ahead of routing
# (see app.mcp.auth for why a plain Mount cannot answer a bare POST to /mcp),
# authenticated with an slp_ connection key and nothing else, and every other
# path passes through untouched.
app.add_middleware(McpAuthMiddleware, mcp_app=mcp_asgi_app)


@app.get("/")
def root():
    return {"name": "slppro", "status": "ok"}
