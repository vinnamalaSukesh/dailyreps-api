from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str
    mongodb_db: str = "dailyreps"
    tz_name: str = "Asia/Kolkata"
    # Shared secret the app sends as X-API-Key. Single-user app, so this is the whole auth.
    api_key: str

    # AI providers (both OpenAI-compatible). Empty key = provider disabled.
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-3.5-flash-lite"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"

    analyze_now_daily_limit: int = 3
    enable_scheduler: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
