"""アプリ設定。"""

from __future__ import annotations

import logging
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    LOG_LEVEL: str = "INFO"

    # extra="ignore": DB_* や OPENAI_API_KEY など他モジュールが読む env は無視する。
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()


def configure_logging() -> None:
    logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True)
