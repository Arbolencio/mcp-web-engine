"""
Centralized Configuration Module (Pydantic Settings / Environment Variables)
"""
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    API_KEY: str = Field(default="", description="Operator-generated HTTP bearer key; required for --serve")
    SEARXNG_URL: str = Field(default="http://127.0.0.1:8082/search", description="Internal SearXNG URL")
    PORT: int = Field(default=5050, ge=1, le=65535, description="Service listening port")
    HOST: str = Field(default="127.0.0.1", min_length=1, description="Service listening host")
    
    # Rate Limiting & Limits
    RATE_LIMIT_PER_MINUTE: int = Field(default=120, ge=1, le=100000, description="Max requests per minute per API key")
    DEFAULT_TIMEOUT_SEC: float = Field(default=10.0, gt=0, le=120, allow_inf_nan=False, description="Default HTTP request timeout in seconds")
    MAX_PAYLOAD_BYTES: int = Field(default=2 * 1024 * 1024, ge=1, le=16 * 1024 * 1024, description="Max payload size limit (2 MB)")

    # Privacy: the DuckDuckGo HTML fallback is deliberately opt-in, so that a query
    # never leaves the host unless the operator explicitly allows it.
    ALLOW_DDG_FALLBACK: bool = Field(default=False, description="Fall back to html.duckduckgo.com when SearXNG is unavailable (privacy trade-off, off by default)")
    
    # Environment & Logging
    ENV: str = Field(default="production", description="Environment (development/production)")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

def load_settings():
    """Only an explicitly selected absolute env file may supplement process env."""
    selected = os.environ.get("MCP_WEB_ENGINE_ENV_FILE")
    if selected:
        path = Path(selected).expanduser()
        if not path.is_absolute() or not path.is_file():
            raise ValueError("MCP_WEB_ENGINE_ENV_FILE must name an existing absolute file")
        return Settings(_env_file=path, _env_file_encoding="utf-8")
    return Settings()


settings = load_settings()
