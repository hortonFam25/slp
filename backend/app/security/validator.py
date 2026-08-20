"""
Which Entra validator the API door uses — decided ONCE, here.

There are two implementations in this package and they are not
interchangeable:

  * app.security.jwt         decodes with verify_signature=False. It is a
                             scaffolding decoder: it will happily accept a
                             token anybody can write by hand, so it is only
                             ever correct on a developer's laptop, where there
                             is no tenant to check against and the fallback
                             user is the only user there is.
  * app.security.jwt_production
                             fetches Entra's JWKS and verifies the signature,
                             audience, issuer and expiry for real.

Before this module the dependency imported the FIRST one unconditionally, in
every environment. That is the whole reason this file exists: the choice is now
made from configuration (settings.verify_jwt_signatures — see settings.py) and
made in exactly one place, so no door can pick the wrong one by importing the
wrong name.

The production validator is resolved LAZILY and cached. Importing it eagerly
would build a JWKS client at process start — on a box with no tenant
configured, and on the import path of every unit test — for a code path that a
development run never takes.

Claims always come back as `app.security.jwt.TokenClaims`, whichever validator
produced them, so callers (and the AuthContext dataclass) see one type.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Callable

from app.security.jwt import TokenClaims
from app.security.jwt import validate_jwt as _validate_unverified
from app.settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _verified_validator() -> Callable[[str], TokenClaims]:
    """The real one, built on first use and kept (the JWKS cache is in it)."""
    from app.security.jwt_production import get_validator

    validator = get_validator()

    def _run(token: str) -> TokenClaims:
        claims = validator.validate_jwt(token)
        # The production module has its own claims model (it carries `tid`).
        # Re-shape it into the one type the app knows; pydantic drops the
        # extras, exactly as it already does for the dozens of Entra claims
        # neither model declares.
        return TokenClaims(**claims.model_dump())

    return _run


def validate_jwt(token: str) -> TokenClaims:
    """
    Validate a bearer token, or raise.

    Raising is the contract the caller depends on: get_auth_context turns ANY
    exception from here into a 401, so a validator that cannot verify must
    never return claims.
    """
    if settings.verify_jwt_signatures:
        return _verified_validator()(token)
    return _validate_unverified(token)


__all__ = ["TokenClaims", "validate_jwt"]
