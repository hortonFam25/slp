"""
Production-ready JWT validation for Azure AD tokens.
Replace the placeholder jwt.py with this implementation for deployment.
"""
from typing import Optional, Dict, Any
import requests
import jwt
from jwt import PyJWKSClient
from pydantic import BaseModel
from app.settings import settings


class TokenClaims(BaseModel):
    sub: str
    aud: Optional[str] = None
    iss: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    oid: Optional[str] = None  # Azure AD object ID
    tid: Optional[str] = None  # Azure AD tenant ID


class JWTValidator:
    def __init__(self):
        self.tenant_id = settings.aad_tenant_id
        self.client_id = settings.aad_client_id
        self.issuer = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        self.jwks_uri = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        self.audience = "api://604604d7-697a-4111-8845-a1bc1014bd49"
        
        # Initialize JWKS client for key retrieval
        self.jwks_client = PyJWKSClient(self.jwks_uri)
    
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
                audience=self.audience,
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


# Global validator instance
jwt_validator = JWTValidator()


def validate_jwt(token: str) -> TokenClaims:
    """Main function to validate JWT tokens"""
    return jwt_validator.validate_jwt(token)
