from functools import lru_cache
from typing import List, Any, Optional
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator


class Settings(BaseSettings):
    environment: str = "development"
    cors_allow_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://slppro-dbgmguexhmd5h3fh.eastus2-01.azurewebsites.net",
    ]

    # Azure AD / Auth
    aad_tenant_id: str = ""
    aad_client_id: str = ""
    aad_client_secret: str = ""
    aad_authority: str = "https://login.microsoftonline.com/"

    # OpenAI
    openai_api_key: str = ""
    ai_model: str = "gpt-5.2"
    ai_reasoning_effort: str = "low"
    ai_verbosity: str = "medium"
    ai_max_output_tokens: int = 100000
    ai_chat_history_max_messages: int = 12
    ai_chat_history_max_input_tokens: int = 60000

    # Database
    sql_server_connection_string: str = ""

    # Access control / user bootstrap
    access_control_mode: str = "monitor"  # off | monitor | enforce
    access_admin_emails: List[str] = []
    access_full_student_access_emails: List[str] = []
    auth_require_bearer: bool = False
    auth_fallback_user_external_id: str = "local-user"
    auth_fallback_user_email: str = ""
    auth_fallback_user_name: str = "Local User"

    # The ONE origin this installation calls itself by (env: SLP_PUBLIC_ORIGIN).
    #
    # Read from the environment rather than from the request's Host header on
    # purpose: an MCP client that gets a 401 is told where to look for the
    # protected-resource metadata, and a spoofed Host would otherwise be able
    # to point it somewhere else. It is also the prefix of the canonical
    # resource URI, so a key minted for SLP Pro cannot be replayed against
    # something that merely answers on another name.
    public_origin: str = Field(
        default="https://slppro-api-a7caazgxa2gcaaaz.eastus2-01.azurewebsites.net",
        validation_alias=AliasChoices("SLP_PUBLIC_ORIGIN", "public_origin"),
    )

    # Where the SPA lives (env: SLP_FRONTEND_ORIGIN).
    #
    # SLP Pro is split across two Azure app services: this API answers on
    # `public_origin` and the React app on another host entirely. That is the
    # one place this OAuth facade differs from a single-origin app — the
    # authorize endpoint cannot redirect to a PATH, it has to name the SPA's
    # origin, and the origin has to come from configuration because the API
    # process has no other way to know it.
    #
    # Empty means "use the default for this environment" — see consent_origin.
    frontend_origin: str = Field(
        default="",
        validation_alias=AliasChoices("SLP_FRONTEND_ORIGIN", "frontend_origin"),
    )

    # Verify Entra JWT signatures? None = decide from the environment.
    #
    # The default is the safe one: anything that is not `development` verifies.
    # The override exists so a developer can point a local run at a real tenant
    # and exercise the production validator without pretending to be
    # production everywhere else (env: AUTH_JWT_VERIFY=1).
    auth_jwt_verify: Optional[bool] = None

    # The audience an Entra access token must carry to be accepted by the
    # production validator. Defaults to this installation's registered API
    # scope so nothing has to be configured for the existing deployment.
    aad_api_audience: str = "api://604604d7-697a-4111-8845-a1bc1014bd49"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _parse_cors_list(cls, value: Any):
        if value is None:
            return value
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return []
            # Try JSON array first
            if val.startswith("["):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            # Fallback: comma-separated string
            return [item.strip() for item in val.split(",") if item.strip()]
        return value

    @field_validator("access_admin_emails", "access_full_student_access_emails", mode="before")
    @classmethod
    def _parse_email_list(cls, value: Any):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return []
            if val.startswith("["):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            return [item.strip().lower() for item in val.split(",") if item.strip()]
        return value

    @property
    def resource_uri(self) -> str:
        """
        The canonical MCP resource identifier (RFC 8707), with NO trailing
        slash. A client that sends `resource` on the OAuth authorize endpoint
        must send exactly this string; anything else is a token being asked
        for a different audience.
        """
        return f"{self.public_origin.rstrip('/')}/mcp"

    @property
    def resource_metadata_url(self) -> str:
        """Where an unauthenticated /mcp call is told to look (RFC 9728)."""
        return f"{self.public_origin.rstrip('/')}/.well-known/oauth-protected-resource/mcp"

    @property
    def consent_origin(self) -> str:
        """
        The origin of the SPA that shows the OAuth consent screen.

        Configured value wins. With nothing configured, development falls back
        to http://localhost:3000 (what `npm run dev` serves, and already in the
        CORS allow list) and everything else to the deployed frontend host, so
        neither a developer nor the Azure app service needs a setting to make
        the flow work.
        """
        configured = (self.frontend_origin or "").strip().rstrip("/")
        if configured:
            return configured
        if self.environment.strip().lower() == "development":
            return "http://localhost:3000"
        return "https://slppro-dbgmguexhmd5h3fh.eastus2-01.azurewebsites.net"

    @property
    def consent_url(self) -> str:
        """The absolute URL /oauth/authorize hands the browser to."""
        return f"{self.consent_origin}/connect/authorize"

    @property
    def verify_jwt_signatures(self) -> bool:
        """
        Which Entra validator the API door uses.

        One question, one answer, read in one place (app.security.validator):
        an explicit AUTH_JWT_VERIFY wins, otherwise every environment except
        `development` verifies signatures against Entra's JWKS.
        """
        if self.auth_jwt_verify is not None:
            return bool(self.auth_jwt_verify)
        return self.environment.strip().lower() != "development"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


