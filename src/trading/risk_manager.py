"""
Risk Management System
Enforces trading limits and protects capital
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
from config.settings import get_settings


class RiskManager:
    """Manages risk and enforces trading limits"""

    def __init__(self):
        """Initialize risk manager"""
        self.settings = get_settings()
        self.daily_loss = 0.0
        self.daily_trades = 0
        self.last_reset = datetime.now()
        self.open_positions_value = 0.0

        logger.info("Risk Manager initialized")

    def reset_daily_stats(self):
        """Reset daily statistics at midnight"""
        now = datetime.now()
        if now.date() > self.last_reset.date():
            logger.info("Resetting daily statistics")
            self.daily_loss = 0.0
            self.daily_trades = 0
            self.last_reset = now

    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed

        Returns:
            (can_trade, reason)
        """
        self.reset_daily_stats()

        # Check daily loss limit
        if abs(self.daily_loss) >= self.settings.daily_loss_limit:
            return False, f"Daily loss limit reached (${abs(self.daily_loss):.2f})"

        # Check maximum daily trades (prevent overtrading)
        max_daily_trades = 50
        if self.daily_trades >= max_daily_trades:
            return False, f"Maximum daily trades reached ({max_daily_trades})"

        return True, "Trading allowed"

    def validate_position_size(
        self,
        position_size: float,
        current_balance: float
    ) -> tuple[bool, float, str]:
        """
        Validate and adjust position size

        Args:
            position_size: Requested position size in USD
            current_balance: Current account balance

        Returns:
            (is_valid, adjusted_size, reason)
        """
        # Check minimum position size
        min_size = 1.0
        if position_size < min_size:
            return False, 0, f"Position size too small (min: ${min_size})"

        # Check maximum position size from settings
        max_size = self.settings.max_position_size
        if position_size > max_size:
            logger.warning(
                f"Position size ${position_size:.2f} exceeds max ${max_size:.2f}, adjusting"
            )
            position_size = max_size

        # Check percentage of balance (max 10% per trade)
        max_pct_per_trade = 0.10
        max_from_balance = current_balance * max_pct_per_trade
        if position_size > max_from_balance:
            logger.warning(
                f"Position size ${position_size:.2f} exceeds 10% of balance, "
                f"adjusting to ${max_from_balance:.2f}"
            )
            position_size = max_from_balance

        # Check if we have enough balance
        if position_size > current_balance:
            return False, 0, f"Insufficient balance (need ${position_size:.2f}, have ${current_balance:.2f})"

        return True, position_size, "Position size valid"

    def calculate_position_size(
        self,
        confidence: int,
        current_balance: float,
        ai_suggested_size: float = None
    ) -> float:
        """
        Calculate appropriate position size based on confidence and balance

        Args:
            confidence: AI confidence level (0-100)
            current_balance: Current account balance
            ai_suggested_size: AI suggested position size (1-10 scale)

        Returns:
            Position size in USD
        """
        # Base position size on confidence
        # Low confidence (0-40): 1-2% of balance
        # Medium confidence (41-70): 2-5% of balance
        # High confidence (71-100): 5-10% of balance

        if confidence < 40:
            pct = 0.01  # 1%
        elif confidence < 70:
            pct = 0.03  # 3%
        else:
            pct = 0.07  # 7%

        # Adjust by AI suggested size if provided
        if ai_suggested_size:
            # Scale: 1-10 → 0.5x-2.0x multiplier
            multiplier = 0.5 + (ai_suggested_size / 10) * 1.5
            pct *= multiplier

        position_size = current_balance * pct

        # Apply maximum limits
        position_size = min(position_size, self.settings.max_position_size)

        # Round to 2 decimals
        position_size = round(position_size, 2)

        logger.debug(
            f"Calculated position size: ${position_size:.2f} "
            f"(confidence: {confidence}%, balance: ${current_balance:.2f})"
        )

        return position_size

    def should_stop_loss(
        self,
        entry_price: float,
        current_price: float,
        position_type: str
    ) -> tuple[bool, str]:
        """
        Check if stop loss should be triggered

        Args:
            entry_price: Entry price
            current_price: Current price
            position_type: "BUY" or "SELL"

        Returns:
            (should_stop, reason)
        """
        # Calculate loss percentage
        if position_type.upper() == "BUY":
            loss_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SELL
            loss_pct = ((entry_price - current_price) / entry_price) * 100

        # Stop loss at -15%
        stop_loss_pct = -15.0

        if loss_pct <= stop_loss_pct:
            return True, f"Stop loss triggered: {loss_pct:.2f}%"

        return False, ""

    def should_take_profit(
        self,
        entry_price: float,
        current_price: float,
        position_type: str,
        target_profit_pct: float = 20.0
    ) -> tuple[bool, str]:
        """
        Check if profit target is reached

        Args:
            entry_price: Entry price
            current_price: Current price
            position_type: "BUY" or "SELL"
            target_profit_pct: Target profit percentage

        Returns:
            (should_exit, reason)
        """
        # Calculate profit percentage
        if position_type.upper() == "BUY":
            profit_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SELL
            profit_pct = ((entry_price - current_price) / entry_price) * 100

        if profit_pct >= target_profit_pct:
            return True, f"Profit target reached: {profit_pct:.2f}%"

        return False, ""

    def record_trade(self, profit_loss: float):
        """
        Record a completed trade

        Args:
            profit_loss: Profit or loss amount
        """
        self.daily_loss += profit_loss
        self.daily_trades += 1

        if profit_loss < 0:
            logger.warning(f"Trade loss recorded: ${profit_loss:.2f}")
        else:
            logger.info(f"Trade profit recorded: ${profit_loss:.2f}")

        logger.info(
            f"Daily stats: {self.daily_trades} trades, "
            f"${self.daily_loss:+.2f} P&L"
        )

    def get_risk_metrics(self) -> Dict:
        """
        Get current risk metrics

        Returns:
            Dictionary with risk metrics
        """
        return {
            "daily_loss": self.daily_loss,
            "daily_trades": self.daily_trades,
            "loss_limit": self.settings.daily_loss_limit,
            "loss_limit_used_pct": (abs(self.daily_loss) / self.settings.daily_loss_limit) * 100,
            "can_trade": self.can_trade()[0],
            "last_reset": self.last_reset.isoformat()
        }
