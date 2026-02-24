"""
Logging Configuration
Sets up structured logging for the entire application
Includes sensitive data filtering to prevent credential leaks
"""
from loguru import logger
import sys
import re
from pathlib import Path
from config.settings import get_settings


class SensitiveDataFilter:
    """
    Filter to redact sensitive data from logs.
    Prevents API keys, tokens, and passwords from being logged.
    """

    PATTERNS = [
        # Generic API keys and secrets
        (re.compile(r'(api[_-]?key["\s:=]+)[\w\-]{20,}', re.I), r'\1[REDACTED]'),
        (re.compile(r'(secret[_-]?key["\s:=]+)[\w\-]{20,}', re.I), r'\1[REDACTED]'),
        (re.compile(r'(token["\s:=]+)[\w\-]{20,}', re.I), r'\1[REDACTED]'),

        # Alpaca API keys (start with PK or SK)
        (re.compile(r'PK[A-Z0-9]{20,}'), '[ALPACA_KEY_REDACTED]'),
        (re.compile(r'SK[A-Z0-9]{20,}'), '[ALPACA_SECRET_REDACTED]'),

        # OpenAI API keys (start with sk-proj-)
        (re.compile(r'sk-proj-[a-zA-Z0-9\-_]{20,}'), '[OPENAI_KEY_REDACTED]'),
        (re.compile(r'sk-[a-zA-Z0-9\-_]{40,}'), '[OPENAI_KEY_REDACTED]'),

        # Telegram bot tokens (format: 1234567890:ABC...)
        (re.compile(r'\d{8,10}:AA[a-zA-Z0-9_-]{30,}'), '[TELEGRAM_TOKEN_REDACTED]'),

        # Passwords
        (re.compile(r'(password["\s:=]+)[^\s]+', re.I), r'\1[REDACTED]'),
        (re.compile(r'(pwd["\s:=]+)[^\s]+', re.I), r'\1[REDACTED]'),

        # Bearer tokens in headers
        (re.compile(r'Bearer\s+[a-zA-Z0-9\-_.]+', re.I), 'Bearer [REDACTED]'),

        # Credit card numbers (basic pattern)
        (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CARD_REDACTED]'),
    ]

    def __call__(self, record):
        """Filter function called by loguru for each log record"""
        message = record["message"]

        # Apply all redaction patterns
        for pattern, replacement in self.PATTERNS:
            message = pattern.sub(replacement, message)

        record["message"] = message
        return True


def setup_logging():
    """Configure logging for the application"""

    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Create logs directory with restricted permissions
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Try to set restrictive permissions (Unix-like systems)
    try:
        logs_dir.chmod(0o700)  # rwx------
    except Exception:
        pass  # Windows or permission denied

    # Create sensitive data filter
    sensitive_filter = SensitiveDataFilter()

    # Console handler (colored output with filtering)
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
        filter=sensitive_filter
    )

    # File handler - General log (with sensitive data filtering)
    logger.add(
        logs_dir / "trading.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        filter=sensitive_filter
    )

    # File handler - Errors only (with sensitive data filtering)
    logger.add(
        logs_dir / "errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="5 MB",
        retention="60 days",
        compression="zip",
        filter=sensitive_filter
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
