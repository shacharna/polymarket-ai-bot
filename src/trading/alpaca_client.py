"""
Alpaca Markets API Client
Handles all interactions with Alpaca for US stock trading
"""
from typing import Dict, List, Optional, Any
from loguru import logger
from alpaca_trade_api import REST
from alpaca_trade_api.rest import TimeFrame
from config.settings import get_settings
from datetime import datetime, timedelta
import pytz


class AlpacaClient:
    """Client for interacting with Alpaca Markets API"""

    def __init__(self):
        """Initialize Alpaca client"""
        self.settings = get_settings()
        self.client = None
        self._initialize_client()
        self.et_tz = pytz.timezone("US/Eastern")

    def _initialize_client(self):
        """Initialize the Alpaca REST client"""
        try:
            logger.debug(f"Initializing Alpaca client with base_url: {self.settings.alpaca_base_url}")
            self.client = REST(
                key_id=self.settings.alpaca_api_key,
                secret_key=self.settings.alpaca_secret_key,
                base_url=self.settings.alpaca_base_url,
            )
            # Verify connection
            account = self.client.get_account()
            logger.info(
                f"Alpaca client initialized | "
                f"Equity: ${float(account.equity):,.2f} | "
                f"Buying Power: ${float(account.buying_power):,.2f}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Alpaca client: {e}")
            raise

    def get_account(self) -> Optional[Dict[str, Any]]:
        """Get account information"""
        try:
            account = self.client.get_account()
            return {
                "equity": float(account.equity),
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "day_trade_count": int(account.daytrade_count),
                "pattern_day_trader": account.pattern_day_trader,
                "status": account.status,
            }
        except Exception as e:
            logger.error(f"Error fetching account: {e}")
            return None

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        try:
            positions = self.client.list_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "side": "long" if float(p.qty) > 0 else "short",
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc),
                    "change_today": float(p.change_today),
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def get_bars(
        self, symbol: str, timeframe: str = "15Min", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get OHLCV candlestick data

        Args:
            symbol: Stock ticker
            timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
            limit: Number of bars to fetch
        """
        try:
            tf_map = {
                "1Min": TimeFrame.Minute,
                "5Min": TimeFrame(5, "Min"),
                "15Min": TimeFrame(15, "Min"),
                "1Hour": TimeFrame.Hour,
                "1Day": TimeFrame.Day,
            }
            tf = tf_map.get(timeframe, TimeFrame(15, "Min"))

            end = datetime.now(pytz.UTC)
            start = end - timedelta(days=5)

            bars = self.client.get_bars(
                symbol, tf, start=start.isoformat(), end=end.isoformat(), limit=limit
            )

            return [
                {
                    "timestamp": bar.t.isoformat(),
                    "open": float(bar.o),
                    "high": float(bar.h),
                    "low": float(bar.l),
                    "close": float(bar.c),
                    "volume": int(bar.v),
                    "vwap": float(bar.vw) if hasattr(bar, "vw") else None,
                }
                for bar in bars
            ]
        except Exception as e:
            logger.error(f"Error fetching bars for {symbol}: {e}")
            return []

    def get_latest_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get real-time bid/ask/last price"""
        try:
            quote = self.client.get_latest_quote(symbol)
            return {
                "bid": float(quote.bp),
                "ask": float(quote.ap),
                "bid_size": int(quote.bs),
                "ask_size": int(quote.as_),
                "mid": (float(quote.bp) + float(quote.ap)) / 2,
            }
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def get_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get full market snapshot for a symbol"""
        try:
            snapshot = self.client.get_snapshot(symbol)
            daily_bar = snapshot.daily_bar
            prev_daily_bar = snapshot.prev_daily_bar
            latest_trade = snapshot.latest_trade

            current_price = float(latest_trade.p)
            prev_close = float(prev_daily_bar.c) if prev_daily_bar else current_price
            day_open = float(daily_bar.o) if daily_bar else current_price

            return {
                "symbol": symbol,
                "price": current_price,
                "day_open": day_open,
                "day_high": float(daily_bar.h) if daily_bar else current_price,
                "day_low": float(daily_bar.l) if daily_bar else current_price,
                "day_close": float(daily_bar.c) if daily_bar else current_price,
                "day_volume": int(daily_bar.v) if daily_bar else 0,
                "prev_close": prev_close,
                "change_pct": ((current_price - prev_close) / prev_close * 100)
                if prev_close
                else 0,
                "gap_pct": ((day_open - prev_close) / prev_close * 100)
                if prev_close
                else 0,
                "intraday_change_pct": ((current_price - day_open) / day_open * 100)
                if day_open
                else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching snapshot for {symbol}: {e}")
            return None

    def get_watchlist_snapshots(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batch get snapshots for all watchlist symbols"""
        try:
            snapshots = self.client.get_snapshots(symbols)
            result = {}
            for symbol, snapshot in snapshots.items():
                try:
                    daily_bar = snapshot.daily_bar
                    prev_daily_bar = snapshot.prev_daily_bar
                    latest_trade = snapshot.latest_trade

                    current_price = float(latest_trade.p)
                    prev_close = (
                        float(prev_daily_bar.c) if prev_daily_bar else current_price
                    )
                    day_open = float(daily_bar.o) if daily_bar else current_price

                    result[symbol] = {
                        "symbol": symbol,
                        "price": current_price,
                        "day_open": day_open,
                        "day_high": float(daily_bar.h) if daily_bar else current_price,
                        "day_low": float(daily_bar.l) if daily_bar else current_price,
                        "day_volume": int(daily_bar.v) if daily_bar else 0,
                        "prev_close": prev_close,
                        "change_pct": (
                            (current_price - prev_close) / prev_close * 100
                        )
                        if prev_close
                        else 0,
                        "gap_pct": ((day_open - prev_close) / prev_close * 100)
                        if prev_close
                        else 0,
                        "intraday_change_pct": (
                            (current_price - day_open) / day_open * 100
                        )
                        if day_open
                        else 0,
                    }
                except Exception as e:
                    logger.debug(f"Error processing snapshot for {symbol}: {e}")
                    continue

            logger.debug(f"Fetched snapshots for {len(result)} symbols")
            return result
        except Exception as e:
            logger.error(f"Error fetching watchlist snapshots: {e}")
            return {}

    def place_market_order(
        self, symbol: str, qty: float, side: str, paper_trading: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Place a market order"""
        try:
            if paper_trading and "paper" not in self.settings.alpaca_base_url:
                logger.warning("Paper trading enabled but using live URL!")
                return None

            order = self.client.submit_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                type="market",
                time_in_force="day",
            )

            logger.info(f"Market order placed: {side} {qty} {symbol} | ID: {order.id}")
            return {
                "order_id": order.id,
                "symbol": symbol,
                "side": side,
                "qty": float(qty),
                "type": "market",
                "status": order.status,
            }
        except Exception as e:
            logger.error(f"Error placing market order for {symbol}: {e}")
            return None

    def place_bracket_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        take_profit_price: float,
        stop_loss_price: float,
    ) -> Optional[Dict[str, Any]]:
        """Place a bracket order with take profit and stop loss"""
        try:
            order = self.client.submit_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                type="market",
                time_in_force="day",
                order_class="bracket",
                take_profit={"limit_price": round(take_profit_price, 2)},
                stop_loss={"stop_price": round(stop_loss_price, 2)},
            )

            logger.info(
                f"Bracket order: {side} {qty} {symbol} | "
                f"TP: ${take_profit_price:.2f} | SL: ${stop_loss_price:.2f}"
            )
            return {
                "order_id": order.id,
                "symbol": symbol,
                "side": side,
                "qty": float(qty),
                "type": "bracket",
                "status": order.status,
                "take_profit": take_profit_price,
                "stop_loss": stop_loss_price,
            }
        except Exception as e:
            logger.error(f"Error placing bracket order for {symbol}: {e}")
            return None

    def close_position(self, symbol: str) -> bool:
        """Close a specific position"""
        try:
            self.client.close_position(symbol)
            logger.info(f"Closed position: {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}")
            return False

    def close_all_positions(self) -> bool:
        """Emergency close all positions"""
        try:
            self.client.close_all_positions()
            logger.warning("CLOSED ALL POSITIONS")
            return True
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all pending orders"""
        try:
            self.client.cancel_all_orders()
            logger.info("Cancelled all pending orders")
            return True
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return False

    def is_market_open(self) -> bool:
        """Check if US stock market is currently open"""
        try:
            clock = self.client.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Error checking market clock: {e}")
            return False

    def get_market_clock(self) -> Optional[Dict[str, Any]]:
        """Get market clock details"""
        try:
            clock = self.client.get_clock()
            return {
                "is_open": clock.is_open,
                "next_open": clock.next_open.isoformat(),
                "next_close": clock.next_close.isoformat(),
            }
        except Exception as e:
            logger.error(f"Error fetching market clock: {e}")
            return None

    def get_most_active_stocks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get the most active stocks by volume and biggest movers.
        Scans the entire market for opportunities.
        """
        try:
            # Get all tradeable assets
            assets = self.client.list_assets(status="active", asset_class="us_equity")

            # Filter to common stocks that are tradeable and shortable
            tradeable = [
                a.symbol for a in assets
                if a.tradable and a.exchange in ("NYSE", "NASDAQ")
                and not a.symbol.isdigit()
                and len(a.symbol) <= 5
                and "." not in a.symbol
            ]

            # Get snapshots in batches (API limit)
            all_movers = []
            batch_size = 100

            for i in range(0, min(len(tradeable), 500), batch_size):
                batch = tradeable[i:i + batch_size]
                try:
                    snapshots = self.client.get_snapshots(batch)
                    for symbol, snap in snapshots.items():
                        try:
                            daily_bar = snap.daily_bar
                            prev_daily_bar = snap.prev_daily_bar
                            latest_trade = snap.latest_trade

                            if not daily_bar or not prev_daily_bar or not latest_trade:
                                continue

                            price = float(latest_trade.p)
                            prev_close = float(prev_daily_bar.c)
                            day_open = float(daily_bar.o)
                            volume = int(daily_bar.v)

                            if price < 2.0 or prev_close <= 0 or volume < 100000:
                                continue

                            change_pct = ((price - prev_close) / prev_close) * 100
                            gap_pct = ((day_open - prev_close) / prev_close) * 100
                            intraday_pct = ((price - day_open) / day_open) * 100 if day_open > 0 else 0

                            all_movers.append({
                                "symbol": symbol,
                                "price": price,
                                "day_open": day_open,
                                "day_high": float(daily_bar.h),
                                "day_low": float(daily_bar.l),
                                "day_volume": volume,
                                "prev_close": prev_close,
                                "change_pct": change_pct,
                                "gap_pct": gap_pct,
                                "intraday_change_pct": intraday_pct,
                                "abs_change": abs(change_pct),
                            })
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Error fetching snapshot batch: {e}")
                    continue

            # Sort by absolute change (biggest movers first)
            all_movers.sort(key=lambda x: x["abs_change"], reverse=True)

            # Return top movers
            result = all_movers[:limit]
            logger.info(
                f"Scanned market: found {len(all_movers)} active stocks, "
                f"returning top {len(result)} movers"
            )
            return result

        except Exception as e:
            logger.error(f"Error scanning market: {e}")
            return []

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders"""
        try:
            orders = self.client.list_orders(status="open")
            return [
                {
                    "order_id": o.id,
                    "symbol": o.symbol,
                    "side": o.side,
                    "qty": float(o.qty),
                    "type": o.type,
                    "status": o.status,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            return []
