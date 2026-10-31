import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite:///./wardrobe.db"
    STORAGE_ROOT: str = "./storage"

    # Supabase. Empty means the app runs entirely on the local SQLite file and
    # local disk, which is the default and stays working untouched.
    SUPABASE_DB_URL: str = ""
    CLOUD_MODE: bool = False
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_BUCKET: str = "wardrobe"
    MAX_UPLOAD_MB: int = 10
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp"

    SESSION_SECRET: str = "default_secret_please_change_in_production"
    SESSION_DAYS: int = 30
    COOKIE_SECURE: bool = Field(default_factory=lambda data: data.get("CLOUD_MODE", False))
    COOKIE_SAMESITE: str = "lax"

    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "AdminSecurePassword123!"

    MODEL_ID: str = "mattmdjaga/segformer_b2_clothes"
    # Mask is predicted here, then upsampled. 512 meant an ~8x blow-up on a
    # phone photo, so every edge arrived as a visible staircase.
    INFERENCE_SIDE: int = 1024
    # Masking and cropping both happen at this resolution. Bounds the logit
    # tensor and stops 18MB item PNGs at the source.
    WORK_SIDE: int = 1280
    # Longest side of a stored cutout.
    OUTPUT_MAX_SIDE: int = 1024
    TORCH_THREADS: int = 4
    LAMA_MODEL_PATH: str = str(Path.home() / ".cache" / "torch" / "hub" / "checkpoints" / "big-lama.pt")

    # Class-agnostic matting. SegFormer decides *which* garment a pixel belongs
    # to; this decides where the subject actually ends. Disable to fall back to
    # the colour heuristic, which needs no download and no extra time.
    MATTING_ENABLED: bool = True
    MATTING_MODEL_ID: str = "ZhengPeng7/BiRefNet"
    # 512 is the knee: area is stable from 320 up, but 320 leaves a pale fringe.
    # 1024 costs 77s a photo against 23s for barely crisper edges.
    MATTING_SIDE: int = 512

    PUBLIC_ORIGIN: str = "http://127.0.0.1:8000"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    RESET_TOKEN_MINUTES: int = 30


settings = Settings()


def effective_database_url(s: Settings) -> str:
    """Supabase when it is configured and the placeholder has been replaced."""
    url = s.SUPABASE_DB_URL.strip()
    if url and "PASTE_DB_PASSWORD_HERE" not in url:
        return url
    return s.DATABASE_URL


if settings.CLOUD_MODE and effective_database_url(settings).startswith("sqlite"):
    raise RuntimeError(
        "CLOUD_MODE requires a persistent Postgres database because container storage is ephemeral. "
        "Set SUPABASE_DB_URL before starting the app."
    )
