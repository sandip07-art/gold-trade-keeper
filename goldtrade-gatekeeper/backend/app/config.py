from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./goldtrade.db"
    MAX_TRADES_PER_DAY: int = 3
    MAX_DAILY_LOSS_PCT: float = 2.0
    RISK_PER_TRADE_PCT: float = 1.0
    ATR_EXPANSION_MULTIPLIER: float = 1.5
    ATR_AVG_PERIODS: int = 20
    NEWS_WINDOW_MINUTES: int = 30
    CORS_ORIGINS: str = "*"


settings = Settings()
