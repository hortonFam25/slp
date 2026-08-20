"""
Personal API keys: mint, list, revoke, and resolve one at the door.

The scheme, in one place so nothing else has to know it:

  secret     "slp_" + secrets.token_hex(20)    -> "slp_" + 40 hex chars, 44 total
  prefix     secret[:12]                       -> "slp_a1b2c3d4", display only
  stored     sha256(secret).hexdigest()        -> 64 hex chars, UNIQUE

sha256 rather than a password hash (bcrypt/argon2) on purpose: the secret is
160 bits of `secrets` randomness, not a human-chosen password, so there is no
dictionary to slow an attacker down with — and the digest is looked up on EVERY
MCP call, where a deliberately slow KDF would be a per-request tax for no gain.
The lookup is a plain indexed equality on the digest.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models.api_token import KIND_MANUAL, KIND_OAUTH, ApiToken

# Every secret starts with this, which is what lets a door tell a machine key
# from an Entra JWT without parsing anything.
TOKEN_PREFIX = "slp_"

# 20 bytes -> 40 hex characters. Changing this changes new keys only; existing
# ones keep working because nothing here depends on the length.
TOKEN_BYTES = 20

PREFIX_LEN = 12

# Ten keys per user is far past "a laptop, a phone and Claude", and it stops a
# runaway script from filling the table.
#
# The cap counts MANUAL keys only. An OAuth access key is minted by the machine
# on a schedule for as long as the connector stays switched on — counting those
# would mean a therapist with a claude.ai connector eventually cannot press
# "create key", and, worse, that a therapist with ten keys could not connect
# claude.ai at all. The two populations are capped by different things: manual
# keys by this number, OAuth keys by their short TTL and by the user's ability
# to revoke the grant.
MAX_ACTIVE_TOKENS = 10

# Short access + long refresh is the whole point of OAuth: the credential that
# travels on every call is the one that expires soonest.
ACCESS_TOKEN_TTL = timedelta(hours=24)


class TokenLimitError(Exception):
    """Raised when a user already holds MAX_ACTIVE_TOKENS live manual keys."""


def generate_secret() -> str:
    return f"{TOKEN_PREFIX}{secrets.token_hex(TOKEN_BYTES)}"


def hash_secret(secret: str) -> str:
    """sha256 hex of the exact string the client will present."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def looks_like_token(value: str | None) -> bool:
    return bool(value) and value.startswith(TOKEN_PREFIX)


def _live(stmt, now: datetime):
    """
    The one definition of "still valid", applied as SQL.

    Revoked is dead; expired is dead in exactly the same way; a NULL
    expires_at never expires, which is what every manual key carries.
    """
    return stmt.where(ApiToken.revoked_at.is_(None)).where(
        or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > now)
    )


def list_tokens(db: Session, user_id: int) -> list[ApiToken]:
    """
    This user's LIVE keys, newest first.

    OAuth-minted keys are included deliberately — the key list is the ONE place
    a therapist can see and cut off what is talking to his caseload, and a
    connector that did not appear there would be a connection nobody could
    revoke. Expired ones are filtered out so yesterday's rotated access keys do
    not silt the list up.
    """
    stmt = (
        select(ApiToken)
        .where(ApiToken.user_id == user_id)
        .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
    )
    return list(db.execute(_live(stmt, datetime.utcnow())).scalars().all())


def count_manual_tokens(db: Session, user_id: int) -> int:
    """Live MANUAL keys for this user — what MAX_ACTIVE_TOKENS caps."""
    stmt = (
        select(ApiToken)
        .where(ApiToken.user_id == user_id)
        .where(ApiToken.kind == KIND_MANUAL)
    )
    return len(list(db.execute(_live(stmt, datetime.utcnow())).scalars().all()))


def get_token(db: Session, user_id: int, token_id: int) -> ApiToken | None:
    """
    One of this user's own live keys.

    Scoped by user so somebody else's key id is a miss rather than a forbidden
    — a 404 leaks nothing about whether that id exists.
    """
    stmt = (
        select(ApiToken)
        .where(ApiToken.id == token_id)
        .where(ApiToken.user_id == user_id)
    )
    return db.execute(_live(stmt, datetime.utcnow())).scalars().one_or_none()


def create_token(db: Session, user_id: int, name: str) -> tuple[ApiToken, str]:
    """
    Mint a key. Returns (row, plaintext) — the plaintext is never stored and
    this is the only moment it exists on the server.
    """
    if count_manual_tokens(db, user_id) >= MAX_ACTIVE_TOKENS:
        raise TokenLimitError(
            f"You already have {MAX_ACTIVE_TOKENS} connection keys. "
            f"Revoke one before creating another."
        )

    secret = generate_secret()
    row = ApiToken(
        user_id=user_id,
        name=(name or "").strip()[:80],
        token_hash=hash_secret(secret),
        prefix=secret[:PREFIX_LEN],
        created_at=datetime.utcnow(),
        kind=KIND_MANUAL,
        expires_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, secret


def create_oauth_token(
    db: Session,
    user_id: int,
    name: str,
    oauth_client_id: int,
    oauth_code_id: int,
    ttl: timedelta = ACCESS_TOKEN_TTL,
    now: datetime | None = None,
) -> tuple[ApiToken, str]:
    """
    Mint the ACCESS half of an OAuth grant.

    The same mechanism as a manual key — `slp_` + 160 bits, sha256 at rest,
    bound to a user — so no door has to learn a second credential format when
    claude.ai arrives. What differs is only that this one expires, remembers
    which client holds it, and carries the grant family that can kill it.

    Not capped by MAX_ACTIVE_TOKENS: see the note on that constant.
    """
    stamp = now or datetime.utcnow()
    secret = generate_secret()
    row = ApiToken(
        user_id=user_id,
        name=(name or "").strip()[:80],
        token_hash=hash_secret(secret),
        prefix=secret[:PREFIX_LEN],
        created_at=stamp,
        kind=KIND_OAUTH,
        expires_at=stamp + ttl,
        oauth_client_id=oauth_client_id,
        oauth_code_id=oauth_code_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, secret


def revoke_grant_family(db: Session, oauth_code_id: int, commit: bool = True) -> int:
    """
    Revoke every access key descended from one consent.

    Killing only today's access key would be a revoke that appears to work and
    stops working within the day, because the connector would simply refresh
    itself a new one.
    """
    now = datetime.utcnow()
    result = db.execute(
        update(ApiToken)
        .where(ApiToken.oauth_code_id == oauth_code_id)
        .where(ApiToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if commit:
        db.commit()
    return int(result.rowcount or 0)


def revoke_token(db: Session, row: ApiToken) -> ApiToken:
    """
    Revoke a key. The ROW IS KEPT (revoked_at is stamped) rather than deleted,
    so a digest can never be reissued to a different key by accident.
    """
    row.revoked_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_token(db: Session, secret: str) -> ApiToken | None:
    """
    The door. A presented secret -> the live key row, or None.

    Revoked AND expired keys are excluded here rather than checked by the
    caller, so there is exactly one place that decides what "still valid"
    means and no door can grow a hole by forgetting one of the two.
    """
    if not looks_like_token(secret):
        return None
    stmt = select(ApiToken).where(ApiToken.token_hash == hash_secret(secret))
    return db.execute(_live(stmt, datetime.utcnow())).scalars().one_or_none()


def touch(db: Session, token_id: int) -> None:
    """
    Stamp last_used_at.

    Deliberately a bare UPDATE committed on its own: it is a courtesy column,
    and it must not be able to fail — or roll back — the request that triggered
    it. A lost stamp under a race is fine; a 500 because we could not write one
    is not.
    """
    try:
        db.execute(
            update(ApiToken)
            .where(ApiToken.id == token_id)
            .values(last_used_at=datetime.utcnow())
        )
        db.commit()
    except Exception:  # pragma: no cover - operational surface
        db.rollback()


def to_out(row: ApiToken) -> dict:
    """The list/create shape. The secret is not here and cannot be recovered."""
    return {
        "id": row.id,
        "name": row.name,
        "prefix": row.prefix,
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
        "kind": row.kind,
        "expires_at": row.expires_at,
    }
