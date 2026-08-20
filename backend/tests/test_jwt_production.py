"""
The production Entra validator, exercised with locally signed tokens.

Entra issues two shapes of access token for the same API registration:

    v1  aud = "api://<client-guid>"   iss = "https://sts.windows.net/<tenant>/"
    v2  aud = "<client-guid>"         iss = "https://login.microsoftonline.com/<tenant>/v2.0"

The validator pins the v2 issuer (requestedAccessTokenVersion=2 on the
registration) but must accept BOTH audience spellings — the aud flip is
controlled by the app registration, not by us, and accepting only one form
401s every caller the moment that setting changes. These tests sign real
RS256 tokens with a throwaway key and stub the JWKS lookup, so the
signature/aud/iss/exp checks all genuinely run.
"""

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.security import jwt_production
from app.settings import settings

# Pinned test identities — NOT read from settings/env, so the validator and
# the signed tokens agree regardless of what AAD_* vars the machine has (CI
# has none; a dev box may have real ones).
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
API_URI_AUD = "api://11112222-3333-4444-5555-666677778888"
BARE_GUID_AUD = API_URI_AUD.removeprefix("api://")
V2_ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
V1_ISSUER = f"https://sts.windows.net/{TENANT}/"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def validator(rsa_key, monkeypatch):
    monkeypatch.setattr(settings, "aad_tenant_id", TENANT)
    monkeypatch.setattr(settings, "aad_api_audience", API_URI_AUD)
    v = jwt_production.JWTValidator()

    class _Key:
        key = rsa_key.public_key()

    class _StubJwks:
        def get_signing_key_from_jwt(self, token):
            return _Key()

    monkeypatch.setattr(v, "jwks_client", _StubJwks())
    return v


def _sign(rsa_key, *, aud, iss=V2_ISSUER, exp_minutes=5, **extra):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-123",
        "aud": aud,
        "iss": iss,
        "exp": now + timedelta(minutes=exp_minutes),
        "nbf": now - timedelta(minutes=1),
        "iat": now,
        "preferred_username": "someone@example.com",
        "name": "Some One",
        # a sampling of real v2 claims the model must tolerate
        "oid": "11111111-2222-3333-4444-555555555555",
        "tid": TENANT,
        "scp": "access_as_user",
        "ver": "2.0",
        **extra,
    }
    return pyjwt.encode(payload, rsa_key, algorithm="RS256")


def test_v2_bare_guid_audience_is_accepted(validator, rsa_key):
    """The regression: v2 tokens carry the bare client-id GUID as aud."""
    claims = validator.validate_jwt(_sign(rsa_key, aud=BARE_GUID_AUD))
    assert claims.sub == "user-123"
    assert claims.preferred_username == "someone@example.com"


def test_api_uri_audience_is_accepted(validator, rsa_key):
    """The v1-style App ID URI audience keeps working."""
    claims = validator.validate_jwt(_sign(rsa_key, aud=API_URI_AUD))
    assert claims.sub == "user-123"


def test_wrong_audience_is_rejected(validator, rsa_key):
    with pytest.raises(ValueError, match="audience"):
        validator.validate_jwt(_sign(rsa_key, aud="api://someone-elses-api"))


def test_v1_issuer_is_rejected(validator, rsa_key):
    """v1 sts.windows.net tokens are rejected — the registration requests v2."""
    with pytest.raises(ValueError, match="issuer"):
        validator.validate_jwt(_sign(rsa_key, aud=BARE_GUID_AUD, iss=V1_ISSUER))


def test_expired_token_is_rejected(validator, rsa_key):
    with pytest.raises(ValueError, match="expired"):
        validator.validate_jwt(_sign(rsa_key, aud=BARE_GUID_AUD, exp_minutes=-5))


def test_wrong_key_signature_is_rejected(validator):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(ValueError):
        validator.validate_jwt(_sign(other_key, aud=BARE_GUID_AUD))
