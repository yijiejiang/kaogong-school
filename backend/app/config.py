from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
SAMPLE_DIR = BASE_DIR / "samples"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "kaogong"
    environment: str = "development"
    app_secret_key: str = "dev-secret-change-me"
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'app.db'}"
    adk_database_url: str = ""
    cors_origins: str = "http://localhost:3000"
    public_base_url: str = ""
    default_user_id: str = "local-user"
    mock_llm: bool = False
    enable_scheduler: bool = True
    enable_knowledge_extraction: bool = True

    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_default_model: str = ""
    llm_embedding_model: str = ""
    tavily_api_key: str = ""
    asr_local_model: str = "small"

    max_upload_bytes: int = 50 * 1024 * 1024
    max_url_bytes: int = 5 * 1024 * 1024
    chunk_size: int = 800
    chunk_overlap: int = 100
    hash_embedding_dim: int = 384

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def adk_db_url(self) -> str:
        return self.adk_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
