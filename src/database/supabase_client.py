"""
Supabase client for async trade history storage
Non-blocking writes with graceful failure handling
"""
import queue
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from supabase import create_client, Client

# Singleton instance
_supabase_client = None


class SupabaseClient:
    """
    Async Supabase client for trade history storage

    Key features:
    - Queue-based async writes (non-blocking)
    - Graceful failure handling (continues trading if DB fails)
    - Background thread for database operations
    - Automatic reconnection on network failures
    """

    def __init__(self, url, key):
        # type: (str, str) -> None
        """Initialize Supabase client with async writer"""
        self.url = url
        self.key = key
        self.client = None  # type: Optional[Client]
        self.enabled = True

        # Queue for async writes
        self.write_queue = queue.Queue(maxsize=1000)  # type: queue.Queue
        self.writer_thread = None  # type: Optional[threading.Thread]
        self.running = False

        # Statistics
        self.writes_success = 0
        self.writes_failed = 0

        # Initialize client
        self._connect()

        # Start background writer thread
        if self.enabled:
            self._start_writer_thread()

    def _connect(self):
        # type: () -> bool
        """Connect to Supabase"""
        try:
            self.client = create_client(self.url, self.key)
            logger.info("Connected to Supabase database")
            self.enabled = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            logger.warning("Database disabled - trade history will not be stored")
            self.enabled = False
            return False

    def _start_writer_thread(self):
        # type: () -> None
        """Start background thread for async writes"""
        if self.writer_thread and self.writer_thread.is_alive():
            return

        self.running = True
        self.writer_thread = threading.Thread(
            target=self._writer_loop,
            daemon=True,
            name="SupabaseWriter"
        )
        self.writer_thread.start()
        logger.info("Supabase writer thread started")

    def _writer_loop(self):
        # type: () -> None
        """Background loop that processes write queue"""
        while self.running:
            try:
                # Block for up to 1 second waiting for data
                operation = self.write_queue.get(timeout=1.0)

                # Process the write operation
                self._execute_write(operation)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in Supabase writer thread: {e}")

    def _execute_write(self, operation):
        # type: (Dict[str, Any]) -> bool
        """Execute a write operation to Supabase"""
        if not self.enabled or not self.client:
            self.writes_failed += 1
            return False

        try:
            table = operation.get("table")
            data = operation.get("data")

            if not table or not data:
                logger.error("Invalid write operation - missing table or data")
                self.writes_failed += 1
                return False

            # Execute insert
            result = self.client.table(table).insert(data).execute()

            if result:
                self.writes_success += 1
                logger.debug(f"Successfully wrote to {table}: {data.get('symbol', 'unknown')}")
                return True
            else:
                logger.error(f"Failed to write to {table}")
                self.writes_failed += 1
                return False

        except Exception as e:
            logger.error(f"Supabase write error: {e}")
            self.writes_failed += 1

            # Try to reconnect if connection issue
            if "connection" in str(e).lower() or "network" in str(e).lower():
                logger.info("Attempting to reconnect to Supabase...")
                self._connect()

            return False

    def log_trade(self, trade_data):
        # type: (Dict[str, Any]) -> bool
        """
        Queue trade data for async write to database

        Args:
            trade_data: Dictionary with trade details

        Returns:
            True if queued successfully, False if queue full
        """
        if not self.enabled:
            return False

        try:
            # Add to write queue (non-blocking)
            operation = {
                "table": "trades",
                "data": trade_data
            }

            self.write_queue.put_nowait(operation)
            logger.debug(f"Queued trade for DB write: {trade_data.get('symbol', 'unknown')}")
            return True

        except queue.Full:
            logger.error("Supabase write queue is full - dropping trade data")
            self.writes_failed += 1
            return False
        except Exception as e:
            logger.error(f"Error queueing trade data: {e}")
            self.writes_failed += 1
            return False

    def log_trade_entry(self, symbol, side, entry_price, quantity, position_value,
                       strategy, confidence, ai_setup_score=None, ai_risk_score=None,
                       ai_reasoning=None, indicators=None, paper_trading=True,
                       alpaca_order_id=None, bot_version=None):
        # type: (str, str, float, int, float, str, int, Optional[int], Optional[int], Optional[str], Optional[Dict], bool, Optional[str], Optional[str]) -> bool
        """
        Log trade entry with all relevant details

        Args:
            symbol: Stock ticker symbol
            side: 'buy' or 'sell'
            entry_price: Entry price per share
            quantity: Number of shares
            position_value: Total position value
            strategy: Strategy name ('momentum', 'mean_reversion', etc.)
            confidence: Strategy confidence (0-100)
            ai_setup_score: AI setup score (1-10)
            ai_risk_score: AI risk score (1-10)
            ai_reasoning: AI analysis reasoning
            indicators: Technical indicators dict (RSI, SMA, MACD, etc.)
            paper_trading: True if paper trading, False if live
            alpaca_order_id: Alpaca order ID
            bot_version: Bot version string

        Returns:
            True if queued successfully
        """
        trade_data = {
            "symbol": symbol,
            "side": side,
            "entry_price": float(entry_price),
            "entry_time": datetime.utcnow().isoformat(),
            "quantity": int(quantity),
            "position_value": float(position_value),
            "strategy": strategy,
            "confidence": int(confidence),
            "paper_trading": paper_trading,
        }

        # Add optional fields
        if ai_setup_score is not None:
            trade_data["ai_setup_score"] = int(ai_setup_score)
        if ai_risk_score is not None:
            trade_data["ai_risk_score"] = int(ai_risk_score)
        if ai_reasoning:
            trade_data["ai_reasoning"] = str(ai_reasoning)
        if alpaca_order_id:
            trade_data["alpaca_order_id"] = str(alpaca_order_id)
        if bot_version:
            trade_data["bot_version"] = str(bot_version)

        # Add technical indicators if provided
        if indicators:
            if "rsi" in indicators:
                trade_data["rsi_14"] = float(indicators["rsi"])
            if "sma_20" in indicators:
                trade_data["sma_20"] = float(indicators["sma_20"])
            if "sma_50" in indicators:
                trade_data["sma_50"] = float(indicators["sma_50"])
            if "macd" in indicators:
                trade_data["macd"] = float(indicators["macd"])
            if "macd_signal" in indicators:
                trade_data["macd_signal"] = float(indicators["macd_signal"])
            if "volume_avg" in indicators:
                trade_data["volume_avg"] = int(indicators["volume_avg"])
            if "volume_current" in indicators:
                trade_data["volume_current"] = int(indicators["volume_current"])

        return self.log_trade(trade_data)

    def update_trade_exit(self, symbol, entry_time, exit_price, exit_reason, profit_loss, profit_loss_pct):
        # type: (str, str, float, str, float, float) -> bool
        """
        Update trade with exit details

        Args:
            symbol: Stock ticker
            entry_time: Entry timestamp (ISO format) - used to find the trade
            exit_price: Exit price per share
            exit_reason: Reason for exit ('take_profit', 'stop_loss', etc.)
            profit_loss: Dollar P&L
            profit_loss_pct: Percentage P&L

        Returns:
            True if update queued successfully
        """
        if not self.enabled or not self.client:
            return False

        try:
            exit_time = datetime.utcnow()

            # Calculate hold duration
            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            hold_duration = int((exit_time - entry_dt).total_seconds() / 60)

            # Update via Supabase
            result = self.client.table("trades").update({
                "exit_price": float(exit_price),
                "exit_time": exit_time.isoformat(),
                "exit_reason": exit_reason,
                "profit_loss": float(profit_loss),
                "profit_loss_pct": float(profit_loss_pct),
                "hold_duration_minutes": hold_duration
            }).eq("symbol", symbol).eq("entry_time", entry_time).execute()

            if result:
                logger.info(f"Updated trade exit for {symbol}: {profit_loss_pct:+.2f}% ({exit_reason})")
                return True
            else:
                logger.error(f"Failed to update trade exit for {symbol}")
                return False

        except Exception as e:
            logger.error(f"Error updating trade exit: {e}")
            return False

    def update_open_trade_exit(self, symbol, exit_price, exit_reason, profit_loss, profit_loss_pct):
        # type: (str, float, str, float, float) -> bool
        """
        Update the most recent OPEN trade for a symbol with exit details.

        Matches by symbol WHERE exit_time IS NULL so we don't need the exact
        entry_time that was stored asynchronously by log_trade_entry().

        Called from engine.manage_positions() when a trailing stop or bracket
        order closes a position.
        """
        if not self.enabled or not self.client:
            return False

        try:
            exit_time = datetime.utcnow().isoformat()

            result = (
                self.client.table("trades")
                .update({
                    "exit_price": float(exit_price),
                    "exit_time": exit_time,
                    "exit_reason": exit_reason,
                    "profit_loss": float(profit_loss),
                    "profit_loss_pct": float(profit_loss_pct),
                })
                .eq("symbol", symbol)
                .is_("exit_time", "null")  # Only update open (not yet closed) trades
                .execute()
            )

            if result and result.data:
                logger.info(
                    f"DB exit recorded for {symbol}: "
                    f"{profit_loss_pct:+.2f}% (${profit_loss:+.2f}) | {exit_reason}"
                )
                return True
            else:
                logger.warning(
                    f"No open trade found in DB for {symbol} to update exit — "
                    f"entry may not have been logged yet"
                )
                return False

        except Exception as e:
            logger.error(f"Error updating trade exit for {symbol}: {e}")
            return False

    def get_stats(self):
        # type: () -> Dict[str, Any]
        """Get database statistics"""
        queue_size = self.write_queue.qsize()

        return {
            "enabled": self.enabled,
            "queue_size": queue_size,
            "writes_success": self.writes_success,
            "writes_failed": self.writes_failed,
            "success_rate": (
                self.writes_success / (self.writes_success + self.writes_failed) * 100
                if (self.writes_success + self.writes_failed) > 0 else 0
            )
        }

    def stop(self):
        # type: () -> None
        """Stop the writer thread and close connection"""
        logger.info("Stopping Supabase client...")
        self.running = False

        # Wait for queue to empty (max 10 seconds)
        if self.writer_thread:
            try:
                # Process remaining items
                timeout = 10.0
                start = datetime.now()
                while not self.write_queue.empty() and (datetime.now() - start).total_seconds() < timeout:
                    threading.Event().wait(0.1)

                self.writer_thread.join(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping writer thread: {e}")

        stats = self.get_stats()
        logger.info(
            f"Supabase client stopped. "
            f"Success: {stats['writes_success']}, Failed: {stats['writes_failed']}"
        )


def get_supabase_client(url=None, key=None):
    # type: (Optional[str], Optional[str]) -> Optional[SupabaseClient]
    """
    Get singleton Supabase client instance

    Args:
        url: Supabase project URL (required on first call)
        key: Supabase API key (required on first call)

    Returns:
        SupabaseClient instance or None if disabled
    """
    global _supabase_client

    if _supabase_client is None:
        if url and key:
            _supabase_client = SupabaseClient(url, key)
        else:
            logger.warning("Supabase credentials not provided - database disabled")
            return None

    return _supabase_client
