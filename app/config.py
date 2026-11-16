"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM credentials (only the provider you use is required)
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # LLM selection
    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "gpt-4o-mini"
    USE_MOCK_LLM: bool = True
    LLM_MAX_RETRIES: int = 1

    # Website extractor
    MAX_CONTENT_CHARS: int = 12000
    MAX_TOTAL_CHARS: int = 20000
    REQUEST_TIMEOUT: int = 20
    MAX_REDIRECTS: int = 5
    MAX_PAGES_PER_SITE: int = 3
    USER_AGENT: str = "AI-Link-Analysis/1.0"

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 86400
    CACHE_DIR: str = ".cache"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 4000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
