"""
Aggressive Stock Trading Bot - Main Entry Point
Trades US stocks via Alpaca with AI-powered aggressive strategies
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


class StockTradingBot:
    """Main application class"""

    def __init__(self):
        """Initialize the bot"""
        print("Aggressive Stock Trading Bot")
        print("=" * 50)

        # Setup logging
        setup_logging()
        logger.info("Starting Aggressive Stock Trading Bot...")

        # Load settings
        self.settings = get_settings()

        # Display mode
        paper = "paper" in self.settings.alpaca_base_url
        mode = "PAPER TRADING" if paper else "LIVE TRADING"
        logger.info(f"Mode: {mode} | Strategy: {self.settings.trading_mode.upper()}")

        if not paper:
            logger.warning("WARNING: LIVE TRADING MODE - REAL MONEY AT RISK!")
            logger.warning("Press Ctrl+C within 10 seconds to abort...")
            import time
            time.sleep(10)

        # Initialize components
        self.trading_engine = TradingEngine()
        self.telegram_bot = TradingTelegramBot(trading_engine=self.trading_engine)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        logger.info("All components initialized")

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
                daemon=True,
            )
            telegram_thread.start()
            logger.info("Telegram bot started")

            # Send startup notification
            paper = "paper" in self.settings.alpaca_base_url
            mode = "PAPER" if paper else "LIVE"
            watchlist = ", ".join(self.settings.get_watchlist_symbols()[:5])

            asyncio.run(
                self.telegram_bot.send_notification(
                    f"*Bot Started*\n\n"
                    f"Mode: {mode} - {self.settings.trading_mode.upper()}\n"
                    f"Watchlist: {watchlist}...\n"
                    f"Scan Interval: {self.settings.scan_interval}s\n"
                    f"Max Positions: {self.settings.max_concurrent_positions}\n"
                    f"Confidence: {self.settings.confidence_threshold}%+\n\n"
                    f"Bot is now monitoring US stock markets!"
                )
            )

            # Start trading engine (blocking)
            logger.info("Starting trading engine...")
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
            if hasattr(self, "trading_engine"):
                self.trading_engine.stop()
            if hasattr(self, "telegram_bot"):
                self.telegram_bot.stop()
                asyncio.run(
                    self.telegram_bot.send_notification("*Bot Stopped*")
                )
            logger.info("Shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def main():
    """Main entry point"""
    try:
        bot = StockTradingBot()
        bot.start()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
