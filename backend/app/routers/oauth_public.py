"""
The OAuth 2.1 connector facade — the endpoints that let claude.ai add SLP Pro
as a custom connector without anybody copying a key anywhere.

TWO routers live in this file, and the split between them is the design:

  `router` — UNAUTHENTICATED, outside /api, outside the OpenAPI schema. Its
  paths are fixed by RFC and its caller is a machine that has, by definition,
  no credential yet:

      GET  /.well-known/oauth-protected-resource        RFC 9728
      GET  /.well-known/oauth-protected-resource/mcp    RFC 9728
      GET  /.well-known/oauth-authorization-server      RFC 8414
      POST /oauth/register                              RFC 7591 (DCR)
      GET  /oauth/authorize                             RFC 6749 + PKCE
      POST /oauth/token                                 RFC 6749 (form-encoded)

  `consent_router` — /api/oauth, behind the ordinary session gate, called by a
  signed-in therapist's browser. It is where the human decision is recorded and
  the authorization code is actually minted.

The one thing NOT in the public half is the human step. /oauth/authorize does
no login and shows no consent UI: it validates, and then hands the browser to
the SPA, where the app's existing Entra sign-in and a consent card live.

SLP Pro is split across two Azure app services — the API answers on
settings.public_origin and the React app on settings.consent_origin — so unlike
a single-origin app this redirect must name an ABSOLUTE URL on another host.
That host is configuration (SLP_FRONTEND_ORIGIN), never anything the caller
sent, because a redirect target read from a request is an open redirect with
extra steps.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import AuthContext
from app.routers.api_tokens import require_session_auth
from app.schemas.oauth import OAuthConsentIn, OAuthRedirectOut
from app.services import oauth as oauth_service
from app.services.oauth import OAuthError
from app.settings import settings

logger = logging.getLogger(__name__)

# include_in_schema=False: these are RFC paths for machines, and putting them
# in the therapist-facing OpenAPI document would only invite somebody to call
# them by hand.
router = APIRouter(include_in_schema=False)

# The human half. `require_session_auth` is the SAME dependency the connection
# key routes use, imported rather than re-written so the two cannot drift: a
# real Entra session is required, an `slp_` key can never reach it (a key is
# not a JWT and fails to decode), and the development fallback user is allowed
# through so the flow is testable locally.
#
# A key that could approve a NEW grant would be a key that quietly issues
# itself a fresh family of successors, and revoking the original would fix
# nothing.
consent_router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# Discovery documents are public, tiny and change only on redeploy.
_DISCOVERY_CACHE = "public, max-age=3600"

# RFC 6749 §5.1: token responses must never be cached.
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _error_page(title: str, message: str, status_code: int = 400) -> HTMLResponse:
    """
    The dead end for an authorize request whose client or callback cannot be
    trusted.

    This is the ONE place the flow renders HTML itself, and it exists because
    the alternative is worse: if we do not recognise the client, or the
    redirect_uri does not match what it registered, then redirecting is
    forwarding the browser (and, in other error shapes, an authorization code)
    to an address an attacker chose. RFC 6749 §4.1.2.1 says exactly this — do
    not redirect, inform the user.

    Rendered in-process rather than bounced to the SPA for the same reason: the
    SPA is a different origin, and a cross-origin hop is a redirect too.
    """
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SLP Pro — connection problem</title>
<style>
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         margin: 0; padding: 48px 20px; background: #f6f7f9; color: #17202b; }}
  .card {{ max-width: 34rem; margin: 0 auto; background: #fff; border-radius: 14px;
          padding: 28px 30px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
  h1 {{ font-size: 1.25rem; margin: 0 0 .6rem; }}
  p {{ line-height: 1.5; margin: 0 0 .8rem; }}
  .muted {{ color: #5b6672; font-size: .9rem; }}
</style></head>
<body><div class="card">
<h1>{title}</h1>
<p>{message}</p>
<p class="muted">Nothing was shared and no access was granted. Close this window
and start the connection again from Claude.</p>
</div></body></html>"""
    return HTMLResponse(content=body, status_code=status_code)


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------
def _discovery(payload: dict) -> JSONResponse:
    return JSONResponse(content=payload, headers={"Cache-Control": _DISCOVERY_CACHE})


@router.get("/.well-known/oauth-protected-resource")
def protected_resource_metadata_root() -> JSONResponse:
    """RFC 9728, at the bare well-known path."""
    return _discovery(oauth_service.protected_resource_metadata())


@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata_mcp() -> JSONResponse:
    """
    RFC 9728 again, at the path a client derives from the resource URI — and
    the exact URL the /mcp 401 challenge points at (see app.mcp.auth).

    Both are served because clients differ on which one they ask for: the RFC
    says to insert the resource's path component into the well-known path
    (giving .../oauth-protected-resource/mcp), while plenty of implementations
    just fetch the bare one. Serving both costs one route and removes an entire
    class of "connector won't connect" support question.
    """
    return _discovery(oauth_service.protected_resource_metadata())


@router.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata() -> JSONResponse:
    """RFC 8414. The issuer is settings.public_origin, never the Host header."""
    return _discovery(oauth_service.authorization_server_metadata())


# --------------------------------------------------------------------------
# RFC 7591 dynamic client registration
# --------------------------------------------------------------------------
@router.post("/oauth/register", status_code=status.HTTP_201_CREATED)
async def register(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """
    A client registers itself, unauthenticated, and gets a client_id.

    Open registration is not an oversight — it is what DCR is. The client_id it
    yields is not a permission: it names a would-be caller and nothing more.
    Nothing is reachable until a signed-in therapist reads a consent card and
    presses Approve, and the row created here is inert until then.

    Unknown metadata fields are ignored rather than rejected (RFC 7591 §2), so
    a client that sends software_statement, client_uri, logo_uri, scope or
    anything else invented next year still registers.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_client_metadata",
                "error_description": "Body must be a JSON object",
            },
        )

    raw_uris = payload.get("redirect_uris")
    if not isinstance(raw_uris, list) or not raw_uris:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_redirect_uri",
                "error_description": "redirect_uris is required and must be a "
                "non-empty array",
            },
        )
    bad = [u for u in raw_uris if not oauth_service.is_registerable_redirect_uri(u)]
    if bad:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_redirect_uri",
                "error_description": "Every redirect_uri must be https:// (or "
                "http:// on loopback) and carry no fragment",
            },
        )

    auth_method = payload.get(
        "token_endpoint_auth_method", oauth_service.PUBLIC_CLIENT_AUTH
    )
    if auth_method != oauth_service.PUBLIC_CLIENT_AUTH:
        # A confidential client would need a secret we would then have to store
        # and hand back over HTTP. Public + PKCE is both simpler and stronger.
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_client_metadata",
                "error_description": "Only public clients are supported "
                '(token_endpoint_auth_method must be "none")',
            },
        )

    grant_types = payload.get("grant_types")
    if not isinstance(grant_types, list) or not grant_types:
        grant_types = ["authorization_code", "refresh_token"]
    unsupported = [
        g for g in grant_types if g not in ("authorization_code", "refresh_token")
    ]
    if unsupported:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_client_metadata",
                "error_description": "Supported grant_types are "
                "authorization_code and refresh_token",
            },
        )

    response_types = payload.get("response_types")
    if not isinstance(response_types, list) or not response_types:
        response_types = ["code"]
    if [t for t in response_types if t != "code"]:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_client_metadata",
                "error_description": 'The only response_type is "code"',
            },
        )

    name = payload.get("client_name")
    client = oauth_service.register_client(
        db,
        client_name=name if isinstance(name, str) else None,
        redirect_uris=[str(u) for u in raw_uris],
        grant_types=grant_types,
        response_types=response_types,
    )
    logger.info(
        "OAuth DCR: registered client_name=%r redirect_uris=%s",
        client.client_name,
        client.redirect_uris,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        headers=_NO_STORE,
        content={
            "client_id": client.client_id,
            "client_id_issued_at": int(client.created_at.timestamp()),
            "client_name": client.client_name,
            "redirect_uris": json.loads(client.redirect_uris),
            "grant_types": json.loads(client.grant_types or "[]"),
            "response_types": json.loads(client.response_types or "[]"),
            "token_endpoint_auth_method": client.token_endpoint_auth_method,
        },
    )


# --------------------------------------------------------------------------
# RFC 6749 authorization endpoint
# --------------------------------------------------------------------------
@router.get("/oauth/authorize")
def authorize(request: Request, db: Session = Depends(get_db)) -> Response:
    """
    Validate the request, then hand the browser to the SPA.

    Two very different failure modes live here, and the difference is the point:

      * client_id unknown, or redirect_uri not EXACTLY one this client
        registered -> render an error page. Never redirect. The address we
        would redirect to is precisely the thing we just failed to verify.
      * anything else wrong (response_type, PKCE, resource) -> redirect to the
        PROVEN callback with error=..., which is what lets the client show the
        user a sensible message instead of hanging.

    On success nothing is minted and nothing is remembered: a 302 to the SPA's
    /connect/authorize carrying the original query string verbatim, so the
    consent page reads exactly what the client sent — including `state`, which
    must come back to the client byte for byte or its CSRF check fails. There
    is no server-side pending-request row because there is nothing worth
    keeping: every parameter is re-validated against the registration when the
    therapist approves, so a hand-edited query string buys an attacker nothing.
    """
    params = request.query_params
    client_id = params.get("client_id") or ""
    redirect_uri = params.get("redirect_uri") or ""

    client = oauth_service.get_client(db, client_id)
    if client is None:
        return _error_page(
            "Unknown app",
            "The app that sent you here is not registered with SLP Pro, so we "
            "cannot show you a sign-in for it.",
        )
    if not oauth_service.redirect_uri_matches(client, redirect_uri):
        return _error_page(
            "That return address does not match",
            "The address this app asked us to send you back to is not one it "
            "registered. SLP Pro will not forward you to it.",
        )

    try:
        oauth_service.validate_authorization_request(
            response_type=params.get("response_type"),
            code_challenge=params.get("code_challenge"),
            code_challenge_method=params.get("code_challenge_method"),
            resource=params.get("resource"),
        )
    except OAuthError as exc:
        return RedirectResponse(
            url=oauth_service.build_redirect(
                redirect_uri,
                {
                    "error": exc.error,
                    "error_description": exc.description,
                    "state": params.get("state"),
                },
            ),
            status_code=status.HTTP_302_FOUND,
        )

    # The original query string, verbatim, PLUS one field the OAuth request
    # itself has no room for: the name this client registered under. Only this
    # handler can supply it — it has just looked the registration up and proved
    # it — and the consent page needs it for the anti-phishing line that names
    # who is asking. Appended rather than merged so `state` and everything else
    # reach the page exactly as the client sent them; a client_name in the
    # incoming query is overridden here, because a caller-supplied one would be
    # precisely the lie the field exists to prevent.
    forwarded = [
        (k, v) for k, v in request.query_params.multi_items() if k != "client_name"
    ]
    if client.client_name:
        forwarded.append(("client_name", client.client_name))
    query = urlencode(forwarded)
    target = settings.consent_url
    return RedirectResponse(
        url=f"{target}?{query}" if query else target,
        status_code=status.HTTP_302_FOUND,
    )


# --------------------------------------------------------------------------
# RFC 6749 token endpoint
# --------------------------------------------------------------------------
@router.post("/oauth/token")
async def token(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """
    application/x-www-form-urlencoded in, JSON out — both fixed by RFC 6749.

    No client authentication: every client here is public, and PKCE is what
    stands in for the secret. The access token that comes out is an ordinary
    `slp_` key with a 24-hour expiry, which is why /mcp needed no new code to
    accept it.
    """
    try:
        form = await request.form()
    except Exception:  # pragma: no cover - malformed body
        form = {}
    grant_type = (form.get("grant_type") or "").strip()

    try:
        if grant_type == "authorization_code":
            issued = oauth_service.redeem_code(
                db,
                code=(form.get("code") or "").strip(),
                client_id=(form.get("client_id") or "").strip(),
                redirect_uri=(form.get("redirect_uri") or "").strip(),
                code_verifier=(form.get("code_verifier") or "").strip(),
            )
        elif grant_type == "refresh_token":
            issued = oauth_service.refresh(
                db,
                refresh_token=(form.get("refresh_token") or "").strip(),
                client_id=(form.get("client_id") or "").strip() or None,
            )
        elif not grant_type:
            raise OAuthError("invalid_request", "grant_type is required")
        else:
            raise OAuthError(
                "unsupported_grant_type",
                "Supported grant types are authorization_code and refresh_token",
            )
    except OAuthError as exc:
        db.rollback()
        logger.info("OAuth token refused: %s (%s)", exc.error, exc.description)
        return JSONResponse(
            status_code=exc.status_code, headers=_NO_STORE, content=exc.as_dict()
        )

    token_id = issued.pop("_token_id", None)
    logger.info("OAuth token issued: api_token id=%s", token_id)
    return JSONResponse(status_code=200, headers=_NO_STORE, content=issued)


# --------------------------------------------------------------------------
# the human step: /api/oauth/consent
# --------------------------------------------------------------------------
def _bad_request(exc: OAuthError) -> HTTPException:
    """
    An OAuth validation failure, shaped for the SPA rather than for a client.

    The consent page shows this to a therapist, so it carries a readable
    message and the RFC error code beside it — the page never has to parse
    prose to decide what happened.
    """
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"message": exc.description or exc.error, "code": exc.error},
    )


def _resolve_client(db: Session, client_id: str, redirect_uri: str):
    """
    Re-establish that the client and callback are genuine.

    Everything the SPA sent came from a query string the SPA did not verify.
    This repeats the two checks /oauth/authorize made, because a therapist
    could have been sent straight to the consent page with hand-written
    parameters.
    """
    client = oauth_service.get_client(db, client_id)
    if client is None:
        raise _bad_request(
            OAuthError("invalid_client", "That app is not registered with SLP Pro")
        )
    if not oauth_service.redirect_uri_matches(client, redirect_uri):
        raise _bad_request(
            OAuthError(
                "invalid_request",
                "That return address is not one this app registered",
            )
        )
    return client


@consent_router.post("/consent", response_model=OAuthRedirectOut)
def consent_approve(
    payload: OAuthConsentIn,
    auth: AuthContext = Depends(require_session_auth),
    db: Session = Depends(get_db),
):
    """
    The therapist says yes: mint a single-use authorization code and tell the
    browser where to take it.

    Nothing long-lived is created here. The code is ten minutes, one use, and
    bound to (client, callback, PKCE challenge, this therapist) — so even if
    the redirect leaks, whoever holds it cannot exchange it without the
    verifier, cannot exchange it at a different callback, and cannot exchange
    it twice.

    The code is bound to `auth.user`, not to `auth.effective_user`: consent is
    given by the person signed in, and an admin browsing act-as must not be
    able to hand out a connector that runs as somebody else.
    """
    client = _resolve_client(db, payload.client_id, payload.redirect_uri)

    try:
        oauth_service.validate_authorization_request(
            response_type="code",
            code_challenge=payload.code_challenge,
            code_challenge_method=payload.code_challenge_method,
            resource=payload.resource,
        )
    except OAuthError as exc:
        raise _bad_request(exc)

    _row, code = oauth_service.create_code(
        db,
        client=client,
        user_id=auth.user.id,
        redirect_uri=payload.redirect_uri,
        code_challenge=payload.code_challenge,
        resource=payload.resource,
    )
    logger.info(
        "OAuth consent approved: user=%s client_id=%s", auth.user.id, payload.client_id
    )
    return {
        "redirect_url": oauth_service.build_redirect(
            payload.redirect_uri, {"code": code, "state": payload.state}
        )
    }


@consent_router.post("/consent/deny", response_model=OAuthRedirectOut)
def consent_deny(
    payload: OAuthConsentIn,
    auth: AuthContext = Depends(require_session_auth),
    db: Session = Depends(get_db),
):
    """
    The therapist says no.

    RFC 6749 §4.1.2.1: a refusal is still an answer, delivered to the client's
    own callback as error=access_denied with the state it sent. Silence would
    leave claude.ai spinning forever with no way to tell "he said no" from "the
    server fell over".

    The client and callback are validated exactly as on approve — a denial is
    the one response an attacker would love to have redirected somewhere of his
    choosing, because it looks harmless.
    """
    _resolve_client(db, payload.client_id, payload.redirect_uri)
    return {
        "redirect_url": oauth_service.build_redirect(
            payload.redirect_uri, {"error": "access_denied", "state": payload.state}
        )
    }


__all__ = ["router", "consent_router"]
