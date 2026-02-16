"""
Configuration settings for Polymarket AI Trading Bot
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Polymarket API
    polymarket_api_key: str = Field(..., alias="POLYMARKET_API_KEY")
    polymarket_api_secret: str = Field(..., alias="POLYMARKET_API_SECRET")
    polymarket_api_passphrase: str = Field(..., alias="POLYMARKET_API_PASSPHRASE")

    # Wallet
    wallet_private_key: str = Field(..., alias="WALLET_PRIVATE_KEY")
    wallet_address: str = Field(..., alias="WALLET_ADDRESS")

    # Anthropic
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., alias="TELEGRAM_CHAT_ID")

    # Trading Configuration
    initial_balance: float = Field(100.0, alias="INITIAL_BALANCE")
    max_position_size: float = Field(10.0, alias="MAX_POSITION_SIZE")
    daily_loss_limit: float = Field(20.0, alias="DAILY_LOSS_LIMIT")
    risk_per_trade: float = Field(2.0, alias="RISK_PER_TRADE")

    # System
    paper_trading: bool = Field(True, alias="PAPER_TRADING")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    polygon_rpc_url: str = Field("https://polygon-rpc.com", alias="POLYGON_RPC_URL")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Singleton instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance"""
    global settings
    if settings is None:
        settings = Settings()
    return settings
