"""
Research-Grade Spatio-Temporal Analytics Backend
Configuration via Pydantic Settings
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars like PYTHON_VERSION
    )

    # Application
    app_name: str = "District Evolution Analytics API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    # Must be set via DATABASE_URL env var — no hardcoded credentials
    database_url: str
    db_pool_min_size: int = 2
    db_pool_max_size: int = 20
    db_command_timeout: int = 60

    db_query_timeout: int = 30

    # Logging
    log_level: str = "INFO"

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 30

    # Cache / Redis
    redis_url: str = "redis://localhost:6379/0"
    # "redis", "memory", or "auto" (try Redis, fallback to memory)
    cache_backend: str = "auto"

    @property
    def requires_ssl(self) -> bool:
        """Check if database URL requires SSL."""
        return "neon.tech" in self.database_url or "sslmode=require" in self.database_url

    # Security
    auth_enabled: bool = False
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_algorithms: list[str] = ["RS256"]

    # Deprecated
    api_key: str | None = None

    # CORS (Parsed from comma-separated env var or list)
    cors_origins: list[str] = [
        "https://i-ascap.onrender.com",
        "https://i-ascap.vercel.app",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @property
    def parsed_cors_origins(self) -> list[str]:
        """
        Merge default CORS origins with env var 'CORS_ALLOW_ORIGINS'.
        """
        defaults = set(self.cors_origins)
        # If running in explicit production, we might want to ONLY use env vars.
        # But for now, we just remove localhost from hardcoded defaults.
        return list(defaults)

    # Data Paths
    data_dir: str = "/app/data"
    lineage_csv_path: str = "/app/data/v1/district_lineage.csv"

    # Analytics
    bootstrap_iterations: int = 1000
    confidence_level: float = 0.95
    coverage_ratio_tolerance: float = 0.05  # ±5%

    # Versioning
    dataset_version: str = "v1.5_harmonized"
    boundary_version: str = "2024-01-15"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()  # type: ignore[call-arg]
