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
    # Pricing per 1M tokens (input/output), as of 2026-07:
    #   gemini-2.5-flash-lite  $0.10 / $0.40   <- default, 15x cheaper than 3.6
    #   gemini-3.1-flash-lite  $0.25 / $1.50
    #   gemini-2.5-flash       $0.30 / $2.50
    #   gemini-3.6-flash       $1.50 / $7.50
    # gemini-2.0-flash is DEPRECATED (shut down 2026-06-01) — do not use.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    # Routing is classification, not writing — run it on the cheapest model even
    # if you upgrade GEMINI_MODEL for reply composition.
    GEMINI_ROUTER_MODEL: str = "gemini-2.5-flash-lite"

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
    # CALIBRATION NOTE: ts_rank with default normalisation returns SMALL values —
    # roughly 0.061 for a single matching term, 0.099 for two, ~0.2+ for a
    # strong multi-term match. A threshold like 0.30 means the fast path never
    # fires and every question costs a model call. Tune with:
    #   python -m scripts.tune_retrieval
    FTS_FAST_PATH_RANK: float = 0.05
    # Qdrant score below which we treat retrieval as "nothing relevant found".
    SEMANTIC_MIN_SCORE: float = 0.55

    # Keyword rank above which we trust the lexical match on its own. Below it,
    # semantic search also runs and the results are merged (hybrid retrieval).
    # Set to 0 to make every query keyword-only; set high to always use vectors.
    FTS_STRONG_MATCH_RANK: float = 0.25

    # --- Retrieval confidence (hybrid_retrieval) ---
    # These replace hand-tuned ts_rank thresholds as the decision variable.
    # Cosine similarity is comparable across queries in a way ts_rank is not.
    RETRIEVAL_HIGH: float = 0.72     # one clear winner -> answer from it
    RETRIEVAL_FLOOR: float = 0.55    # below this, nothing relevant was found
    RETRIEVAL_MIN_GAP: float = 0.06  # gap to 2nd place; smaller means ambiguous

    # Use grounded LLM composition for every question rather than templates.
    # Costs ~$0.10/month more per client and is measurably more accurate.
    ALWAYS_COMPOSE_ANSWERS: bool = True

    # --- Agent mode (tool-calling) ---
    # The model decides intent and sequencing; tools enforce every rule. This
    # replaces hand-written intent routing, which caused 6 of the 10 bugs found
    # in live testing. Costs roughly $1.70/month per client at 3,000 messages.
    # Set false to fall back to the deterministic pipeline (kept as a safety net).
    AGENT_MODE: bool = True
    AGENT_MAX_ROUNDS: int = 5

    # Per-customer inbound rate limit.
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # LLM generation caps.
    # NOTE: thinking models (gemini-2.5+/3.x) spend output budget on internal
    # reasoning before emitting text. Too low a cap returns EMPTY text with
    # finish_reason=MAX_TOKENS, which looks like a parsing bug. Keep headroom.
    LLM_MAX_OUTPUT_TOKENS: int = 800
    ROUTER_MAX_OUTPUT_TOKENS: int = 1024

    # Routing/extraction is classification, not reasoning — disable thinking to
    # cut both latency and cost. Ignored automatically by non-thinking models.
    GEMINI_DISABLE_THINKING: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
