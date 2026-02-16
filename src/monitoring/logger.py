"""
Logging Configuration
Sets up structured logging for the entire application
"""
from loguru import logger
import sys
from pathlib import Path
from config.settings import get_settings


def setup_logging():
    """Configure logging for the application"""

    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Console handler (colored output)
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True
    )

    # File handler - General log
    logger.add(
        logs_dir / "trading.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )

    # File handler - Errors only
    logger.add(
        logs_dir / "errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="5 MB",
        retention="60 days",
        compression="zip"
    )

    # File handler - Trading activity (trades, orders)
    logger.add(
        logs_dir / "trades.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        level="INFO",
        filter=lambda record: "TRADE" in record["extra"],
        rotation="10 MB",
        retention="90 days"
    )

    logger.info("Logging configured successfully")


def log_trade(action: str, market: str, price: float, size: float, **kwargs):
    """
    Log a trade execution

    Args:
        action: BUY or SELL
        market: Market name
        price: Execution price
        size: Position size
        **kwargs: Additional trade details
    """
    logger.bind(TRADE=True).info(
        f"{action} | {market} | ${price:.4f} | ${size:.2f} | {kwargs}"
    )
