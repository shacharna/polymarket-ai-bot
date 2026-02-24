"""
Risk Management System - Strict Mode
Enforces hard risk limits. No trade is allowed without risk approval.

Rules:
  1. Max 0.5-1% risk per trade
  2. Max daily loss 1-2% of equity
  3. Max drawdown 10% from peak equity (bot pauses entirely)
  4. Pause after consecutive losses
  5. Every trade must pass risk_approve() before execution
"""
from typing import Dict, Tuple
from datetime import datetime, timedelta
from loguru import logger
from config.settings import get_settings


class RiskManager:
    """Strict risk manager - every trade must be approved"""

    def __init__(self):
        self.settings = get_settings()

        # Daily tracking
        self.daily_loss = 0.0
        self.daily_profit = 0.0
        self.daily_trades = 0
        self.last_reset = datetime.now()

        # Consecutive loss tracking
        self.consecutive_losses = 0
        self.loss_pause_active = False

        # Drawdown tracking
        self.peak_equity = 0.0  # Set on first account check
        self.drawdown_pause_active = False

        # PDT tracking
        self.day_trades_5d = []  # type: list

        # Trailing stops: symbol -> {peak_price, activated}
        self.trailing_stops = {}  # type: Dict[str, Dict]

        logger.info(
            f"Risk Manager initialized | STRICT MODE | "
            f"Risk/trade: {self.settings.min_risk_per_trade_pct*100:.1f}-{self.settings.risk_per_trade_pct*100:.1f}% | "
            f"Daily limit: {self.settings.daily_loss_limit_pct*100:.1f}% | "
            f"Max drawdown: {self.settings.max_drawdown_pct*100:.0f}% | "
            f"Pause after {self.settings.max_consecutive_losses} consecutive losses"
        )

    # ── Core Risk Gate ──

    def risk_approve(self, equity, buying_power, position_size_usd, price, symbol):
        # type: (float, float, float, float, str) -> Tuple[bool, float, str]
        """
        THE SINGLE GATE: Every trade MUST pass through here.
        Returns (approved, adjusted_size, reason).
        No trade is allowed without this returning True.
        """
        # 1. Check if trading is allowed at all
        can_trade, reason = self.can_trade(equity)
        if not can_trade:
            return False, 0, reason

        # 2. Check drawdown
        dd_ok, dd_reason = self.check_drawdown(equity)
        if not dd_ok:
            return False, 0, dd_reason

        # 3. Check consecutive loss pause
        if self.loss_pause_active:
            return False, 0, (
                f"PAUSED: {self.consecutive_losses} consecutive losses. "
                f"Waiting for reset (next trading day or manual /resume)."
            )

        # 4. Check PDT
        pdt_ok, pdt_msg = self.check_pdt_limit()
        if not pdt_ok:
            return False, 0, pdt_msg

        # 5. Enforce max risk per trade (0.5-1% of equity)
        max_risk_usd = equity * self.settings.risk_per_trade_pct
        if position_size_usd > max_risk_usd:
            logger.warning(
                f"Position ${position_size_usd:.2f} exceeds "
                f"{self.settings.risk_per_trade_pct*100:.1f}% risk limit "
                f"(${max_risk_usd:.2f}), capping"
            )
            position_size_usd = max_risk_usd

        # 6. Enforce max position % of equity
        max_from_equity = equity * self.settings.max_position_pct
        if position_size_usd > max_from_equity:
            position_size_usd = max_from_equity

        # 7. Enforce absolute max
        if position_size_usd > self.settings.max_position_size:
            position_size_usd = self.settings.max_position_size

        # 8. Check buying power
        if position_size_usd > buying_power:
            return False, 0, f"Insufficient buying power (${buying_power:.2f})"

        # 9. Minimum viable trade
        if position_size_usd < 10.0:
            return False, 0, "Position size too small (min $10)"

        if price > 0 and int(position_size_usd / price) <= 0:
            return False, 0, f"Cannot afford even 1 share of {symbol} at ${price:.2f}"

        position_size_usd = round(position_size_usd, 2)
        return True, position_size_usd, "RISK APPROVED"

    # ── Trading Permission Checks ──

    def can_trade(self, current_equity=None):
        # type: (float) -> Tuple[bool, str]
        """Check if trading is allowed based on daily limits"""
        self.reset_daily_stats()

        # Daily loss limit (1-2% of equity)
        if current_equity:
            dynamic_limit = current_equity * self.settings.daily_loss_limit_pct
        else:
            dynamic_limit = self.settings.daily_loss_limit

        if abs(self.daily_loss) >= dynamic_limit:
            return False, (
                f"DAILY LOSS LIMIT: ${abs(self.daily_loss):.2f} lost today "
                f"(limit: ${dynamic_limit:.2f} = {self.settings.daily_loss_limit_pct*100:.1f}% of equity)"
            )

        # Max daily trades
        if self.daily_trades >= self.settings.max_daily_trades:
            return False, f"Max daily trades reached ({self.settings.max_daily_trades})"

        return True, "Trading allowed"

    def check_drawdown(self, current_equity):
        # type: (float) -> Tuple[bool, str]
        """
        Check max drawdown from peak equity.
        If drawdown exceeds max_drawdown_pct (10%), pause ALL trading.
        """
        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # Skip check if peak not yet established
        if self.peak_equity <= 0:
            self.peak_equity = current_equity
            return True, "OK"

        # Calculate drawdown
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        max_dd = self.settings.max_drawdown_pct

        if drawdown >= max_dd:
            self.drawdown_pause_active = True
            return False, (
                f"MAX DRAWDOWN BREACHED: {drawdown*100:.1f}% from peak "
                f"(${self.peak_equity:.2f} -> ${current_equity:.2f}). "
                f"Limit: {max_dd*100:.0f}%. ALL TRADING PAUSED."
            )

        if drawdown >= max_dd * 0.7:
            logger.warning(
                f"Drawdown warning: {drawdown*100:.1f}% from peak "
                f"(${self.peak_equity:.2f}). Limit: {max_dd*100:.0f}%"
            )

        self.drawdown_pause_active = False
        return True, f"Drawdown: {drawdown*100:.1f}%"

    # ── Position Sizing ──

    def calculate_position_size(self, confidence, buying_power, current_equity, ai_suggested_size=None):
        # type: (int, float, float, float) -> float
        """
        Calculate position size strictly within 0.5-1% risk per trade.
        Confidence scales within that range, NOT beyond it.
        """
        min_pct = self.settings.min_risk_per_trade_pct  # 0.5%
        max_pct = self.settings.risk_per_trade_pct       # 1.0%

        # Scale linearly: low confidence = 0.5%, high confidence = 1.0%
        if confidence <= 50:
            pct = min_pct
        elif confidence >= 90:
            pct = max_pct
        else:
            # Linear interpolation between 50-90 confidence
            ratio = (confidence - 50) / 40.0
            pct = min_pct + ratio * (max_pct - min_pct)

        position_size = current_equity * pct

        # Hard caps
        position_size = min(position_size, self.settings.max_position_size)
        position_size = min(position_size, buying_power * 0.95)
        position_size = round(max(position_size, 0), 2)

        logger.debug(
            f"Position size: ${position_size:.2f} "
            f"({pct*100:.2f}% of ${current_equity:.2f} equity, "
            f"confidence: {confidence}%)"
        )
        return position_size

    def calculate_qty(self, position_size_usd, price):
        # type: (float, float) -> int
        """Calculate number of shares to buy"""
        if price <= 0:
            return 0
        qty = int(position_size_usd / price)
        return max(qty, 1) if position_size_usd >= price else 0

    # ── Trade Recording ──

    def record_trade(self, profit_loss):
        # type: (float,) -> None
        """Record a completed trade and track consecutive losses"""
        if profit_loss < 0:
            self.daily_loss += profit_loss
            self.consecutive_losses += 1
            logger.warning(
                f"Trade LOSS: ${profit_loss:.2f} | "
                f"Consecutive losses: {self.consecutive_losses}/{self.settings.max_consecutive_losses}"
            )

            # Check consecutive loss limit
            if self.consecutive_losses >= self.settings.max_consecutive_losses:
                self.loss_pause_active = True
                logger.error(
                    f"CONSECUTIVE LOSS LIMIT: {self.consecutive_losses} losses in a row. "
                    f"TRADING PAUSED. Use /resume to reset."
                )
        else:
            self.daily_profit += profit_loss
            self.consecutive_losses = 0  # Reset on any win
            self.loss_pause_active = False
            logger.info(f"Trade PROFIT: ${profit_loss:+.2f}")

        self.daily_trades += 1
        daily_pnl = self.daily_loss + self.daily_profit
        logger.info(
            f"Daily: {self.daily_trades} trades | "
            f"P&L: ${daily_pnl:+.2f} | "
            f"Consecutive losses: {self.consecutive_losses}"
        )

    def reset_consecutive_losses(self):
        """Manual reset (via /resume command)"""
        self.consecutive_losses = 0
        self.loss_pause_active = False
        self.drawdown_pause_active = False
        logger.info("Consecutive loss counter and drawdown pause RESET manually")

    # ── PDT Rule ──

    def check_pdt_limit(self):
        # type: () -> Tuple[bool, str]
        """Check Pattern Day Trader rule (3 day trades per 5 business days if < $25k)"""
        now = datetime.now()
        five_days_ago = now - timedelta(days=7)
        recent = [dt for dt in self.day_trades_5d if dt > five_days_ago]
        count = len(recent)

        if count >= 3:
            return False, f"PDT limit: {count}/3 day trades used. Cannot day trade."
        elif count == 2:
            return True, f"PDT warning: {count}/3 day trades. 1 remaining."
        return True, f"PDT OK: {count}/3 day trades used."

    def record_day_trade(self):
        """Record a day trade"""
        self.day_trades_5d.append(datetime.now())

    # ── Daily Reset ──

    def reset_daily_stats(self):
        """Reset daily statistics at midnight"""
        now = datetime.now()
        if now.date() > self.last_reset.date():
            logger.info("Resetting daily statistics")
            self.daily_loss = 0.0
            self.daily_profit = 0.0
            self.daily_trades = 0
            self.last_reset = now

            # Also reset consecutive losses on new day
            if self.loss_pause_active:
                logger.info("New trading day - resetting consecutive loss pause")
                self.consecutive_losses = 0
                self.loss_pause_active = False

            # Clean old PDT records
            cutoff = now - timedelta(days=7)
            self.day_trades_5d = [dt for dt in self.day_trades_5d if dt > cutoff]

    # ── Trailing Stops ──

    def update_trailing_stop(self, symbol, entry_price, current_price, position_type):
        # type: (str, float, float, str) -> Tuple[bool, str]
        """Update and check trailing stop"""
        if not self.settings.trailing_stop_enabled:
            return False, ""

        activation = self.settings.trailing_stop_activation
        distance = self.settings.trailing_stop_distance

        is_long = position_type.upper() in ("BUY", "LONG")
        if is_long:
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price

        if symbol not in self.trailing_stops:
            self.trailing_stops[symbol] = {"peak_price": current_price, "activated": False}

        ts = self.trailing_stops[symbol]

        # Update peak
        if is_long:
            if current_price > ts["peak_price"]:
                ts["peak_price"] = current_price
        else:
            if current_price < ts["peak_price"]:
                ts["peak_price"] = current_price

        # Activate
        if not ts["activated"] and profit_pct >= activation:
            ts["activated"] = True
            logger.info(f"Trailing stop ACTIVATED for {symbol} at {profit_pct*100:.1f}%")

        # Check trigger
        if ts["activated"]:
            if is_long:
                trail_price = ts["peak_price"] * (1 - distance)
                if current_price <= trail_price:
                    return True, (
                        f"Trailing stop: ${current_price:.2f} below "
                        f"${trail_price:.2f} (peak ${ts['peak_price']:.2f})"
                    )
            else:
                trail_price = ts["peak_price"] * (1 + distance)
                if current_price >= trail_price:
                    return True, (
                        f"Trailing stop: ${current_price:.2f} above "
                        f"${trail_price:.2f} (peak ${ts['peak_price']:.2f})"
                    )

        return False, ""

    def clear_trailing_stop(self, symbol):
        # type: (str,) -> None
        """Remove trailing stop tracking"""
        self.trailing_stops.pop(symbol, None)

    # ── Metrics ──

    def get_risk_metrics(self):
        # type: () -> Dict
        """Get current risk metrics for Telegram /risk command"""
        pdt_ok, pdt_msg = self.check_pdt_limit()
        can_trade, trade_msg = self.can_trade()

        daily_pnl = self.daily_loss + self.daily_profit
        drawdown = 0.0
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - (self.peak_equity + daily_pnl)) / self.peak_equity

        return {
            "daily_pnl": daily_pnl,
            "daily_loss": self.daily_loss,
            "daily_profit": self.daily_profit,
            "daily_trades": self.daily_trades,
            "max_daily_trades": self.settings.max_daily_trades,
            "can_trade": can_trade,
            "trade_status": trade_msg,
            "pdt_ok": pdt_ok,
            "pdt_status": pdt_msg,
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_losses": self.settings.max_consecutive_losses,
            "loss_pause_active": self.loss_pause_active,
            "peak_equity": self.peak_equity,
            "drawdown_pct": drawdown * 100,
            "max_drawdown_pct": self.settings.max_drawdown_pct * 100,
            "drawdown_pause_active": self.drawdown_pause_active,
            "risk_per_trade": f"{self.settings.min_risk_per_trade_pct*100:.1f}-{self.settings.risk_per_trade_pct*100:.1f}%",
            "daily_loss_limit": f"{self.settings.daily_loss_limit_pct*100:.1f}%",
            "trailing_stops_active": sum(
                1 for ts in self.trailing_stops.values() if ts["activated"]
            ),
            "stop_loss_pct": self.settings.stop_loss_pct,
            "take_profit_pct": self.settings.take_profit_pct,
            "last_reset": self.last_reset.isoformat(),
        }
