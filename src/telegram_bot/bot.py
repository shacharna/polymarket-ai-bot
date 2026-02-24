"""
Telegram Bot for Stock Trading Bot Remote Control
Monitor positions, execute manual trades, and control the bot via Telegram
"""
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from loguru import logger
from config.settings import get_settings
from src.monitoring.security_logger import get_security_logger
from typing import Optional
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio


def require_authorization(func):
    """
    Security decorator to check if user is authorized.
    Blocks unauthorized users and logs security events.
    """
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        security_logger = get_security_logger()
        user_chat_id = str(update.message.chat.id)
        authorized_chat_id = str(self.settings.telegram_chat_id)
        username = update.message.from_user.username if update.message.from_user else None

        # Check authorization
        if user_chat_id != authorized_chat_id:
            security_logger.log_unauthorized_access(
                chat_id=user_chat_id,
                command=update.message.text,
                username=username
            )
            await update.message.reply_text(
                "⛔ Unauthorized. This bot is private."
            )
            return

        # Check rate limit
        command_name = func.__name__.replace("_command", "")
        allowed, message = self.check_rate_limit(command_name)
        if not allowed:
            wait_time = int(message.split("Wait ")[1].split("s")[0]) if "Wait" in message else 0
            security_logger.log_rate_limit_violation(
                command=command_name,
                remaining_time=wait_time,
                chat_id=user_chat_id
            )
            await update.message.reply_text(f"⏱️ {message}")
            return

        return await func(self, update, context)

    return wrapper


class TradingTelegramBot:
    """Telegram bot for controlling the stock trading system"""

    def __init__(self, trading_engine=None):
        self.settings = get_settings()
        self.trading_engine = trading_engine
        self.application: Optional[Application] = None
        self.is_running = False

        # Rate limiting for DDoS protection
        self.command_history = defaultdict(list)  # {command: [timestamps]}
        self.rate_limits = {
            "scan": (1, 300),       # 1 per 5 minutes (expensive AI operation)
            "closeall": (1, 60),    # 1 per minute (critical operation)
            "balance": (10, 60),    # 10 per minute
            "positions": (10, 60),  # 10 per minute
            "status": (20, 60),     # 20 per minute
            "trades": (10, 60),     # 10 per minute
            "stats": (5, 60),       # 5 per minute
        }

        logger.info("Telegram bot initialized with auth & rate limiting")

    def check_rate_limit(self, command_name):
        # type: (str) -> tuple[bool, str]
        """
        Check if command is within rate limit.
        Returns: (allowed: bool, message: str)
        """
        if command_name not in self.rate_limits:
            return True, ""

        max_calls, window_seconds = self.rate_limits[command_name]
        now = datetime.now()
        cutoff = now - timedelta(seconds=window_seconds)

        # Clean old timestamps
        self.command_history[command_name] = [
            ts for ts in self.command_history[command_name] if ts > cutoff
        ]

        # Check limit
        if len(self.command_history[command_name]) >= max_calls:
            wait_time = window_seconds - int((now - self.command_history[command_name][0]).total_seconds())
            return False, f"Rate limit exceeded. Wait {wait_time}s before retrying."

        # Record this call
        self.command_history[command_name].append(now)
        return True, ""

    @require_authorization
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        paper = "paper" in self.settings.alpaca_base_url
        mode = "PAPER TRADING" if paper else "LIVE TRADING"

        message = f"""*Aggressive Stock Trading Bot*

*Mode:* {mode}
*Strategy:* {self.settings.trading_mode.upper()}

*Commands:*
/status - Bot status & account info
/balance - Account balance details
/positions - Open stock positions
/trades - Recent trade history
/stats - Trading statistics
/scan - AI market scan (Yahoo Finance + web)
/watchlist - Current watchlist + AI picks
/strategies - Active strategies
/risk - Risk metrics & PDT status
/mode - Trading parameters
/pause - Pause trading
/resume - Resume trading
/closeall - Close all positions
/help - Show this message"""

        await update.message.reply_text(message, parse_mode="Markdown")

    @require_authorization
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            status = self.trading_engine.get_status()
            market = "OPEN" if status.get("market_open") else "CLOSED"
            paper = "PAPER" if status.get("paper") else "LIVE"

            message = f"""*Bot Status*

Status: {status.get('status', 'Unknown')}
Market: {market}
Mode: {paper} - {status.get('mode', '?')}
Equity: ${status.get('equity', 0):,.2f}
Buying Power: ${status.get('buying_power', 0):,.2f}
Daily P&L: ${status.get('daily_pnl', 0):+.2f}
Open Positions: {status.get('open_positions', 0)}
Trades Today: {status.get('trades_today', 0)}
Day Trades: {status.get('day_trade_count', 0)}/3"""

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            balance = self.trading_engine.get_balance()
            if "error" in balance:
                await update.message.reply_text(f"Error: {balance['error']}")
                return

            message = f"""*Account Balance*

Equity: ${balance.get('equity', 0):,.2f}
Cash: ${balance.get('cash', 0):,.2f}
Buying Power: ${balance.get('buying_power', 0):,.2f}
Portfolio Value: ${balance.get('portfolio_value', 0):,.2f}
Session P&L: ${balance.get('total_pnl', 0):+.2f}"""

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            positions = self.trading_engine.get_positions()

            if not positions:
                await update.message.reply_text("No open positions")
                return

            message = "*Open Positions*\n"
            total_pl = 0

            for pos in positions:
                pl = pos.get("unrealized_pl", 0)
                total_pl += pl
                pl_pct = pos.get("unrealized_plpc", 0) * 100
                emoji = "+" if pl >= 0 else ""

                message += f"""
*{pos['symbol']}* ({pos['side']})
  Qty: {pos['qty']:.0f} @ ${pos['avg_entry_price']:.2f}
  Now: ${pos['current_price']:.2f}
  P&L: {emoji}${pl:.2f} ({emoji}{pl_pct:.1f}%)
"""

            message += f"\n*Total Unrealized P&L: ${total_pl:+.2f}*"
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in positions command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            trades = self.trading_engine.get_recent_trades(limit=10)

            if not trades:
                await update.message.reply_text("No recent trades")
                return

            message = "*Recent Trades*\n"
            for i, t in enumerate(trades, 1):
                emoji = "BUY" if t.get("action") == "BUY" else "SELL"
                message += (
                    f"\n{i}. {emoji} {t.get('symbol', '?')} "
                    f"x{t.get('qty', 0):.0f} @ ${t.get('price', 0):.2f} "
                    f"| {t.get('confidence', 0)}% | {t.get('strategy', '?')}"
                )

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in trades command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            stats = self.trading_engine.get_statistics()

            message = f"""*Trading Statistics*

*Performance*
  Total Trades: {stats.get('total_trades', 0)}
  Winners: {stats.get('winning', 0)}
  Losers: {stats.get('losing', 0)}
  Win Rate: {stats.get('win_rate', 0):.1f}%

*P&L*
  Total: ${stats.get('total_pnl', 0):+.2f}
  Avg Win: ${stats.get('avg_win', 0):+.2f}
  Avg Loss: ${stats.get('avg_loss', 0):+.2f}
  Best: ${stats.get('best_trade', 0):+.2f}
  Worst: ${stats.get('worst_trade', 0):+.2f}

*Today*
  Trades: {stats.get('trades_today', 0)}
  P&L: ${stats.get('pnl_today', 0):+.2f}"""

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scan command - trigger AI market scan"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            await update.message.reply_text(
                "Scanning market (Yahoo Finance + Alpaca + AI)...\nThis may take 30-60 seconds."
            )

            # Run scan in background
            self.trading_engine.run_scan()

            # Get results
            summary = self.trading_engine.get_scan_summary()
            await update.message.reply_text(summary, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in scan command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def watchlist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /watchlist command"""
        try:
            # Show both fixed watchlist and AI-selected stocks
            symbols = self.settings.get_watchlist_symbols()
            message = f"*Fixed Watchlist ({len(symbols)} stocks)*\n"
            message += ", ".join(symbols)

            if self.trading_engine:
                ai_symbols = self.trading_engine.scanner.get_dynamic_watchlist()
                if ai_symbols:
                    # Filter out duplicates
                    new_symbols = [s for s in ai_symbols if s not in symbols]
                    if new_symbols:
                        message += f"\n\n*AI-Selected ({len(new_symbols)} stocks)*\n"
                        message += ", ".join(new_symbols)

                    message += f"\n\n*Total Universe: {len(symbols) + len(new_symbols)} stocks*"

            message += "\n\nUse /scan to refresh AI picks"

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def strategies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /strategies command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            strategies = self.trading_engine.get_strategies()
            message = "*Trading Strategies*\n\n"

            for name, enabled in strategies.items():
                status = "ON" if enabled else "OFF"
                message += f"  {name}: {status}\n"

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def risk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /risk command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            risk = self.trading_engine.get_risk_metrics()

            message = f"""*Risk Metrics*

*Daily*
  P&L: ${risk.get('daily_pnl', 0):+.2f}
  Trades: {risk.get('daily_trades', 0)} / {risk.get('max_daily_trades', 50)}
  Can Trade: {"Yes" if risk.get('can_trade') else "No"}

*PDT Status*
  {risk.get('pdt_status', 'Unknown')}

*Stops*
  Stop Loss: {risk.get('stop_loss_pct', 0)}%
  Take Profit: {risk.get('take_profit_pct', 0)}%
  Trailing Stops Active: {risk.get('trailing_stops_active', 0)}"""

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mode command - show trading parameters"""
        s = self.settings
        message = f"""*Trading Parameters*

Mode: {s.trading_mode.upper()}
Confidence Threshold: {s.confidence_threshold}%
Max Position: {s.max_position_pct*100:.0f}% of equity
Max Concurrent: {s.max_concurrent_positions}
Trades/Cycle: {s.max_trades_per_cycle}
Scan Interval: {s.scan_interval}s
Stop Loss: {s.stop_loss_pct}%
Take Profit: {s.take_profit_pct}%
Trailing Stop: {'ON' if s.trailing_stop_enabled else 'OFF'}
  Activation: +{s.trailing_stop_activation*100:.0f}%
  Distance: {s.trailing_stop_distance*100:.0f}%
AI-Only Trades: {'Yes' if s.allow_ai_only_trades else 'No'}
Strategy-Only: {'Yes' if s.allow_strategy_only_trades else 'No'}"""

        await update.message.reply_text(message, parse_mode="Markdown")

    @require_authorization
    async def closeall_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /closeall command - requires explicit confirmation"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("Trading engine not connected")
                return

            # Check if confirmation was provided
            if not context.args or context.args[0] != "CONFIRM":
                positions = self.trading_engine.get_positions()
                if not positions:
                    await update.message.reply_text("No open positions to close")
                    return

                total_value = sum(p.get('market_value', 0) for p in positions)
                total_pl = sum(p.get('unrealized_pl', 0) for p in positions)

                message = f"""⚠️ **WARNING: Close All Positions**

You have {len(positions)} open positions worth ${total_value:,.2f}
Unrealized P&L: ${total_pl:+.2f}

This will close ALL positions immediately at market price.

To confirm, send:
`/closeall CONFIRM`

⏰ You have 60 seconds to confirm."""

                await update.message.reply_text(message, parse_mode="Markdown")
                return

            # Confirmed - execute closeall
            result = self.trading_engine.alpaca.close_all_positions()
            if result:
                await update.message.reply_text("✅ All positions closed!")

                # Log critical operation
                security_logger = get_security_logger()
                username = update.message.from_user.username if update.message.from_user else "unknown"
                security_logger.log_critical_operation(
                    operation="CLOSE_ALL_POSITIONS",
                    user=f"@{username} (chat_id: {update.message.chat.id})",
                    details=f"Closed {len(positions)} positions"
                )
                logger.warning(f"🚨 All positions closed by user via Telegram")
            else:
                await update.message.reply_text("❌ Failed to close positions")

        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

    @require_authorization
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command"""
        if self.trading_engine:
            self.trading_engine.pause()
            await update.message.reply_text("Trading paused. Use /resume to continue.")

    @require_authorization
    async def resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        if self.trading_engine:
            self.trading_engine.resume()
            await update.message.reply_text("Trading resumed.")

    @require_authorization
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await self.start_command(update, context)

    async def send_notification(self, message: str):
        """Send notification to user"""
        try:
            if self.application:
                await self.application.bot.send_message(
                    chat_id=self.settings.telegram_chat_id,
                    text=message,
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    async def send_trade_alert(self, trade_info: dict):
        """Send trade execution alert"""
        emoji = "BUY" if trade_info.get("action") == "BUY" else "SELL"

        message = f"""*Trade Executed*

{emoji} *{trade_info.get('symbol', '?')}*
Qty: {trade_info.get('qty', 0)}
Price: ${trade_info.get('price', 0):.2f}
Size: ${trade_info.get('size_usd', 0):.2f}
Strategy: {trade_info.get('strategy', '?')}
Confidence: {trade_info.get('confidence', 0)}%
SL: ${trade_info.get('stop_loss', 0):.2f}
TP: ${trade_info.get('take_profit', 0):.2f}

{trade_info.get('reasoning', '')[:200]}"""

        await self.send_notification(message)

    def start(self):
        """Start the Telegram bot"""
        try:
            # Create event loop for this thread (required on Python 3.8)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.application = Application.builder().token(
                self.settings.telegram_bot_token
            ).build()

            # Register command handlers
            handlers = [
                ("start", self.start_command),
                ("help", self.help_command),
                ("status", self.status_command),
                ("balance", self.balance_command),
                ("positions", self.positions_command),
                ("trades", self.trades_command),
                ("stats", self.stats_command),
                ("scan", self.scan_command),
                ("watchlist", self.watchlist_command),
                ("strategies", self.strategies_command),
                ("risk", self.risk_command),
                ("mode", self.mode_command),
                ("pause", self.pause_command),
                ("resume", self.resume_command),
                ("closeall", self.closeall_command),
            ]

            for cmd, handler in handlers:
                self.application.add_handler(CommandHandler(cmd, handler))

            logger.info("Starting Telegram bot...")
            self.is_running = True
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)

        except Exception as e:
            logger.error(f"Error starting Telegram bot: {e}")
            raise

    def stop(self):
        """Stop the Telegram bot"""
        try:
            if self.application:
                logger.info("Stopping Telegram bot...")
                self.is_running = False
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")
