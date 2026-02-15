from functools import lru_cache
from typing import List, Any
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


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

    # Database
    sql_server_connection_string: str = ""

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


