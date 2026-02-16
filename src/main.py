"""
Polymarket AI Trading Bot - Main Entry Point
Starts and coordinates all bot components
"""
import sys
import signal
from pathlib import Path
from loguru import logger
from threading import Thread
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from src.monitoring.logger import setup_logging
from src.trading.engine import TradingEngine
from src.telegram.bot import TradingTelegramBot


class PolymarketTradingBot:
    """Main application class"""

    def __init__(self):
        """Initialize the bot"""
        print("🚀 Polymarket AI Trading Bot")
        print("=" * 50)

        # Setup logging
        setup_logging()
        logger.info("Starting Polymarket AI Trading Bot...")

        # Load settings
        self.settings = get_settings()

        # Display mode
        mode = "PAPER TRADING" if self.settings.paper_trading else "⚠️  LIVE TRADING"
        logger.info(f"Mode: {mode}")

        if not self.settings.paper_trading:
            logger.warning("⚠️  WARNING: LIVE TRADING MODE - REAL MONEY AT RISK!")
            logger.warning("⚠️  Press Ctrl+C within 10 seconds to abort...")
            import time
            time.sleep(10)

        # Initialize components
        self.trading_engine = TradingEngine()
        self.telegram_bot = TradingTelegramBot(trading_engine=self.trading_engine)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        logger.info("✅ All components initialized")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal")
        self.shutdown()
        sys.exit(0)

    def start(self):
        """Start the bot"""
        try:
            logger.info("Starting all components...")

            # Start Telegram bot in separate thread
            telegram_thread = Thread(
                target=self.telegram_bot.start,
                daemon=True
            )
            telegram_thread.start()
            logger.info("✅ Telegram bot started")

            # Send startup notification
            asyncio.run(
                self.telegram_bot.send_notification(
                    "🤖 *Bot Started*\n\n"
                    f"Mode: {'PAPER TRADING' if self.settings.paper_trading else 'LIVE TRADING'}\n"
                    f"Balance: ${self.settings.initial_balance:.2f}\n"
                    f"Max Position: ${self.settings.max_position_size:.2f}\n"
                    f"Daily Loss Limit: ${self.settings.daily_loss_limit:.2f}\n\n"
                    "Bot is now monitoring markets 24/7!"
                )
            )

            # Start trading engine (blocking)
            logger.info("✅ Starting trading engine...")
            self.trading_engine.start()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.shutdown()

        except Exception as e:
            logger.error(f"Fatal error: {e}")
            self.shutdown()
            raise

    def shutdown(self):
        """Shutdown the bot gracefully"""
        logger.info("Shutting down...")

        try:
            # Stop trading engine
            if hasattr(self, 'trading_engine'):
                self.trading_engine.stop()

            # Stop Telegram bot
            if hasattr(self, 'telegram_bot'):
                self.telegram_bot.stop()

            # Send shutdown notification
            if hasattr(self, 'telegram_bot'):
                asyncio.run(
                    self.telegram_bot.send_notification("🛑 *Bot Stopped*")
                )

            logger.info("✅ Shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def main():
    """Main entry point"""
    try:
        bot = PolymarketTradingBot()
        bot.start()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
