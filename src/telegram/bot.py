"""
Telegram Bot for Remote Control
Allows monitoring and controlling the trading bot via Telegram
"""
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from loguru import logger
from config.settings import get_settings
from typing import Optional, Any
import asyncio


class TradingTelegramBot:
    """Telegram bot for controlling the trading system"""

    def __init__(self, trading_engine=None):
        """
        Initialize Telegram bot

        Args:
            trading_engine: Reference to the trading engine
        """
        self.settings = get_settings()
        self.trading_engine = trading_engine
        self.application: Optional[Application] = None
        self.is_running = False

        logger.info("Telegram bot initialized")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖 *Polymarket AI Trading Bot*

Welcome! I'm your autonomous trading assistant.

*Available Commands:*
/status - Get bot status and balance
/balance - Check account balance
/positions - View open positions
/trades - Recent trade history
/stats - Trading statistics
/pause - Pause trading
/resume - Resume trading
/stop - Stop the bot
/strategies - View active strategies
/enable <strategy> - Enable a strategy
/disable <strategy> - Disable a strategy
/risk - View risk metrics
/help - Show this message

⚠️ *Current Mode:* {}

The bot is monitoring markets 24/7 and will notify you of all trades.
        """.format("PAPER TRADING" if self.settings.paper_trading else "LIVE TRADING")

        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown'
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            status = self.trading_engine.get_status()

            message = f"""
📊 *Bot Status*

🔹 Status: {status.get('status', 'Unknown')}
💰 Balance: ${status.get('balance', 0):.2f}
📈 Daily P&L: ${status.get('daily_pnl', 0):+.2f}
🎯 Open Positions: {status.get('open_positions', 0)}
📊 Trades Today: {status.get('trades_today', 0)}
⚡ Mode: {status.get('mode', 'Unknown')}

Last Update: {status.get('last_update', 'N/A')}
            """

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            balance = self.trading_engine.get_balance()

            message = f"""
💰 *Account Balance*

💵 USDC: ${balance.get('usdc', 0):.2f}
📊 In Positions: ${balance.get('in_positions', 0):.2f}
💎 Available: ${balance.get('available', 0):.2f}
📈 Total Value: ${balance.get('total', 0):.2f}

🎯 Initial: ${self.settings.initial_balance:.2f}
📊 P&L: ${balance.get('pnl', 0):+.2f} ({balance.get('pnl_pct', 0):+.2f}%)
            """

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            positions = self.trading_engine.get_positions()

            if not positions:
                await update.message.reply_text("📭 No open positions")
                return

            message = "📊 *Open Positions*\n\n"

            for i, pos in enumerate(positions, 1):
                message += f"""
*{i}. {pos.get('market', 'Unknown')[:50]}*
   Side: {pos.get('side', 'N/A')}
   Entry: ${pos.get('entry_price', 0):.4f}
   Current: ${pos.get('current_price', 0):.4f}
   Size: ${pos.get('size', 0):.2f}
   P&L: ${pos.get('pnl', 0):+.2f} ({pos.get('pnl_pct', 0):+.2f}%)
   Age: {pos.get('age_hours', 0):.1f}h

"""

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in positions command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            trades = self.trading_engine.get_recent_trades(limit=10)

            if not trades:
                await update.message.reply_text("📭 No recent trades")
                return

            message = "📜 *Recent Trades*\n\n"

            for i, trade in enumerate(trades, 1):
                pnl_emoji = "✅" if trade.get('pnl', 0) > 0 else "❌"
                message += f"""
{pnl_emoji} *{i}. {trade.get('market', 'Unknown')[:40]}*
   {trade.get('action', 'N/A')} @ ${trade.get('price', 0):.4f}
   Size: ${trade.get('size', 0):.2f}
   P&L: ${trade.get('pnl', 0):+.2f}
   Time: {trade.get('time', 'N/A')}

"""

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in trades command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            stats = self.trading_engine.get_statistics()

            message = f"""
📈 *Trading Statistics*

📊 *Performance*
   Total Trades: {stats.get('total_trades', 0)}
   Winning Trades: {stats.get('winning_trades', 0)}
   Losing Trades: {stats.get('losing_trades', 0)}
   Win Rate: {stats.get('win_rate', 0):.1f}%

💰 *Profit & Loss*
   Total P&L: ${stats.get('total_pnl', 0):+.2f}
   Avg Win: ${stats.get('avg_win', 0):.2f}
   Avg Loss: ${stats.get('avg_loss', 0):.2f}
   Best Trade: ${stats.get('best_trade', 0):+.2f}
   Worst Trade: ${stats.get('worst_trade', 0):+.2f}

📊 *Today*
   Trades: {stats.get('trades_today', 0)}
   P&L: ${stats.get('pnl_today', 0):+.2f}
   Win Rate: {stats.get('win_rate_today', 0):.1f}%
            """

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            self.trading_engine.pause()
            await update.message.reply_text("⏸️ Trading paused. Use /resume to continue.")

        except Exception as e:
            logger.error(f"Error in pause command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            self.trading_engine.resume()
            await update.message.reply_text("▶️ Trading resumed.")

        except Exception as e:
            logger.error(f"Error in resume command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def strategies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /strategies command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            strategies = self.trading_engine.get_strategies()

            message = "🎯 *Trading Strategies*\n\n"

            for name, enabled in strategies.items():
                status = "✅ Enabled" if enabled else "❌ Disabled"
                message += f"• {name}: {status}\n"

            message += "\nUse /enable <strategy> or /disable <strategy>"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in strategies command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def risk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /risk command"""
        try:
            if not self.trading_engine:
                await update.message.reply_text("❌ Trading engine not connected")
                return

            risk = self.trading_engine.get_risk_metrics()

            message = f"""
🛡️ *Risk Metrics*

📊 *Daily Limits*
   Loss: ${abs(risk.get('daily_loss', 0)):.2f} / ${risk.get('loss_limit', 0):.2f}
   Usage: {risk.get('loss_limit_used_pct', 0):.1f}%
   Trades: {risk.get('daily_trades', 0)} / 50

⚙️ *Position Limits*
   Max Size: ${risk.get('max_position_size', 0):.2f}
   Risk/Trade: {risk.get('risk_per_trade', 0):.1f}%

✅ *Status*
   Can Trade: {"Yes ✅" if risk.get('can_trade') else "No ❌"}
            """

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in risk command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await self.start_command(update, context)

    async def send_notification(self, message: str):
        """
        Send notification to user

        Args:
            message: Message to send
        """
        try:
            if self.application:
                await self.application.bot.send_message(
                    chat_id=self.settings.telegram_chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    async def send_trade_alert(self, trade_info: dict):
        """
        Send trade execution alert

        Args:
            trade_info: Trade information dictionary
        """
        emoji = "🟢" if trade_info.get('action') == 'BUY' else "🔴"

        message = f"""
{emoji} *Trade Executed*

Market: {trade_info.get('market', 'Unknown')[:60]}
Action: {trade_info.get('action', 'N/A')}
Price: ${trade_info.get('price', 0):.4f}
Size: ${trade_info.get('size', 0):.2f}
Strategy: {trade_info.get('strategy', 'N/A')}
Confidence: {trade_info.get('confidence', 0)}%

Reasoning: {trade_info.get('reasoning', 'N/A')[:200]}
        """

        await self.send_notification(message)

    def start(self):
        """Start the Telegram bot"""
        try:
            # Create application
            self.application = Application.builder().token(
                self.settings.telegram_bot_token
            ).build()

            # Add command handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("balance", self.balance_command))
            self.application.add_handler(CommandHandler("positions", self.positions_command))
            self.application.add_handler(CommandHandler("trades", self.trades_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("pause", self.pause_command))
            self.application.add_handler(CommandHandler("resume", self.resume_command))
            self.application.add_handler(CommandHandler("strategies", self.strategies_command))
            self.application.add_handler(CommandHandler("risk", self.risk_command))

            # Start polling
            logger.info("Starting Telegram bot...")
            self.is_running = True

            # Run in a separate thread
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
                # Application will stop when polling ends

        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")
