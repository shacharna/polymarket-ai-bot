"""
Risk Management System - Aggressive Mode
Enforces trading limits while allowing high-risk/high-reward trades
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
from config.settings import get_settings
import pytz


class RiskManager:
    """Manages risk with aggressive parameters for stock trading"""

    def __init__(self):
        """Initialize risk manager"""
        self.settings = get_settings()
        self.daily_loss = 0.0
        self.daily_profit = 0.0
        self.daily_trades = 0
        self.day_trades_5d = []  # Track day trades for PDT rule
        self.last_reset = datetime.now()

        # Trailing stop tracking: symbol -> {peak_price, activated}
        self.trailing_stops: Dict[str, Dict] = {}

        logger.info(
            f"Risk Manager initialized | Mode: {self.settings.trading_mode} | "
            f"Stop Loss: {self.settings.stop_loss_pct}% | "
            f"Take Profit: {self.settings.take_profit_pct}%"
        )

    def reset_daily_stats(self):
        """Reset daily statistics at midnight"""
        now = datetime.now()
        if now.date() > self.last_reset.date():
            logger.info("Resetting daily statistics")
            self.daily_loss = 0.0
            self.daily_profit = 0.0
            self.daily_trades = 0
            self.last_reset = now

            # Clean up old day trade records (keep last 5 business days)
            cutoff = now - timedelta(days=7)
            self.day_trades_5d = [
                dt for dt in self.day_trades_5d if dt > cutoff
            ]

    def can_trade(self, current_equity: float = None) -> tuple[bool, str]:
        """
        Check if trading is allowed

        Args:
            current_equity: Current account equity for dynamic limit calculation
        """
        self.reset_daily_stats()

        # Check daily loss limit
        if current_equity:
            dynamic_limit = current_equity * self.settings.daily_loss_limit_pct
        else:
            dynamic_limit = self.settings.daily_loss_limit

        if abs(self.daily_loss) >= dynamic_limit:
            return False, f"Daily loss limit reached (${abs(self.daily_loss):.2f} / ${dynamic_limit:.2f})"

        # Check maximum daily trades
        if self.daily_trades >= self.settings.max_daily_trades:
            return False, f"Maximum daily trades reached ({self.settings.max_daily_trades})"

        return True, "Trading allowed"

    def check_pdt_limit(self) -> tuple[bool, str]:
        """
        Check Pattern Day Trader rule.
        If account < $25k, limited to 3 day trades per 5 business days.

        Returns:
            (can_day_trade, warning_message)
        """
        # Count day trades in last 5 business days
        now = datetime.now()
        five_days_ago = now - timedelta(days=7)  # 7 calendar days ~ 5 business
        recent_day_trades = [
            dt for dt in self.day_trades_5d if dt > five_days_ago
        ]
        count = len(recent_day_trades)

        if count >= 3:
            return False, f"PDT limit: {count}/3 day trades used in 5 days. Cannot day trade."
        elif count == 2:
            return True, f"PDT warning: {count}/3 day trades used. 1 remaining."
        else:
            return True, f"PDT OK: {count}/3 day trades used."

    def record_day_trade(self):
        """Record a day trade (bought and sold same day)"""
        self.day_trades_5d.append(datetime.now())

    def validate_position_size(
        self,
        position_size_usd: float,
        buying_power: float,
        current_equity: float,
    ) -> tuple[bool, float, str]:
        """
        Validate and adjust position size for aggressive trading

        Args:
            position_size_usd: Requested position size in USD
            buying_power: Available buying power
            current_equity: Current account equity
        """
        # Minimum trade size
        min_size = 10.0
        if position_size_usd < min_size:
            return False, 0, f"Position size too small (min: ${min_size})"

        # Max percentage of equity per trade
        max_from_equity = current_equity * self.settings.max_position_pct
        if position_size_usd > max_from_equity:
            logger.warning(
                f"Position ${position_size_usd:.2f} exceeds "
                f"{self.settings.max_position_pct*100:.0f}% of equity, "
                f"capping at ${max_from_equity:.2f}"
            )
            position_size_usd = max_from_equity

        # Check absolute max
        if position_size_usd > self.settings.max_position_size:
            position_size_usd = self.settings.max_position_size

        # Check buying power
        if position_size_usd > buying_power:
            return False, 0, f"Insufficient buying power (${buying_power:.2f})"

        return True, round(position_size_usd, 2), "Position size valid"

    def calculate_position_size(
        self,
        confidence: int,
        buying_power: float,
        current_equity: float,
        ai_suggested_size: float = None,
    ) -> float:
        """
        Calculate aggressive position size based on confidence

        Aggressive tiers:
        - 55-65% confidence: 10% of equity
        - 65-80% confidence: 15% of equity
        - 80%+ confidence: 20-25% of equity
        """
        if confidence < 55:
            pct = 0.05
        elif confidence < 65:
            pct = 0.10
        elif confidence < 80:
            pct = 0.15
        else:
            pct = 0.20

        # Scale by AI suggested size (1-10 scale)
        if ai_suggested_size:
            multiplier = 0.7 + (ai_suggested_size / 10) * 0.6  # 0.7x to 1.3x
            pct *= multiplier

        position_size = current_equity * pct

        # Apply caps
        position_size = min(position_size, self.settings.max_position_size)
        position_size = min(position_size, buying_power * 0.95)  # Keep 5% buffer
        position_size = round(max(position_size, 0), 2)

        logger.debug(
            f"Position size: ${position_size:.2f} "
            f"(confidence: {confidence}%, equity: ${current_equity:.2f})"
        )
        return position_size

    def calculate_qty(self, position_size_usd: float, price: float) -> int:
        """Calculate number of shares to buy"""
        if price <= 0:
            return 0
        qty = int(position_size_usd / price)
        return max(qty, 1) if position_size_usd >= price else 0

    def should_stop_loss(
        self,
        entry_price: float,
        current_price: float,
        position_type: str,
    ) -> tuple[bool, str]:
        """Check if stop loss should trigger"""
        if position_type.upper() in ("BUY", "LONG"):
            loss_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            loss_pct = ((entry_price - current_price) / entry_price) * 100

        if loss_pct <= self.settings.stop_loss_pct:
            return True, f"Stop loss triggered: {loss_pct:.2f}% (limit: {self.settings.stop_loss_pct}%)"

        return False, ""

    def should_take_profit(
        self,
        entry_price: float,
        current_price: float,
        position_type: str,
    ) -> tuple[bool, str]:
        """Check if take profit target is reached"""
        if position_type.upper() in ("BUY", "LONG"):
            profit_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_pct = ((entry_price - current_price) / entry_price) * 100

        if profit_pct >= self.settings.take_profit_pct:
            return True, f"Take profit reached: {profit_pct:.2f}% (target: {self.settings.take_profit_pct}%)"

        return False, ""

    def update_trailing_stop(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        position_type: str,
    ) -> tuple[bool, str]:
        """
        Update and check trailing stop for a position.
        Activates after +activation_pct from entry, then trails at distance_pct below peak.
        """
        if not self.settings.trailing_stop_enabled:
            return False, ""

        activation = self.settings.trailing_stop_activation
        distance = self.settings.trailing_stop_distance

        # Calculate current profit
        if position_type.upper() in ("BUY", "LONG"):
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price

        # Initialize tracking
        if symbol not in self.trailing_stops:
            self.trailing_stops[symbol] = {
                "peak_price": current_price,
                "activated": False,
            }

        ts = self.trailing_stops[symbol]

        # Update peak price
        if position_type.upper() in ("BUY", "LONG"):
            if current_price > ts["peak_price"]:
                ts["peak_price"] = current_price
        else:
            if current_price < ts["peak_price"]:
                ts["peak_price"] = current_price

        # Check activation
        if not ts["activated"] and profit_pct >= activation:
            ts["activated"] = True
            logger.info(
                f"Trailing stop activated for {symbol} at "
                f"{profit_pct*100:.1f}% profit"
            )

        # Check if trailing stop triggered
        if ts["activated"]:
            if position_type.upper() in ("BUY", "LONG"):
                trail_price = ts["peak_price"] * (1 - distance)
                if current_price <= trail_price:
                    return True, (
                        f"Trailing stop: ${current_price:.2f} below trail "
                        f"${trail_price:.2f} (peak ${ts['peak_price']:.2f})"
                    )
            else:
                trail_price = ts["peak_price"] * (1 + distance)
                if current_price >= trail_price:
                    return True, (
                        f"Trailing stop: ${current_price:.2f} above trail "
                        f"${trail_price:.2f} (peak ${ts['peak_price']:.2f})"
                    )

        return False, ""

    def clear_trailing_stop(self, symbol: str):
        """Remove trailing stop tracking when position closes"""
        self.trailing_stops.pop(symbol, None)

    def record_trade(self, profit_loss: float):
        """Record a completed trade"""
        if profit_loss < 0:
            self.daily_loss += profit_loss
            logger.warning(f"Trade loss: ${profit_loss:.2f}")
        else:
            self.daily_profit += profit_loss
            logger.info(f"Trade profit: ${profit_loss:+.2f}")

        self.daily_trades += 1
        logger.info(
            f"Daily: {self.daily_trades} trades | "
            f"P&L: ${self.daily_loss + self.daily_profit:+.2f}"
        )

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        pdt_ok, pdt_msg = self.check_pdt_limit()
        can_trade, trade_msg = self.can_trade()

        return {
            "daily_pnl": self.daily_loss + self.daily_profit,
            "daily_loss": self.daily_loss,
            "daily_profit": self.daily_profit,
            "daily_trades": self.daily_trades,
            "max_daily_trades": self.settings.max_daily_trades,
            "can_trade": can_trade,
            "trade_status": trade_msg,
            "pdt_ok": pdt_ok,
            "pdt_status": pdt_msg,
            "trailing_stops_active": sum(
                1 for ts in self.trailing_stops.values() if ts["activated"]
            ),
            "stop_loss_pct": self.settings.stop_loss_pct,
            "take_profit_pct": self.settings.take_profit_pct,
            "last_reset": self.last_reset.isoformat(),
        }
