"""
Trading Engine - Aggressive Stock Trading
Coordinates all components: Alpaca, AI, strategies, risk management
"""
from typing import Dict, List, Optional, Any
from loguru import logger
from datetime import datetime
import time

from src.trading.alpaca_client import AlpacaClient
from src.agents.ai_agent import AITradingAgent
from src.agents.stock_scanner import StockScannerAgent
from src.trading.risk_manager import RiskManager
from src.trading.strategies import StrategyManager
from src.monitoring.logger import log_trade
from config.settings import get_settings


class TradingEngine:
    """Main trading engine for aggressive stock trading"""

    def __init__(self):
        """Initialize trading engine"""
        self.settings = get_settings()

        # Initialize components
        self.alpaca = AlpacaClient()
        self.ai_agent = AITradingAgent()
        self.scanner = StockScannerAgent()
        self.risk_manager = RiskManager()
        self.strategy_manager = StrategyManager()

        # State
        self.is_running = False
        self.is_paused = False
        self.trades = []
        self.start_time = datetime.now()

        # Cache to avoid redundant AI calls
        self._price_cache = {}  # type: Dict[str, Dict]

        logger.info(
            f"Trading Engine initialized | "
            f"Mode: {self.settings.trading_mode} | "
            f"Base watchlist: {len(self.settings.get_watchlist_symbols())} stocks | "
            f"AI Scanner: ENABLED"
        )

    def start(self):
        """Start the trading engine"""
        logger.info("Starting trading engine...")
        self.is_running = True
        self.is_paused = False
        self.run_trading_loop()

    def stop(self):
        """Stop the trading engine"""
        logger.info("Stopping trading engine...")
        self.is_running = False

    def pause(self):
        logger.info("Pausing trading...")
        self.is_paused = True

    def resume(self):
        logger.info("Resuming trading...")
        self.is_paused = False

    def run_trading_loop(self):
        """Main trading loop"""
        loop_count = 0

        while self.is_running:
            try:
                loop_count += 1

                if self.is_paused:
                    logger.debug("Trading paused, skipping")
                    time.sleep(30)
                    continue

                # Check market hours
                if self.settings.market_hours_only and not self.alpaca.is_market_open():
                    clock = self.alpaca.get_market_clock()
                    if clock:
                        logger.debug(
                            f"Market closed. Next open: {clock.get('next_open', '?')}"
                        )
                    time.sleep(60)
                    continue

                logger.debug(f"--- Trading loop #{loop_count} ---")

                # 1. Get account info
                account = self.alpaca.get_account()
                if not account:
                    logger.error("Failed to get account info")
                    time.sleep(30)
                    continue

                equity = account["equity"]
                buying_power = account["buying_power"]

                # 2. Check risk limits
                can_trade, reason = self.risk_manager.can_trade(equity)
                if not can_trade:
                    logger.warning(f"Cannot trade: {reason}")
                    time.sleep(60)
                    continue

                # 3. Dynamic stock scanning (AI + Yahoo Finance + Alpaca)
                symbols = self._get_trading_symbols()
                snapshots = self.alpaca.get_watchlist_snapshots(symbols)

                if not snapshots:
                    logger.warning("No snapshot data available")
                    time.sleep(self.settings.scan_interval)
                    continue

                logger.info(f"Trading {len(snapshots)} stocks (AI-selected + watchlist)")

                # 4. Find opportunities
                opportunities = self.find_opportunities(
                    snapshots, equity, buying_power
                )

                # 5. Execute trades
                if opportunities:
                    self.execute_opportunities(opportunities, equity, buying_power)

                # 6. Manage existing positions
                self.manage_positions()

                # Sleep between cycles
                time.sleep(self.settings.scan_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(30)

        logger.info("Trading engine stopped")

    def find_opportunities(
        self,
        snapshots: Dict[str, Dict],
        equity: float,
        buying_power: float,
    ) -> List[Dict[str, Any]]:
        """Find trading opportunities using strategies and AI"""
        opportunities = []

        # Get current positions to avoid doubling up
        current_positions = self.alpaca.get_positions()
        held_symbols = {p["symbol"] for p in current_positions}
        available_slots = self.settings.max_concurrent_positions - len(current_positions)

        if available_slots <= 0:
            logger.debug(f"Max positions reached ({len(current_positions)})")
            return []

        # Phase 1: Run strategies on all watchlist stocks (fast, no API calls)
        strategy_candidates = []
        for symbol, snapshot in snapshots.items():
            if symbol in held_symbols:
                continue

            bars = self.alpaca.get_bars(symbol, "15Min", 30)
            signals = self.strategy_manager.analyze_stock(snapshot, bars)

            if signals:
                best_signal = self.strategy_manager.get_best_signal(signals)
                if best_signal and best_signal.get("confidence", 0) >= self.settings.confidence_threshold:
                    strategy_candidates.append({
                        "symbol": symbol,
                        "snapshot": snapshot,
                        "bars": bars,
                        "signal": best_signal,
                    })

        # Phase 2: AI analysis on top candidates (limit to reduce API costs)
        # Also do a quick watchlist scan for AI-only opportunities
        ai_opportunities = []
        if self.settings.allow_ai_only_trades:
            try:
                ai_watchlist = self.ai_agent.analyze_watchlist(snapshots)
                for opp in ai_watchlist:
                    symbol = opp.get("symbol", "")
                    if (
                        symbol
                        and symbol not in held_symbols
                        and opp.get("confidence", 0) >= self.settings.confidence_threshold
                        and opp.get("action", "HOLD") != "HOLD"
                    ):
                        ai_opportunities.append({
                            "symbol": symbol,
                            "snapshot": snapshots.get(symbol, {}),
                            "ai_analysis": opp,
                            "signal_source": "ai_only",
                        })
            except Exception as e:
                logger.error(f"AI watchlist scan failed: {e}")

        # Phase 3: Combine signals
        # Strategy candidates get individual AI validation
        for candidate in strategy_candidates[:5]:  # Limit AI calls
            symbol = candidate["symbol"]
            try:
                ai_analysis = self.ai_agent.analyze_stock(
                    symbol, candidate["snapshot"], candidate["bars"]
                )

                signal = candidate["signal"]

                # Both agree -> highest conviction
                if (
                    ai_analysis.get("action") == signal.get("action")
                    and ai_analysis.get("confidence", 0) >= self.settings.confidence_threshold
                ):
                    opportunities.append({
                        "symbol": symbol,
                        "snapshot": candidate["snapshot"],
                        "signal": signal,
                        "ai_analysis": ai_analysis,
                        "signal_source": "combined",
                        "combined_confidence": (
                            signal.get("confidence", 0) + ai_analysis.get("confidence", 0)
                        ) // 2,
                    })
                # Strategy-only trade
                elif self.settings.allow_strategy_only_trades:
                    opportunities.append({
                        "symbol": symbol,
                        "snapshot": candidate["snapshot"],
                        "signal": signal,
                        "ai_analysis": ai_analysis,
                        "signal_source": "strategy_only",
                        "combined_confidence": signal.get("confidence", 0),
                    })
            except Exception as e:
                logger.error(f"AI analysis failed for {symbol}: {e}")
                if self.settings.allow_strategy_only_trades:
                    opportunities.append({
                        "symbol": symbol,
                        "snapshot": candidate["snapshot"],
                        "signal": candidate["signal"],
                        "ai_analysis": {"action": "HOLD", "confidence": 0},
                        "signal_source": "strategy_only",
                        "combined_confidence": candidate["signal"].get("confidence", 0),
                    })

        # Add AI-only opportunities that weren't already found by strategies
        strategy_symbols = {o["symbol"] for o in opportunities}
        for ai_opp in ai_opportunities:
            if ai_opp["symbol"] not in strategy_symbols:
                opportunities.append(ai_opp)

        logger.info(f"Found {len(opportunities)} opportunities")
        return opportunities

    def execute_opportunities(
        self,
        opportunities: List[Dict],
        equity: float,
        buying_power: float,
    ):
        """Execute the best trading opportunities"""
        # Sort by confidence
        opportunities_sorted = sorted(
            opportunities,
            key=lambda x: x.get("combined_confidence", x.get("ai_analysis", {}).get("confidence", 0)),
            reverse=True,
        )

        # Check how many slots we have
        current_positions = self.alpaca.get_positions()
        available_slots = self.settings.max_concurrent_positions - len(current_positions)
        max_this_cycle = min(self.settings.max_trades_per_cycle, available_slots)

        executed = 0
        for opp in opportunities_sorted:
            if executed >= max_this_cycle:
                break
            if self.execute_trade(opp, equity, buying_power):
                executed += 1

    def execute_trade(
        self,
        opportunity: Dict,
        equity: float,
        buying_power: float,
    ) -> bool:
        """Execute a single trade"""
        try:
            symbol = opportunity["symbol"]
            snapshot = opportunity.get("snapshot", {})
            price = snapshot.get("price", 0)

            if price <= 0:
                return False

            # Determine action and confidence
            ai = opportunity.get("ai_analysis", {})
            signal = opportunity.get("signal", ai)
            action = signal.get("action", ai.get("action", "HOLD"))
            confidence = signal.get("confidence", ai.get("confidence", 0))

            if action == "HOLD":
                return False

            # Calculate position size
            position_size_usd = self.risk_manager.calculate_position_size(
                confidence=confidence,
                buying_power=buying_power,
                current_equity=equity,
                ai_suggested_size=signal.get("position_size", ai.get("position_size")),
            )

            # Validate
            is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
                position_size_usd, buying_power, equity
            )
            if not is_valid:
                logger.warning(f"Invalid position for {symbol}: {reason}")
                return False

            position_size_usd = adjusted_size
            qty = self.risk_manager.calculate_qty(position_size_usd, price)

            if qty <= 0:
                logger.debug(f"Cannot afford {symbol} at ${price:.2f}")
                return False

            # Calculate stop loss and take profit prices for bracket order
            sl_pct = ai.get("stop_loss_pct", self.settings.stop_loss_pct)
            tp_pct = ai.get("take_profit_pct", self.settings.take_profit_pct)

            if action == "BUY":
                stop_loss_price = price * (1 + sl_pct / 100)  # sl_pct is negative
                take_profit_price = price * (1 + tp_pct / 100)
            else:
                stop_loss_price = price * (1 - sl_pct / 100)
                take_profit_price = price * (1 - tp_pct / 100)

            # Place bracket order (market order with TP/SL)
            side = "buy" if action == "BUY" else "sell"
            result = self.alpaca.place_bracket_order(
                symbol=symbol,
                qty=qty,
                side=side,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
            )

            if result:
                trade = {
                    "symbol": symbol,
                    "action": action,
                    "price": price,
                    "qty": qty,
                    "size_usd": qty * price,
                    "confidence": confidence,
                    "strategy": signal.get("strategy", "ai"),
                    "signal_source": opportunity.get("signal_source", "unknown"),
                    "reasoning": signal.get("reasoning", ai.get("reasoning", "")),
                    "order_id": result.get("order_id"),
                    "stop_loss": stop_loss_price,
                    "take_profit": take_profit_price,
                    "timestamp": datetime.now(),
                    "pnl": 0,
                }
                self.trades.append(trade)

                log_trade(
                    action=action,
                    market=symbol,
                    price=price,
                    size=qty * price,
                    confidence=confidence,
                )

                logger.info(
                    f"EXECUTED {action} {qty}x {symbol} @ ${price:.2f} "
                    f"(${qty*price:.2f}) | Conf: {confidence}% | "
                    f"SL: ${stop_loss_price:.2f} | TP: ${take_profit_price:.2f} | "
                    f"Source: {opportunity.get('signal_source', '?')}"
                )
                return True

        except Exception as e:
            logger.error(f"Error executing trade for {opportunity.get('symbol', '?')}: {e}")
        return False

    def manage_positions(self):
        """Monitor and manage open positions with trailing stops"""
        positions = self.alpaca.get_positions()

        for pos in positions:
            try:
                symbol = pos["symbol"]
                entry_price = pos["avg_entry_price"]
                current_price = pos["current_price"]
                pnl_pct = pos["unrealized_plpc"] * 100

                # Check trailing stop
                should_trail, trail_reason = self.risk_manager.update_trailing_stop(
                    symbol=symbol,
                    entry_price=entry_price,
                    current_price=current_price,
                    position_type=pos["side"],
                )

                if should_trail:
                    logger.info(f"TRAILING STOP {symbol}: {trail_reason}")
                    if self.alpaca.close_position(symbol):
                        self.risk_manager.clear_trailing_stop(symbol)
                        self.risk_manager.record_trade(pos["unrealized_pl"])
                        self.risk_manager.record_day_trade()
                        logger.info(
                            f"Closed {symbol} via trailing stop | P&L: ${pos['unrealized_pl']:+.2f}"
                        )
                    continue

                # Note: Bracket orders already have SL/TP built in via Alpaca
                # The trailing stop above is an enhancement on top of that

            except Exception as e:
                logger.error(f"Error managing position {pos.get('symbol', '?')}: {e}")

    # ── Dynamic Stock Scanner ──

    def _get_trading_symbols(self):
        # type: () -> List[str]
        """Get symbols to trade: AI-scanned + fixed watchlist"""
        # Always include fixed watchlist
        symbols = list(self.settings.get_watchlist_symbols())

        # Run AI scanner if needed (every 15 minutes)
        if self.scanner.needs_rescan():
            try:
                logger.info("Running AI market scan (Yahoo Finance + web + Alpaca)...")

                # Get Alpaca market movers
                alpaca_movers = self.alpaca.get_most_active_stocks(limit=50)

                # Run full scan (Yahoo Finance + news + AI analysis)
                picks = self.scanner.full_market_scan(alpaca_movers=alpaca_movers)

                # Add AI-selected symbols
                for pick in picks:
                    sym = pick.get("symbol", "")
                    if sym and sym not in symbols:
                        symbols.append(sym)

                logger.info(
                    f"AI Scanner added {len(picks)} stocks | "
                    f"Total trading universe: {len(symbols)} stocks"
                )
            except Exception as e:
                logger.error(f"Scanner error (using fixed watchlist): {e}")
        else:
            # Use cached scanner results
            for sym in self.scanner.get_dynamic_watchlist():
                if sym not in symbols:
                    symbols.append(sym)

        return symbols

    def run_scan(self):
        # type: () -> List[Dict[str, Any]]
        """Manually trigger a market scan (for Telegram /scan command)"""
        try:
            alpaca_movers = self.alpaca.get_most_active_stocks(limit=50)
            return self.scanner.full_market_scan(alpaca_movers=alpaca_movers)
        except Exception as e:
            logger.error(f"Manual scan error: {e}")
            return []

    def get_scan_summary(self):
        # type: () -> str
        """Get scan summary for Telegram"""
        return self.scanner.get_scan_summary()

    # ── API methods for Telegram bot ──

    def get_status(self) -> Dict:
        """Get bot status"""
        account = self.alpaca.get_account()
        positions = self.alpaca.get_positions()
        clock = self.alpaca.get_market_clock()

        return {
            "status": (
                "Running" if self.is_running and not self.is_paused
                else "Paused" if self.is_paused
                else "Stopped"
            ),
            "equity": account.get("equity", 0) if account else 0,
            "buying_power": account.get("buying_power", 0) if account else 0,
            "day_trade_count": account.get("day_trade_count", 0) if account else 0,
            "open_positions": len(positions),
            "trades_today": self.risk_manager.daily_trades,
            "daily_pnl": self.risk_manager.daily_loss + self.risk_manager.daily_profit,
            "mode": self.settings.trading_mode.upper(),
            "market_open": clock.get("is_open", False) if clock else False,
            "paper": "paper" in self.settings.alpaca_base_url,
            "last_update": datetime.now().isoformat(),
        }

    def get_balance(self) -> Dict:
        """Get balance info"""
        account = self.alpaca.get_account()
        if not account:
            return {"error": "Cannot fetch account"}

        total_pnl = sum(t.get("pnl", 0) for t in self.trades)
        return {
            "equity": account["equity"],
            "buying_power": account["buying_power"],
            "cash": account["cash"],
            "portfolio_value": account["portfolio_value"],
            "total_pnl": total_pnl,
        }

    def get_positions(self) -> List[Dict]:
        """Get open positions from Alpaca"""
        return self.alpaca.get_positions()

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades"""
        return sorted(
            self.trades,
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True,
        )[:limit]

    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        completed = [t for t in self.trades if t.get("pnl", 0) != 0]
        winners = [t for t in completed if t["pnl"] > 0]
        losers = [t for t in completed if t["pnl"] < 0]

        return {
            "total_trades": len(self.trades),
            "completed_trades": len(completed),
            "winning": len(winners),
            "losing": len(losers),
            "win_rate": (len(winners) / len(completed) * 100) if completed else 0,
            "total_pnl": sum(t.get("pnl", 0) for t in completed),
            "avg_win": sum(t["pnl"] for t in winners) / len(winners) if winners else 0,
            "avg_loss": sum(t["pnl"] for t in losers) / len(losers) if losers else 0,
            "best_trade": max((t["pnl"] for t in completed), default=0),
            "worst_trade": min((t["pnl"] for t in completed), default=0),
            "trades_today": self.risk_manager.daily_trades,
            "pnl_today": self.risk_manager.daily_loss + self.risk_manager.daily_profit,
        }

    def get_strategies(self) -> Dict[str, bool]:
        """Get enabled strategies"""
        return {
            name: strategy.enabled
            for name, strategy in self.strategy_manager.strategies.items()
        }

    def get_risk_metrics(self) -> Dict:
        """Get risk metrics"""
        return self.risk_manager.get_risk_metrics()
