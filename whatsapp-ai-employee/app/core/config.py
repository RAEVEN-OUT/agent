from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (see ../.env)."""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    PROJECT_NAME: str = "AI Employee Platform"
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    AUTO_CREATE_TABLES: bool = True

    # --- Postgres ---
    POSTGRES_USER: str = "aiemployee"
    POSTGRES_PASSWORD: str = "aiemployee"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "aiemployee"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Qdrant ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "knowledge_chunks"

    # --- Gemini ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"
    GEMINI_EMBEDDING_DIMENSIONS: int = 1536

    # --- WhatsApp ---
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_APP_ID: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_API_VERSION: str = "v24.0"
    # Set false only for local curl testing without real Meta signatures.
    VERIFY_WEBHOOK_SIGNATURE: bool = True

    # --- Firebase (admin panel auth; not used by the webhook path) ---
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-service-account.json"

    # --- Cascade tuning ---
    # Bump these when prompts or retrieval logic change: it invalidates old
    # cached answers instead of serving stale ones.
    CACHE_PROMPT_VERSION: str = "v1"
    CACHE_RETRIEVAL_VERSION: str = "v1"
    CACHE_TTL_SECONDS: int = 3600
    EMBED_CACHE_TTL_SECONDS: int = 604800  # 7 days

    # Postgres full-text rank above which we answer without touching vectors.
    FTS_FAST_PATH_RANK: float = 0.30
    # Qdrant score below which we treat retrieval as "nothing relevant found".
    SEMANTIC_MIN_SCORE: float = 0.55

    # Per-customer inbound rate limit.
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # LLM generation caps.
    LLM_MAX_OUTPUT_TOKENS: int = 300
    ROUTER_MAX_OUTPUT_TOKENS: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
