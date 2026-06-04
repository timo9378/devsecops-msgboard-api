"""All configuration comes from env vars.
ConfigMap injects DATABASE_HOST / NAME / USER etc., Secret injects PASSWORD
and JWT_SECRET. Nothing is hard-coded for production — the dev defaults below
are placeholders that MUST be overridden by env / k8s Secret.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database (from ConfigMap + Secret) ───────────
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "msgboard"
    database_user: str = "koim"
    database_password: str = "changeme"  # dev placeholder; k8s overrides via Secret

    # ── JWT (from Secret) ────────────────────────────
    jwt_secret: str = "dev-secret-do-not-use-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── App-level (from ConfigMap) ───────────────────
    app_env: str = "development"        # dev / staging / prod — 不同階段套不同設定
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
