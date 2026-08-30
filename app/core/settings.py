from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    SESSION_TTL: int = 60 * 60 * 24 * 14  # 14 days

    API_VERSION: str
    GOOGLE_OAUTH_CLIENT_ID: str
    GOOGLE_OAUTH_CLIENT_SECRET: str
    SESSION_SECRET: str
    REDIS_HOST: str
    REDIS_PORT: int

    FRONTEND_URL: str
    FRONTEND_ORIGIN: str

settings = Settings()