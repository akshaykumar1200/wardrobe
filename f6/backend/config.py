"""
config.py for f6 AI Fashion Wardrobe & Outfit Recommendation Engine
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "AURA Fashion AI"
    PORT: int = 8080
    HOST: str = "0.0.0.0"

    DATABASE_URL: str = "sqlite:///./wardrobe.db"
    STORAGE_ROOT: Path = Path("storage")
    ORIGINALS_DIR: Path = Path("storage/originals")
    ITEMS_DIR: Path = Path("storage/items")

    MAX_UPLOAD_MB: int = 15
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]

    MODEL_ID: str = "mattmdjaga/segformer_b2_clothes"
    INFERENCE_SIDE: int = 1024
    WORK_SIDE: int = 1280
    OUTPUT_MAX_SIDE: int = 1024
    TORCH_THREADS: int = 4

    MATTING_ENABLED: bool = True
    MATTING_MODEL_ID: str = "ZhengPeng7/BiRefNet"
    MATTING_SIDE: int = 512


settings = Settings()

# Ensure storage directories exist
settings.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
settings.ITEMS_DIR.mkdir(parents=True, exist_ok=True)
