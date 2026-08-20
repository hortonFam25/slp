"""
Real JWT validation for Entra ID (Azure AD) access tokens.

This is the validator every non-development environment uses; which one is
picked, and where, is app/security/validator.py. Nothing should import this
module directly except that one.

Signature, audience, issuer and expiry are all verified against the tenant's
published JWKS. The keys are fetched on demand and cached by PyJWKClient, so
the FIRST request after a cold start pays one HTTPS round trip to
login.microsoftonline.com and the rest pay nothing.
"""
from functools import lru_cache
from typing import Optional

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel

from app.settings import settings


class TokenClaims(BaseModel):
    sub: str
    aud: Optional[str] = None
    iss: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    email: Optional[str] = None
    upn: Optional[str] = None
    unique_name: Optional[str] = None
    oid: Optional[str] = None  # Azure AD object ID
    tid: Optional[str] = None  # Azure AD tenant ID


class JWTValidator:
    def __init__(self):
        self.tenant_id = settings.aad_tenant_id
        self.client_id = settings.aad_client_id
        self.issuer = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        self.jwks_uri = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        # The API scope this installation registered. Configurable (env:
        # AAD_API_AUDIENCE) but defaulted to the existing registration, so a
        # deployment that sets nothing keeps working.
        #
        # BOTH spellings are accepted deliberately: Entra v1 access tokens
        # carry aud = the App ID URI ("api://<guid>"), v2 tokens carry aud =
        # the bare client-id GUID for the same registration. Accepting only
        # one form couples this validator to the app registration's
        # requestedAccessTokenVersion, and flipping that setting would 401
        # every caller.
        self.audience = settings.aad_api_audience
        self.audiences = [self.audience]
        if self.audience.startswith("api://"):
            self.audiences.append(self.audience.removeprefix("api://"))

        # Initialize JWKS client for key retrieval. Constructing it fetches
        # nothing; the first validated token does.
        self.jwks_client = PyJWKClient(self.jwks_uri)
    
    def validate_jwt(self, token: str) -> TokenClaims:
        """Validate Azure AD JWT token"""
        try:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audiences,
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "require": ["exp", "iss", "aud", "sub"]
                }
            )
            
            return TokenClaims(**payload)
            
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidAudienceError:
            raise ValueError("Invalid token audience")
        except jwt.InvalidIssuerError:
            raise ValueError("Invalid token issuer")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise ValueError(f"Token validation failed: {str(e)}")


@lru_cache(maxsize=1)
def get_validator() -> JWTValidator:
    """
    The process-wide validator, built on first use.

    Lazy rather than a module-level instance: this module is imported by the
    validator seam, which is imported by the auth dependency, which is imported
    by every router — and a development run must not build a JWKS client for a
    tenant it does not have.
    """
    return JWTValidator()


def validate_jwt(token: str) -> TokenClaims:
    """Main function to validate JWT tokens"""
    return get_validator().validate_jwt(token)
