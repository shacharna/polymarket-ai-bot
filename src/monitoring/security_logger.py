"""
Security Event Logging for Trading Bot
Tracks authentication failures, rate limit violations, and unusual activity
Separate from regular trading logs for security auditing
"""
from loguru import logger
from datetime import datetime
from typing import Optional


class SecurityLogger:
    """
    Centralized security event logging.
    All security events are logged to a separate security.log file
    for easy auditing and monitoring.
    """

    def __init__(self):
        # Add separate log file for security events
        logger.add(
            "logs/security.log",
            rotation="10 MB",
            retention="90 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="WARNING",
            filter=lambda record: record["extra"].get("SECURITY", False)
        )
        logger.bind(SECURITY=True).info("Security logger initialized")

    def log_unauthorized_access(self, chat_id, command, username=None):
        # type: (str, str, Optional[str]) -> None
        """Log unauthorized Telegram access attempt"""
        user_info = f"@{username}" if username else "unknown"
        logger.bind(SECURITY=True).warning(
            f"🚨 Unauthorized access | chat_id={chat_id} | "
            f"user={user_info} | command={command}"
        )

    def log_rate_limit_violation(self, command, remaining_time, chat_id=None):
        # type: (str, int, Optional[str]) -> None
        """Log rate limit violation"""
        logger.bind(SECURITY=True).warning(
            f"⏱️ Rate limit exceeded | command={command} | "
            f"wait_time={remaining_time}s | chat_id={chat_id or 'unknown'}"
        )

    def log_suspicious_activity(self, event_type, details):
        # type: (str, str) -> None
        """Log suspicious activity"""
        logger.bind(SECURITY=True).error(
            f"⚠️ Suspicious activity | type={event_type} | details={details}"
        )

    def log_credential_usage(self, api_name, success, error_msg=None):
        # type: (str, bool, Optional[str]) -> None
        """Log API credential usage (for detecting stolen credentials)"""
        status = "SUCCESS" if success else "FAILED"
        msg = f"🔑 API auth | api={api_name} | status={status}"
        if error_msg:
            msg += f" | error={error_msg}"

        if success:
            logger.bind(SECURITY=True).info(msg)
        else:
            logger.bind(SECURITY=True).warning(msg)

    def log_critical_operation(self, operation, user, details=None):
        # type: (str, str, Optional[str]) -> None
        """Log critical operations (close all positions, etc)"""
        msg = f"🚨 Critical operation | operation={operation} | user={user}"
        if details:
            msg += f" | details={details}"
        logger.bind(SECURITY=True).warning(msg)

    def log_security_config_change(self, setting, old_value, new_value, user):
        # type: (str, str, str, str) -> None
        """Log security configuration changes"""
        logger.bind(SECURITY=True).warning(
            f"⚙️ Security config changed | setting={setting} | "
            f"old={old_value} | new={new_value} | user={user}"
        )

    def log_login_attempt(self, chat_id, success, username=None):
        # type: (str, bool, Optional[str]) -> None
        """Log Telegram bot login attempts"""
        user_info = f"@{username}" if username else f"chat_id={chat_id}"
        status = "SUCCESS" if success else "FAILED"

        if success:
            logger.bind(SECURITY=True).info(f"✅ Login {status} | user={user_info}")
        else:
            logger.bind(SECURITY=True).warning(f"❌ Login {status} | user={user_info}")

    def log_api_key_rotation(self, api_name, rotated_by):
        # type: (str, str) -> None
        """Log API key rotation events"""
        logger.bind(SECURITY=True).info(
            f"🔑 API key rotated | api={api_name} | rotated_by={rotated_by}"
        )


# Singleton instance
_security_logger = None  # type: Optional[SecurityLogger]


def get_security_logger():
    # type: () -> SecurityLogger
    """Get or create security logger instance"""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger
