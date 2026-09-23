from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://tracker:tracker@localhost:5432/tracker"
    jwt_secret: str = "dev-only-insecure-secret-change-me-in-production"
    jwt_ttl_minutes: int = 60
    bcrypt_rounds: int = 12
    cors_origins: list[str] = ["http://localhost:5173"]
    # Failed sign-ins allowed per window, per account and per client IP.
    login_max_failures_per_email: int = 5
    login_max_failures_per_ip: int = 20
    login_window_seconds: int = 900

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.env == "production" and (
            self.jwt_secret.startswith("dev-") or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be a random value of 32+ characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
