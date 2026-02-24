"""
Configuration settings for US Stock Trading Bot
Strict risk management enforced at all levels
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

    # Polygon.io Massive API
    polygon_api_key: str = Field(..., alias="POLYGON_API_KEY")

    # Watchlist (Pi optimization: reduced from 15 to 8 stocks)
    watchlist: str = Field(
        "AAPL,TSLA,NVDA,MSFT,SPY,QQQ,AMD,PLTR",
        alias="WATCHLIST",
    )

    # Trading Configuration
    trading_mode: str = Field("strict", alias="TRADING_MODE")
    initial_balance: float = Field(500.0, alias="INITIAL_BALANCE")
    max_position_size: float = Field(500.0, alias="MAX_POSITION_SIZE")
    daily_loss_limit: float = Field(150.0, alias="DAILY_LOSS_LIMIT")

    # ── Strict Risk Management ──
    # Per-trade risk: 0.5-1% of equity
    risk_per_trade_pct: float = Field(0.01, alias="RISK_PER_TRADE_PCT")  # 1% max
    min_risk_per_trade_pct: float = Field(0.005, alias="MIN_RISK_PER_TRADE_PCT")  # 0.5% min

    # Daily loss limit: 1-2% of equity
    daily_loss_limit_pct: float = Field(0.02, alias="DAILY_LOSS_LIMIT_PCT")  # 2% max

    # Max drawdown: 10% from peak equity - bot pauses entirely
    max_drawdown_pct: float = Field(0.10, alias="MAX_DRAWDOWN_PCT")  # 10%

    # Consecutive loss pause: pause after N consecutive losses
    max_consecutive_losses: int = Field(3, alias="MAX_CONSECUTIVE_LOSSES")

    # Position limits (Pi optimization: reduced max positions and trades)
    max_concurrent_positions: int = Field(3, alias="MAX_CONCURRENT_POSITIONS")  # Reduced from 5
    max_position_pct: float = Field(0.02, alias="MAX_POSITION_PCT")  # 2% of equity max per position
    max_trades_per_cycle: int = Field(1, alias="MAX_TRADES_PER_CYCLE")  # Reduced from 2
    max_daily_trades: int = Field(15, alias="MAX_DAILY_TRADES")  # Reduced from 20

    # Scanning (optimized for Raspberry Pi)
    scan_interval: int = Field(120, alias="SCAN_INTERVAL")  # 2min to reduce CPU
    confidence_threshold: int = Field(70, alias="CONFIDENCE_THRESHOLD")  # Raised from 65 to be more selective

    # AI role: analysis only, but can provide trade opportunities
    allow_ai_only_trades: bool = Field(True, alias="ALLOW_AI_ONLY_TRADES")
    allow_strategy_only_trades: bool = Field(True, alias="ALLOW_STRATEGY_ONLY_TRADES")
    market_hours_only: bool = Field(True, alias="MARKET_HOURS_ONLY")

    # Stop Loss / Take Profit
    stop_loss_pct: float = Field(-3.0, alias="STOP_LOSS_PCT")  # Tighter stops
    take_profit_pct: float = Field(6.0, alias="TAKE_PROFIT_PCT")  # 2:1 reward/risk

    # Trailing Stop
    trailing_stop_enabled: bool = Field(True, alias="TRAILING_STOP_ENABLED")
    trailing_stop_activation: float = Field(0.03, alias="TRAILING_STOP_ACTIVATION")
    trailing_stop_distance: float = Field(0.015, alias="TRAILING_STOP_DISTANCE")

    # System
    paper_trading: bool = Field(True, alias="PAPER_TRADING")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def get_watchlist_symbols(self) -> List[str]:
        """Parse watchlist string into list of symbols"""
        return [s.strip().upper() for s in self.watchlist.split(",") if s.strip()]


# Singleton instance
settings = None  # type: Optional[Settings]


def get_settings():
    # type: () -> Settings
    """Get or create settings instance"""
    global settings
    if settings is None:
        settings = Settings()
    return settings
