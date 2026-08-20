"""
The door on /mcp.

A pure-ASGI middleware rather than a FastAPI dependency, for two reasons:

  * the MCP endpoint is not a FastAPI route — it is a whole ASGI application
    handed to us by the SDK, and it never sees the dependency injector; and
  * this is the ONLY path where an `slp_` key is the sole accepted credential.
    Entra JWTs are deliberately NOT honoured here: they expire hourly, which
    makes them useless to an agent that is supposed to be able to answer a
    question next Tuesday.

The middleware also OWNS the path. FastMCP's Starlette app carries its route at
`/mcp`, and Starlette's Mount only matches `/mcp/<something>` — a bare POST to
`/mcp` would fall through and answer 404/405. Intercepting the request before
routing means the URL a therapist pastes into `claude mcp add` (".../mcp", no
trailing slash) is the URL that works, with the slashed form accepted too.

What the resolved key buys is stashed in a CONTEXTVAR rather than passed down:
tool bodies are called by the SDK, several frames below anything we wrote, and
a contextvar set here is visible to them because the SDK's per-request task
group inherits this context.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field

from app.db.database import SessionLocal
from app.dependencies.auth import (
    grant_full_student_access,
    normalize_access_mode,
    resolve_allowed_student_ids,
)
from app.models.user import User
from app.services import api_tokens as api_tokens_service
from app.settings import settings

logger = logging.getLogger(__name__)

MCP_PATH = "/mcp"

# JSON-RPC reserved codes stop at -32000; -32001 is the conventional
# "unauthorized" in the application-defined range MCP servers use.
JSONRPC_UNAUTHORIZED = -32001


@dataclass(frozen=True)
class McpPrincipal:
    """
    Who this MCP call is, and which students it may touch.

    Everything here is recomputed from the database on EVERY call rather than
    frozen into the key: the key names a user, and the user's caseload is
    whatever it is right now. A student removed from somebody's access list
    stops being visible on the next tool call, not on the next key rotation.
    """

    user_id: int
    token_id: int
    user_name: str | None
    role: str
    is_admin: bool
    access_mode: str
    enforce_access: bool
    allowed_student_ids: list[int] = field(default_factory=list)

    def may_see_student(self, student_id: int | None) -> bool:
        """
        The MCP equivalent of `ensure_student_access`.

        `access_mode` is honoured exactly as the REST layer honours it: 'off'
        checks nothing, 'monitor' logs and allows, 'enforce' denies. An admin
        is allowed everywhere, as in the app.
        """
        if student_id is None:
            return False
        if self.access_mode == "off" or self.is_admin:
            return True
        if student_id in self.allowed_student_ids:
            return True
        if self.access_mode == "monitor":
            logger.warning(
                "Access monitor: MCP user %s would be denied for student %s",
                self.user_id,
                student_id,
            )
            return True
        return False


_CURRENT: ContextVar[McpPrincipal | None] = ContextVar("slp_mcp_principal", default=None)


def current_principal() -> McpPrincipal:
    """
    The caller, inside a tool body.

    Raising rather than returning None: a tool that ran without a principal
    would be a tool running with no caseload scope at all, and there is no sane
    answer to give it.
    """
    principal = _CURRENT.get()
    if principal is None:  # pragma: no cover - the middleware makes this unreachable
        raise RuntimeError("No MCP principal in context — /mcp auth did not run")
    return principal


def _header(scope, name: bytes) -> str:
    for key, value in scope.get("headers") or []:
        if key == name:
            return value.decode("latin-1")
    return ""


def resolve_principal(secret: str) -> McpPrincipal | None:
    """
    A presented secret -> the principal, or None.

    Uses its OWN session (there is no dependency-injected one here) and repeats
    the gates `get_auth_context` applies to an HTTP request: the user must
    still exist and still be active, and his allowed-student list is read fresh
    from `user_student_access` through the SAME helper the HTTP dependency uses
    — so the two doors cannot drift apart.

    What is deliberately NOT repeated is the upsert half of get_auth_context: a
    key can only exist for a user who was already created by a real sign-in, so
    there is nothing to create here, and an MCP call must never be able to
    invent a user row.
    """
    if not api_tokens_service.looks_like_token(secret):
        return None

    db = SessionLocal()
    try:
        token = api_tokens_service.resolve_token(db, secret)
        if token is None:
            return None

        token_id = token.id
        user_id = token.user_id

        user = db.get(User, user_id)
        if user is None:  # pragma: no cover - orphan token, defensive
            return None
        if not user.is_active:
            return None

        role = (user.role or "basic").lower()
        is_admin = role == "admin"

        # Same courtesy the HTTP dependency does: admins and configured
        # full-access accounts are kept topped up with every student, so a
        # student added since the last sign-in is not invisible to them.
        user_email = (user.email or "").strip().lower()
        if is_admin or (
            user_email
            and user_email in {e.strip().lower() for e in settings.access_full_student_access_emails}
        ):
            grant_full_student_access(db, user)
            db.commit()

        mode = normalize_access_mode(settings.access_control_mode)
        allowed = resolve_allowed_student_ids(db, user, is_admin=is_admin)

        principal = McpPrincipal(
            user_id=user_id,
            token_id=token_id,
            user_name=user.display_name or user.email,
            role=role,
            is_admin=is_admin,
            access_mode=mode,
            enforce_access=mode == "enforce",
            allowed_student_ids=list(allowed),
        )
        api_tokens_service.touch(db, token_id)
        return principal
    finally:
        db.close()


def _www_authenticate() -> bytes:
    """
    The 401 challenge, RFC 6750 + RFC 9728.

    `resource_metadata` is what turns this endpoint from "paste a key here"
    into something claude.ai can connect to on its own: an MCP client that gets
    a 401 reads this parameter, fetches the protected-resource document it
    points at, discovers the authorization server, registers itself and runs
    the consent flow — with the therapist never seeing a token at all. Omit it
    and the client has nowhere to start and simply reports that it cannot
    authenticate.

    The header is emitted TODAY even though the document it names is not served
    yet (that is the OAuth facade's job): the manual-key path is unaffected by
    a discovery URL that 404s, and having the challenge already correct means
    the facade becomes reachable the moment it exists, with nothing here to
    change.
    """
    return (
        f'Bearer realm="slppro", '
        f'resource_metadata="{settings.resource_metadata_url}"'
    ).encode("latin-1")


async def _unauthorized(send, message: str) -> None:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": JSONRPC_UNAUTHORIZED, "message": message},
        }
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                # RFC 6750: tell the agent HOW to authenticate, not just that
                # it failed.
                (b"www-authenticate", _www_authenticate()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class McpAuthMiddleware:
    """
    Owns `/mcp` (and `/mcp/`): authenticates, then hands the request to the
    SDK's ASGI app. Everything else passes straight through untouched.
    """

    def __init__(self, app, mcp_app, path: str = MCP_PATH):
        self.app = app
        self.mcp_app = mcp_app
        self.path = path

    def _is_mcp(self, scope) -> bool:
        if scope.get("type") != "http":
            return False
        raw = scope.get("path") or ""
        return raw.rstrip("/") == self.path

    async def __call__(self, scope, receive, send):
        if not self._is_mcp(scope):
            await self.app(scope, receive, send)
            return

        auth = _header(scope, b"authorization")
        secret = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
        if not api_tokens_service.looks_like_token(secret):
            await _unauthorized(
                send,
                "This endpoint needs SLP Pro authorization. Add it as a custom "
                "connector and sign in with your SLP Pro login, or send "
                "Authorization: Bearer slp_... with a connection key from "
                "Settings > Connect Claude.",
            )
            return

        principal = resolve_principal(secret)
        if principal is None:
            await _unauthorized(
                send,
                "That authorization is unknown, expired, revoked, or belongs "
                "to a deactivated account.",
            )
            return

        # The SDK's app carries its single route at MCP_PATH; normalise so the
        # slashed and unslashed forms both land on it.
        scope = dict(scope)
        scope["path"] = self.path
        scope["raw_path"] = self.path.encode("ascii")

        reset = _CURRENT.set(principal)
        try:
            await self.mcp_app(scope, receive, send)
        finally:
            _CURRENT.reset(reset)
