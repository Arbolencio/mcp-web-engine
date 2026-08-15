"""
Centralized Configuration Module (Pydantic Settings / Environment Variables)
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    API_KEY: str = Field(default="sk_mcp_dev_key_12345", description="Bearer API key for authentication")
    SEARXNG_URL: str = Field(default="http://127.0.0.1:8082/search", description="Internal SearXNG URL")
    PORT: int = Field(default=5050, description="Service listening port")
    HOST: str = Field(default="0.0.0.0", description="Service listening host")
    
    # Rate Limiting & Limits
    RATE_LIMIT_PER_MINUTE: int = Field(default=120, description="Max requests per minute per API key")
    DEFAULT_TIMEOUT_SEC: float = Field(default=10.0, description="Default HTTP request timeout in seconds")
    MAX_PAYLOAD_BYTES: int = Field(default=2 * 1024 * 1024, description="Max payload size limit (2 MB)")
    
    # Environment & Logging
    ENV: str = Field(default="production", description="Environment (development/production)")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

settings = Settings()
