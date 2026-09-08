from __future__ import annotations

from dataclasses import dataclass
import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "VC Simulation Backend")
    app_env: str = os.getenv("APP_ENV", "local")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:55422/postgres",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://:local_redis_pass@127.0.0.1:6380/0")
    auto_create_tables: bool = _bool_env("AUTO_CREATE_TABLES", True)
    runtime_state_ttl_seconds: int = int(os.getenv("RUNTIME_STATE_TTL_SECONDS", "86400"))
    cors_allowed_origins: tuple[str, ...] = _csv_env(
        "CORS_ALLOWED_ORIGINS",
        (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ),
    )
    supabase_url: str = os.getenv("SUPABASE_URL", "http://127.0.0.1:55421")
    models_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET_MODELS", "models")
    thumbnails_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET_THUMBNAILS", "thumbnails")
    uploads_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET_UPLOADS", "uploads")
    exports_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET_EXPORTS", "exports")


settings = Settings()
