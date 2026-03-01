"""
Trade analytics and performance queries
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger


class TradeAnalytics:
    """Query utilities for trade history and performance analysis"""

    def __init__(self, supabase_client):
        # type: (Any) -> None
        """
        Initialize analytics with Supabase client

        Args:
            supabase_client: SupabaseClient instance
        """
        self.client = supabase_client.client if supabase_client else None
        self.enabled = supabase_client.enabled if supabase_client else False

    def get_recent_trades(self, limit=20, paper_trading=None):
        # type: (int, Optional[bool]) -> List[Dict[str, Any]]
        """
        Get recent trades

        Args:
            limit: Maximum number of trades to return
            paper_trading: Filter by paper/live (None = both)

        Returns:
            List of trade dictionaries
        """
        if not self.enabled or not self.client:
            return []

        try:
            query = self.client.table("trades").select("*").order("entry_time", desc=True).limit(limit)

            if paper_trading is not None:
                query = query.eq("paper_trading", paper_trading)

            result = query.execute()
            return result.data if result else []

        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []

    def get_performance_summary(self, days=30, paper_trading=None):
        # type: (int, Optional[bool]) -> Dict[str, Any]
        """
        Get performance summary for last N days

        Args:
            days: Number of days to analyze
            paper_trading: Filter by paper/live (None = both)

        Returns:
            Dictionary with performance metrics
        """
        if not self.enabled or not self.client:
            return {}

        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Query closed trades in date range
            query = (
                self.client.table("trades")
                .select("*")
                .gte("entry_time", start_date.isoformat())
                .lte("entry_time", end_date.isoformat())
                .not_.is_("exit_time", "null")  # Only closed trades
            )

            if paper_trading is not None:
                query = query.eq("paper_trading", paper_trading)

            result = query.execute()
            trades = result.data if result else []

            if not trades:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "total_profit_loss": 0.0,
                    "avg_profit_loss_pct": 0.0,
                    "avg_hold_minutes": 0,
                    "best_trade": None,
                    "worst_trade": None,
                }

            # Calculate metrics
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.get("profit_loss", 0) > 0)
            losing_trades = sum(1 for t in trades if t.get("profit_loss", 0) < 0)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

            total_profit_loss = sum(t.get("profit_loss", 0) for t in trades)
            avg_profit_loss_pct = (
                sum(t.get("profit_loss_pct", 0) for t in trades) / total_trades
                if total_trades > 0 else 0.0
            )
            avg_hold_minutes = (
                sum(t.get("hold_duration_minutes", 0) for t in trades) / total_trades
                if total_trades > 0 else 0
            )

            # Find best and worst trades
            best_trade = max(trades, key=lambda t: t.get("profit_loss", 0))
            worst_trade = min(trades, key=lambda t: t.get("profit_loss", 0))

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 2),
                "total_profit_loss": round(total_profit_loss, 2),
                "avg_profit_loss_pct": round(avg_profit_loss_pct, 2),
                "avg_hold_minutes": int(avg_hold_minutes),
                "best_trade": {
                    "symbol": best_trade.get("symbol"),
                    "profit_loss": round(best_trade.get("profit_loss", 0), 2),
                    "profit_loss_pct": round(best_trade.get("profit_loss_pct", 0), 2),
                    "strategy": best_trade.get("strategy"),
                },
                "worst_trade": {
                    "symbol": worst_trade.get("symbol"),
                    "profit_loss": round(worst_trade.get("profit_loss", 0), 2),
                    "profit_loss_pct": round(worst_trade.get("profit_loss_pct", 0), 2),
                    "strategy": worst_trade.get("strategy"),
                },
            }

        except Exception as e:
            logger.error(f"Error calculating performance summary: {e}")
            return {}

    def get_strategy_performance(self, days=30, paper_trading=None):
        # type: (int, Optional[bool]) -> Dict[str, Dict[str, Any]]
        """
        Get performance breakdown by strategy

        Args:
            days: Number of days to analyze
            paper_trading: Filter by paper/live (None = both)

        Returns:
            Dictionary mapping strategy names to performance metrics
        """
        if not self.enabled or not self.client:
            return {}

        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Query closed trades
            query = (
                self.client.table("trades")
                .select("*")
                .gte("entry_time", start_date.isoformat())
                .lte("entry_time", end_date.isoformat())
                .not_.is_("exit_time", "null")
            )

            if paper_trading is not None:
                query = query.eq("paper_trading", paper_trading)

            result = query.execute()
            trades = result.data if result else []

            if not trades:
                return {}

            # Group by strategy
            strategies = {}  # type: Dict[str, List[Dict[str, Any]]]
            for trade in trades:
                strategy = trade.get("strategy", "unknown")
                if strategy not in strategies:
                    strategies[strategy] = []
                strategies[strategy].append(trade)

            # Calculate metrics per strategy
            performance = {}
            for strategy, strategy_trades in strategies.items():
                total = len(strategy_trades)
                wins = sum(1 for t in strategy_trades if t.get("profit_loss", 0) > 0)
                losses = sum(1 for t in strategy_trades if t.get("profit_loss", 0) < 0)

                performance[strategy] = {
                    "total_trades": total,
                    "winning_trades": wins,
                    "losing_trades": losses,
                    "win_rate": round((wins / total * 100) if total > 0 else 0.0, 2),
                    "total_profit_loss": round(sum(t.get("profit_loss", 0) for t in strategy_trades), 2),
                    "avg_profit_loss_pct": round(
                        sum(t.get("profit_loss_pct", 0) for t in strategy_trades) / total if total > 0 else 0.0,
                        2
                    ),
                    "avg_confidence": round(
                        sum(t.get("confidence", 0) for t in strategy_trades) / total if total > 0 else 0.0,
                        1
                    ),
                }

            return performance

        except Exception as e:
            logger.error(f"Error calculating strategy performance: {e}")
            return {}

    def get_symbol_performance(self, symbol, paper_trading=None):
        # type: (str, Optional[bool]) -> Dict[str, Any]
        """
        Get performance for a specific symbol

        Args:
            symbol: Stock ticker
            paper_trading: Filter by paper/live (None = both)

        Returns:
            Dictionary with symbol performance metrics
        """
        if not self.enabled or not self.client:
            return {}

        try:
            query = (
                self.client.table("trades")
                .select("*")
                .eq("symbol", symbol)
                .not_.is_("exit_time", "null")
            )

            if paper_trading is not None:
                query = query.eq("paper_trading", paper_trading)

            result = query.execute()
            trades = result.data if result else []

            if not trades:
                return {"symbol": symbol, "total_trades": 0}

            total = len(trades)
            wins = sum(1 for t in trades if t.get("profit_loss", 0) > 0)
            losses = sum(1 for t in trades if t.get("profit_loss", 0) < 0)

            return {
                "symbol": symbol,
                "total_trades": total,
                "winning_trades": wins,
                "losing_trades": losses,
                "win_rate": round((wins / total * 100) if total > 0 else 0.0, 2),
                "total_profit_loss": round(sum(t.get("profit_loss", 0) for t in trades), 2),
                "avg_profit_loss_pct": round(
                    sum(t.get("profit_loss_pct", 0) for t in trades) / total if total > 0 else 0.0,
                    2
                ),
                "last_trade_time": max(t.get("entry_time") for t in trades),
            }

        except Exception as e:
            logger.error(f"Error getting symbol performance: {e}")
            return {}

    def get_daily_performance(self, days=7, paper_trading=None):
        # type: (int, Optional[bool]) -> List[Dict[str, Any]]
        """
        Get daily performance breakdown

        Args:
            days: Number of days to analyze
            paper_trading: Filter by paper/live (None = both)

        Returns:
            List of daily performance dictionaries
        """
        if not self.enabled or not self.client:
            return []

        try:
            # Use the trade_performance view
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            query = (
                self.client.table("trade_performance")
                .select("*")
                .gte("trade_date", start_date.date().isoformat())
                .lte("trade_date", end_date.date().isoformat())
                .order("trade_date", desc=True)
            )

            if paper_trading is not None:
                query = query.eq("paper_trading", paper_trading)

            result = query.execute()
            return result.data if result else []

        except Exception as e:
            logger.error(f"Error getting daily performance: {e}")
            return []

    def get_best_performing_symbols(self, limit=10, days=30, paper_trading=None):
        # type: (int, int, Optional[bool]) -> List[Dict[str, Any]]
        """
        Get best performing symbols by profit/loss

        Args:
            limit: Number of symbols to return
            days: Number of days to analyze
            paper_trading: Filter by paper/live (None = both)

        Returns:
            List of symbol performance dictionaries
        """
        if not self.enabled or not self.client:
            return []

        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Query closed trades
            query = (
                self.client.table("trades")
                .select("*")
                .gte("entry_time", start_date.isoformat())
                .lte("entry_time", end_date.isoformat())
                .not_.is_("exit_time", "null")
            )

            if paper_trading is not None:
                query = query.eq("paper_trading", paper_trading)

            result = query.execute()
            trades = result.data if result else []

            if not trades:
                return []

            # Group by symbol and calculate totals
            symbol_performance = {}  # type: Dict[str, Dict[str, Any]]
            for trade in trades:
                symbol = trade.get("symbol")
                if symbol not in symbol_performance:
                    symbol_performance[symbol] = {
                        "symbol": symbol,
                        "total_trades": 0,
                        "total_profit_loss": 0.0,
                    }
                symbol_performance[symbol]["total_trades"] += 1
                symbol_performance[symbol]["total_profit_loss"] += trade.get("profit_loss", 0)

            # Sort by profit/loss and take top N
            sorted_symbols = sorted(
                symbol_performance.values(),
                key=lambda x: x["total_profit_loss"],
                reverse=True
            )[:limit]

            return [
                {
                    "symbol": s["symbol"],
                    "total_trades": s["total_trades"],
                    "total_profit_loss": round(s["total_profit_loss"], 2),
                }
                for s in sorted_symbols
            ]

        except Exception as e:
            logger.error(f"Error getting best performing symbols: {e}")
            return []
