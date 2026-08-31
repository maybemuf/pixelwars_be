from urllib.parse import urlsplit

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    ENVIROMENT: str
    SESSION_TTL: int = 60 * 60 * 24 * 14  # 14 days

    API_VERSION: str
    GOOGLE_OAUTH_CLIENT_ID: str
    GOOGLE_OAUTH_CLIENT_SECRET: str
    SESSION_SECRET: str
    REDIS_HOST: str
    REDIS_PORT: int
    COOLDOWN_SEC: int

    # AnyHttpUrl so a scheme-less value ("localhost:3000") fails at startup instead of
    # silently breaking the OAuth redirect and every CORS/Socket.IO origin check.
    FRONTEND_URL: AnyHttpUrl

    @property
    def FRONTEND_ORIGIN(self) -> str:
        """scheme://host:port — what a browser puts in the Origin header."""
        url = urlsplit(str(self.FRONTEND_URL))
        return f"{url.scheme}://{url.netloc}"
    
    def is_production(self) -> bool:
        return self.ENVIROMENT == "prod"

settings = Settings()

BOARD_KEY = "board:main"
BOARD_OWNAGE_KEY = "board:main:ownage"
BOARD_USERS_KEY = "board:main:users"
BOARD_LOGS_KEY = "board:main:logs"
BOARD_LEADERBOARD_KEY = "board:main:leaderboard"
BOARD_TOTAL_KEY = "board:main:total"
# capped log: keeps replay/audit useful without letting the stream outgrow the board
BOARD_LOG_MAXLEN = 1_000_000
BOARD_DIM = 1024
BOARD_MAX_OFFSET = BOARD_DIM * BOARD_DIM - 1