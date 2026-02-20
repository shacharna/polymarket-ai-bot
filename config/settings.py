"""
Configuration settings for Aggressive Stock Trading Bot
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Alpaca API
    alpaca_api_key: str = Field(..., alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(..., alias="ALPACA_SECRET_KEY")
    alpaca_base_url: str = Field(
        "https://paper-api.alpaca.markets", alias="ALPACA_BASE_URL"
    )

    # OpenAI
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", alias="OPENAI_MODEL")

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., alias="TELEGRAM_CHAT_ID")

    # Watchlist
    watchlist: str = Field(
        "AAPL,TSLA,NVDA,MSFT,AMZN,META,GOOGL,AMD,NFLX,SPY,QQQ,SOFI,PLTR,COIN,MARA",
        alias="WATCHLIST",
    )

    # Trading Configuration
    trading_mode: str = Field("aggressive", alias="TRADING_MODE")
    initial_balance: float = Field(500.0, alias="INITIAL_BALANCE")
    max_position_size: float = Field(500.0, alias="MAX_POSITION_SIZE")
    daily_loss_limit: float = Field(150.0, alias="DAILY_LOSS_LIMIT")
    risk_per_trade: float = Field(10.0, alias="RISK_PER_TRADE")

    # Aggressive Parameters
    max_concurrent_positions: int = Field(5, alias="MAX_CONCURRENT_POSITIONS")
    scan_interval: int = Field(60, alias="SCAN_INTERVAL")
    confidence_threshold: int = Field(55, alias="CONFIDENCE_THRESHOLD")
    max_position_pct: float = Field(0.25, alias="MAX_POSITION_PCT")
    daily_loss_limit_pct: float = Field(0.30, alias="DAILY_LOSS_LIMIT_PCT")
    max_trades_per_cycle: int = Field(3, alias="MAX_TRADES_PER_CYCLE")
    max_daily_trades: int = Field(50, alias="MAX_DAILY_TRADES")
    allow_ai_only_trades: bool = Field(True, alias="ALLOW_AI_ONLY_TRADES")
    allow_strategy_only_trades: bool = Field(True, alias="ALLOW_STRATEGY_ONLY_TRADES")
    market_hours_only: bool = Field(True, alias="MARKET_HOURS_ONLY")

    # Stop Loss / Take Profit
    stop_loss_pct: float = Field(-8.0, alias="STOP_LOSS_PCT")
    take_profit_pct: float = Field(15.0, alias="TAKE_PROFIT_PCT")

    # Trailing Stop
    trailing_stop_enabled: bool = Field(True, alias="TRAILING_STOP_ENABLED")
    trailing_stop_activation: float = Field(0.05, alias="TRAILING_STOP_ACTIVATION")
    trailing_stop_distance: float = Field(0.03, alias="TRAILING_STOP_DISTANCE")

    # System
    paper_trading: bool = Field(True, alias="PAPER_TRADING")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore unknown env vars (e.g. old ANTHROPIC_API_KEY)

    def get_watchlist_symbols(self) -> List[str]:
        """Parse watchlist string into list of symbols"""
        return [s.strip().upper() for s in self.watchlist.split(",") if s.strip()]


# Singleton instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance"""
    global settings
    if settings is None:
        settings = Settings()
    return settings
