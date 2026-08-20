"""
The authorization-server facade.

SLP Pro is an OAuth 2.1 RESOURCE server: /mcp is the resource, and the MCP
authorization spec says a client that meets it must be able to discover an
authorization server, register itself, and run code+PKCE — with no human ever
copying a secret anywhere. Entra ID, where SLP Pro's therapists actually sign
in, does not implement Dynamic Client Registration, so it cannot be that
authorization server for claude.ai. This module is the facade that can: OUR
endpoints issue codes and tokens, while the human step — proving you are this
therapist — is still the app's own Entra sign-in inside the SPA. We never see a
password and we never mint an identity; we mint an `slp_` key for a user Entra
has already vouched for.

Everything secret here is stored as sha256 and nothing secret is ever put in a
URL except the authorization code, which is single use, dies in ten minutes,
and is worthless without the PKCE verifier that only the client that started
the flow has.

The five rules this file exists to keep:

  1. S256 only. `plain` is not accepted, not stored, not translated.
  2. Redirect URIs match EXACTLY. Never by prefix, never by host.
  3. Codes are single use, and a second use is treated as a compromise: it
     fails AND revokes everything the first use produced.
  4. Refresh tokens rotate. Presenting a burnt one gets nothing.
  5. The issuer is settings.public_origin and nothing else — never the Host
     header, which the caller controls.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.oauth_client import OAuthClient
from app.models.oauth_code import OAuthCode
from app.models.oauth_refresh_token import OAuthRefreshToken
from app.services import api_tokens as api_tokens_service
from app.settings import settings

# --------------------------------------------------------------------------
# lifetimes
# --------------------------------------------------------------------------
# Long enough for a therapist to read the consent card and press a button,
# short enough that a code left in a browser history is worthless by the time
# anyone finds it.
CODE_TTL = timedelta(minutes=10)

# The credential that rides on every /mcp call. 24h is the spec's number.
ACCESS_TTL = api_tokens_service.ACCESS_TOKEN_TTL

# Long, because the point of a connector is that it still works in November.
# It is safe to be long precisely because it rotates on every use and only
# opens /oauth/token.
REFRESH_TTL = timedelta(days=60)

SCOPE = "caseload"
S256 = "S256"
PUBLIC_CLIENT_AUTH = "none"

CODE_BYTES = 32
REFRESH_BYTES = 32
CLIENT_ID_BYTES = 16


class OAuthError(Exception):
    """
    An RFC 6749 error, carried as data.

    `error` is the machine-readable code the spec defines; the description is
    for a human reading a log or a consent card. Which of the two transports it
    takes — a 400 JSON body at the token endpoint, an error redirect at the
    authorize endpoint, an HTML page when there is no safe redirect — is the
    caller's decision, because only the caller knows whether the redirect
    target can be trusted yet.
    """

    def __init__(self, error: str, description: str = "", status_code: int = 400):
        super().__init__(f"{error}: {description}" if description else error)
        self.error = error
        self.description = description
        self.status_code = status_code

    def as_dict(self) -> dict:
        body = {"error": self.error}
        if self.description:
            body["error_description"] = self.description
        return body


# --------------------------------------------------------------------------
# secrets
# --------------------------------------------------------------------------
def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _eq(a: str, b: str) -> bool:
    """
    Constant-time string equality.

    Compares BYTES rather than str: secrets.compare_digest raises TypeError on
    a str containing anything outside ASCII, and a redirect URI is attacker
    supplied — a 500 there would be a denial of service handed over for free.
    """
    return secrets.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


def pkce_challenge(verifier: str) -> str:
    """RFC 7636 S256: base64url(sha256(verifier)), padding stripped."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def verify_pkce(verifier: str, challenge: str) -> bool:
    if not verifier or not challenge:
        return False
    try:
        computed = pkce_challenge(verifier)
    except UnicodeEncodeError:
        # RFC 7636 restricts the verifier to an ASCII alphabet; anything else
        # is malformed and simply does not match.
        return False
    # Constant time: the challenge is public, but the comparison costs nothing
    # to do right and a timing oracle on a code exchange is a real class of bug.
    return _eq(computed, challenge)


# --------------------------------------------------------------------------
# clients (RFC 7591)
# --------------------------------------------------------------------------
def is_registerable_redirect_uri(uri: str) -> bool:
    """
    https:// anywhere, or http:// on loopback.

    Loopback is allowed because a desktop client legitimately listens on
    127.0.0.1; plain http anywhere else would put an authorization code on the
    wire in the clear, which is the one thing the redirect is carrying.
    """
    if not uri or not isinstance(uri, str):
        return False
    try:
        parsed = urlparse(uri)
    except ValueError:
        return False
    if parsed.fragment:
        # RFC 6749 §3.1.2: a redirect URI may not carry a fragment.
        return False
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    if parsed.scheme == "http":
        host = (parsed.hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")
    return False


def register_client(
    db: Session,
    client_name: str | None,
    redirect_uris: list[str],
    grant_types: list[str] | None = None,
    response_types: list[str] | None = None,
    token_endpoint_auth_method: str = PUBLIC_CLIENT_AUTH,
) -> OAuthClient:
    row = OAuthClient(
        client_id=secrets.token_hex(CLIENT_ID_BYTES),
        client_name=(client_name or "").strip()[:120] or None,
        redirect_uris=json.dumps(list(redirect_uris)),
        grant_types=json.dumps(
            list(grant_types or ["authorization_code", "refresh_token"])
        ),
        response_types=json.dumps(list(response_types or ["code"])),
        token_endpoint_auth_method=token_endpoint_auth_method,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_client(db: Session, client_id: str) -> OAuthClient | None:
    if not client_id:
        return None
    stmt = select(OAuthClient).where(OAuthClient.client_id == client_id)
    return db.execute(stmt).scalars().one_or_none()


def redirect_uris_of(client: OAuthClient) -> list[str]:
    try:
        parsed = json.loads(client.redirect_uris or "[]")
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return []
    return [u for u in parsed if isinstance(u, str)]


def redirect_uri_matches(client: OAuthClient, redirect_uri: str) -> bool:
    """EXACT string equality against the registration. Never a prefix."""
    if not redirect_uri:
        return False
    return any(_eq(u, redirect_uri) for u in redirect_uris_of(client))


def client_display_name(client: OAuthClient) -> str:
    """
    What the therapist will see in his connection-key list.

    Suffixed with "connected app" rather than named only by whatever the client
    called itself, because the client picks its own name at registration and
    "Notes Helper" sitting unexplained in a list of connection keys tells
    nobody what it is or how it got there. The prefix is the client's own name
    (Claude, ChatGPT, ...) — this server is client-neutral, so the label must
    not assume claude.ai.
    """
    name = (client.client_name or "").strip()
    return (f"{name} — connected app" if name else "Connected app")[:80]


# --------------------------------------------------------------------------
# request validation, shared by /oauth/authorize and /api/oauth/consent
# --------------------------------------------------------------------------
def validate_resource(resource: str | None) -> None:
    """
    RFC 8707. `resource` is optional, but if it is sent it must name US.

    An audience-restricted token is only restricted if the server refuses to
    issue one for an audience it is not.
    """
    if resource is None or resource == "":
        return
    if resource.rstrip("/") != settings.resource_uri:
        raise OAuthError(
            "invalid_target",
            f"This server only issues tokens for {settings.resource_uri}",
        )


def validate_authorization_request(
    response_type: str | None,
    code_challenge: str | None,
    code_challenge_method: str | None,
    resource: str | None,
) -> None:
    """
    Everything that can be checked once the client and its callback are known
    to be genuine — i.e. everything whose failure may safely be reported BY
    REDIRECT, because the redirect target has already been proven.
    """
    if response_type != "code":
        raise OAuthError(
            "unsupported_response_type",
            "Only the authorization code flow is supported",
        )
    if not code_challenge:
        raise OAuthError("invalid_request", "code_challenge is required (PKCE)")
    if (code_challenge_method or "") != S256:
        # `plain` is refused rather than accepted-and-downgraded: a plain
        # challenge IS the verifier, so an intercepted authorization request
        # hands the attacker everything he needs.
        raise OAuthError("invalid_request", "code_challenge_method must be S256")
    if not 43 <= len(code_challenge) <= 128:
        raise OAuthError("invalid_request", "code_challenge is malformed")
    validate_resource(resource)


# --------------------------------------------------------------------------
# authorization codes
# --------------------------------------------------------------------------
def create_code(
    db: Session,
    client: OAuthClient,
    user_id: int,
    redirect_uri: str,
    code_challenge: str,
    resource: str | None = None,
    now: datetime | None = None,
) -> tuple[OAuthCode, str]:
    """Mint a code. Returns (row, plaintext); only the digest is stored."""
    stamp = now or datetime.utcnow()
    plaintext = secrets.token_urlsafe(CODE_BYTES)
    row = OAuthCode(
        code_hash=_hash(plaintext),
        oauth_client_id=client.id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=S256,
        resource=resource or None,
        created_at=stamp,
        expires_at=stamp + CODE_TTL,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, plaintext


def build_redirect(redirect_uri: str, params: dict) -> str:
    """
    Append params to a callback that may already carry a query string.

    RFC 6749 §3.1.2 explicitly allows a registered redirect URI to have one,
    and clobbering it would break the client's own state handling.
    """
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    if not clean:  # pragma: no cover - never called empty
        return redirect_uri
    joiner = "&" if urlparse(redirect_uri).query else "?"
    return f"{redirect_uri}{joiner}{urlencode(clean)}"


def _revoke_family(db: Session, code: OAuthCode, reason: str) -> None:
    """Kill every credential descended from one consent."""
    api_tokens_service.revoke_grant_family(db, code.id, commit=False)
    db.execute(
        update(OAuthRefreshToken)
        .where(OAuthRefreshToken.oauth_code_id == code.id)
        .where(OAuthRefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow(), revoked_reason=reason[:40])
    )
    db.commit()


def redeem_code(
    db: Session,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
    now: datetime | None = None,
) -> dict:
    """
    grant_type=authorization_code.

    Every failure is `invalid_grant` with no detail about WHICH check failed:
    telling a caller "unknown code" apart from "wrong verifier" turns the token
    endpoint into an oracle for guessing either.

    The replay rule (OAuth 2.1 §4.1.3) is the interesting one. A code presented
    twice means two parties hold it, and we cannot tell which of them is the
    real client — so the safe move is to trust neither: the second request
    fails and everything the first request produced is revoked on the spot. The
    therapist's connector breaks, loudly, instead of an attacker quietly
    holding a working key.
    """
    stamp = now or datetime.utcnow()
    if not code or not client_id or not redirect_uri or not code_verifier:
        raise OAuthError(
            "invalid_request",
            "code, client_id, redirect_uri and code_verifier are all required",
        )

    row = (
        db.execute(select(OAuthCode).where(OAuthCode.code_hash == _hash(code)))
        .scalars()
        .one_or_none()
    )
    if row is None:
        raise OAuthError("invalid_grant", "Unknown or expired authorization code")

    if row.consumed_at is not None:
        _revoke_family(db, row, "code replay")
        raise OAuthError(
            "invalid_grant",
            "This authorization code has already been used; every token issued "
            "from it has been revoked",
        )

    client = db.get(OAuthClient, row.oauth_client_id)
    if client is None or not _eq(client.client_id, client_id):
        raise OAuthError("invalid_grant", "Unknown or expired authorization code")

    if row.expires_at <= stamp:
        raise OAuthError("invalid_grant", "Unknown or expired authorization code")

    if not _eq(row.redirect_uri, redirect_uri):
        raise OAuthError("invalid_grant", "Unknown or expired authorization code")

    if row.code_challenge_method != S256 or not verify_pkce(
        code_verifier, row.code_challenge
    ):
        raise OAuthError("invalid_grant", "Unknown or expired authorization code")

    # Consume FIRST, and commit it, so the window in which two concurrent
    # redemptions could both pass the checks above is the width of one UPDATE
    # guarded by the WHERE clause below — the second one changes no rows and is
    # treated as the replay it is.
    consumed = db.execute(
        update(OAuthCode)
        .where(OAuthCode.id == row.id)
        .where(OAuthCode.consumed_at.is_(None))
        .values(consumed_at=stamp)
    )
    db.commit()
    if not consumed.rowcount:
        db.refresh(row)
        _revoke_family(db, row, "code replay")
        raise OAuthError(
            "invalid_grant",
            "This authorization code has already been used; every token issued "
            "from it has been revoked",
        )
    db.refresh(row)

    return _issue(db, client, row, stamp)


def _issue(db: Session, client: OAuthClient, code: OAuthCode, stamp: datetime) -> dict:
    """Mint the access/refresh pair for one grant and shape the RFC response."""
    token_row, access = api_tokens_service.create_oauth_token(
        db,
        user_id=code.user_id,
        name=client_display_name(client),
        oauth_client_id=client.id,
        oauth_code_id=code.id,
        ttl=ACCESS_TTL,
        now=stamp,
    )
    refresh_plain = secrets.token_urlsafe(REFRESH_BYTES)
    db.add(
        OAuthRefreshToken(
            token_hash=_hash(refresh_plain),
            oauth_client_id=client.id,
            oauth_code_id=code.id,
            user_id=code.user_id,
            created_at=stamp,
            expires_at=stamp + REFRESH_TTL,
        )
    )
    db.commit()

    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TTL.total_seconds()),
        "refresh_token": refresh_plain,
        "scope": SCOPE,
        # Not part of the response body contract, but the caller wants it for
        # logging and the route strips it.
        "_token_id": token_row.id,
    }


def refresh(
    db: Session,
    refresh_token: str,
    client_id: str | None = None,
    now: datetime | None = None,
) -> dict:
    """
    grant_type=refresh_token, with rotation.

    The presented row is burnt (used_at) and a new one takes its place, so the
    chain has exactly one live link at a time. `client_id` is checked when the
    client sends it — RFC 6749 §6 asks public clients to — but is not required,
    because the refresh token IS the credential here and refusing a correct one
    for a missing echo would just break connectors for no gain.

    A SPENT link presented again is treated exactly as a replayed authorization
    code is (OAuth 2.1 §4.14.2), and for the same reason: the legitimate client
    has already moved on to the next token, so a request carrying the old one
    means a copy of it exists somewhere it should not. Rotation alone would
    only refuse this one request while the thief — or the real client — kept
    the rest of the chain; revoking the whole family ends the grant for
    everybody, which is loud, recoverable in one re-consent, and the only
    outcome that does not leave an unknown party holding a working key.
    """
    stamp = now or datetime.utcnow()
    if not refresh_token:
        raise OAuthError("invalid_request", "refresh_token is required")

    row = (
        db.execute(
            select(OAuthRefreshToken).where(
                OAuthRefreshToken.token_hash == _hash(refresh_token)
            )
        )
        .scalars()
        .one_or_none()
    )
    if row is None:
        raise OAuthError("invalid_grant", "Unknown or expired refresh token")

    code = db.get(OAuthCode, row.oauth_code_id)
    if code is None:  # pragma: no cover - the FK makes this unreachable
        raise OAuthError("invalid_grant", "Unknown or expired refresh token")

    if row.used_at is not None or row.revoked_at is not None:
        _revoke_family(db, code, "refresh replay")
        raise OAuthError(
            "invalid_grant",
            "This refresh token has already been used; every token issued from "
            "that authorization has been revoked",
        )
    if row.expires_at <= stamp:
        # Merely out of time is not evidence of anything: the therapist left
        # the connector alone for two months. Refuse it, revoke nothing.
        raise OAuthError("invalid_grant", "Unknown or expired refresh token")

    client = db.get(OAuthClient, row.oauth_client_id)
    if client is None:  # pragma: no cover - the FK makes this unreachable
        raise OAuthError("invalid_grant", "Unknown or expired refresh token")
    if client_id and not _eq(client.client_id, client_id):
        raise OAuthError("invalid_grant", "Unknown or expired refresh token")

    burnt = db.execute(
        update(OAuthRefreshToken)
        .where(OAuthRefreshToken.id == row.id)
        .where(OAuthRefreshToken.used_at.is_(None))
        .where(OAuthRefreshToken.revoked_at.is_(None))
        .values(used_at=stamp, revoked_at=stamp, revoked_reason="rotated")
    )
    db.commit()
    if not burnt.rowcount:  # pragma: no cover - concurrent rotation
        raise OAuthError("invalid_grant", "Unknown or expired refresh token")

    return _issue(db, client, code, stamp)


def revoke_refresh_tokens_for_family(
    db: Session, oauth_code_id: int, reason: str = "revoked"
) -> int:
    """
    Cut the refresh half of a grant.

    Called when a therapist revokes an OAuth key from the connection-key list:
    an access key alone would come straight back on the next refresh, so
    revoking one without the other would be a button that does nothing an hour
    later.
    """
    result = db.execute(
        update(OAuthRefreshToken)
        .where(OAuthRefreshToken.oauth_code_id == oauth_code_id)
        .where(OAuthRefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow(), revoked_reason=reason[:40])
    )
    db.commit()
    return int(result.rowcount or 0)


def live_refresh_tokens(db: Session, oauth_code_id: int) -> int:
    """Live links in one grant's refresh chain (0 or 1 in practice)."""
    stmt = (
        select(OAuthRefreshToken)
        .where(OAuthRefreshToken.oauth_code_id == oauth_code_id)
        .where(OAuthRefreshToken.used_at.is_(None))
        .where(OAuthRefreshToken.revoked_at.is_(None))
        .where(OAuthRefreshToken.expires_at > datetime.utcnow())
    )
    return len(list(db.execute(stmt).scalars().all()))


# --------------------------------------------------------------------------
# discovery documents (RFC 9728 / RFC 8414)
# --------------------------------------------------------------------------
def protected_resource_metadata() -> dict:
    return {
        "resource": settings.resource_uri,
        "authorization_servers": [settings.public_origin.rstrip("/")],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [SCOPE],
    }


def authorization_server_metadata() -> dict:
    origin = settings.public_origin.rstrip("/")
    return {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/oauth/authorize",
        "token_endpoint": f"{origin}/oauth/token",
        "registration_endpoint": f"{origin}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": [S256],
        "token_endpoint_auth_methods_supported": [PUBLIC_CLIENT_AUTH],
        "scopes_supported": [SCOPE],
    }
